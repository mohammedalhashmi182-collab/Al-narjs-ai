/* Public xAI voice page. The API key stays on the server; this file uses a short-lived client secret. */
(function () {
  const MAX = 180;
  const RATE = 24000;
  const EN = document.documentElement.lang === "en";
  const T = EN
    ? {
        idle: "Ready",
        connecting: "Connecting…",
        listening: "Listening…",
        speaking: "Speaking",
        ended: "Call ended",
        muted: "Microphone muted",
        again: "Start another call",
        endedTime: "The call reached its 3-minute limit.",
        mic: "We could not use the microphone. Allow it in the browser and try again.",
        noMic: "No microphone was found on this device.",
        limit: "The daily call limit has been reached, or the line is busy. Email or call us, or try again later.",
        missing: "The live call is not available right now. Email or call us and we will help.",
        down: "The connection failed. Check your internet and try again, or email or call us.",
        dropped: "The call dropped before it started.",
        youHung: "The call has ended. You can start another one.",
        missingShort: "Unavailable",
        limitShort: "Daily limit reached",
        unavailable: "Call unavailable",
        title: "Talk to the Al-Narjis agent",
      }
    : {
        idle: "جاهز",
        connecting: "يتصل…",
        listening: "يسمعك…",
        speaking: "يتحدث",
        ended: "انتهت المكالمة",
        muted: "المايك مكتوم",
        again: "ابدأ مكالمة جديدة",
        endedTime: "انتهى وقت المكالمة (3 دقائق).",
        mic: "ما قدرنا نوصل للمايك. اسمح للمتصفح باستخدام المايك وجرّب مرة ثانية.",
        noMic: "ما لقينا مايك في جهازك.",
        limit: "وصلنا للحد اليومي للمكالمات أو الخط مشغول. راسلنا أو اتصل، أو جرّب بعدين.",
        missing: "المكالمة الحية غير متاحة حالياً. راسلنا أو اتصل ونساعدك.",
        down: "صار خلل في الاتصال. تأكد من الإنترنت وجرّب مرة ثانية، أو راسلنا أو اتصل.",
        dropped: "انقطعت المكالمة قبل أن تبدأ.",
        youHung: "انتهت المكالمة. تقدر تبدأ مكالمة جديدة.",
        missingShort: "غير متاحة",
        limitShort: "الحد اليومي",
        unavailable: "المكالمة غير متاحة",
        title: "تحدث مع مستشار النرجس",
      };

  const $ = (id) => document.getElementById(id);
  const card = $("p");
  const status = $("s");
  const log = $("log");
  const vid = $("vid");
  const mute = $("mute");
  const timer = $("tm");
  const start = $("start");
  const wave = $("wave");
  if (!card || !start || !wave) return;

  document.title = T.title;
  if (EN) {
    mute.setAttribute("aria-label", "Mute microphone");
    $("end").setAttribute("aria-label", "End call");
    card.setAttribute("aria-label", "Live call with the Al-Narjis agent");
  }
  for (let k = 0; k < 44; k++) {
    const bar = document.createElement("i");
    bar.style.setProperty("--h", (8 + Math.abs(Math.sin(k * 0.7)) * 36 * (1 - Math.abs(k - 15) / 30)) + "px");
    bar.style.animationDelay = (k % 7) * 0.1 + "s";
    wave.append(bar);
  }

  const ST = { idle: T.idle, connecting: T.connecting, listening: T.listening, speaking: T.speaking, ended: T.ended };
  let socket = null;
  let audioCtx = null;
  let micStream = null;
  let processor = null;
  let tick = null;
  let startedAt = 0;
  let ending = false;
  let blocked = false;
  let playAt = 0;
  let outLevel = 0;
  let inLevel = 0;
  let agentRow = null;
  let sessionReady = false;
  let sessionInstructions = "";
  let sessionGreeting = "";
  let personaSent = false;
  let greetingSent = false;
  let openingSettled = false;
  const blockedIds = {};
  const heldAudio = {};

  function setMode(name) {
    card.classList.remove("idle", "listening", "speaking", "ready", "ended", "connecting");
    card.classList.add(name === "connecting" ? "ready" : name);
    if (name === "connecting") card.classList.add("connecting");
    const muted = mute.getAttribute("aria-pressed") === "true";
    status.textContent = name === "listening" && muted ? T.muted : ST[name];
    vid.classList.toggle("talk", name === "speaking");
  }

  function add(text, cls) {
    const row = document.createElement("div");
    row.className = "row" + (cls ? " " + cls : "");
    row.innerHTML = '<div class="av" aria-hidden="true">' + (cls === "u" ? "👤" : "") + '</div><div class="m"></div>';
    row.lastChild.textContent = text;
    log.append(row);
    log.scrollTop = 1e5;
    return row;
  }

  function fmt(seconds) {
    const value = Math.max(0, Math.ceil(seconds));
    return Math.floor(value / 60) + ":" + String(value % 60).padStart(2, "0");
  }

  function startTimer() {
    startedAt = performance.now();
    timer.textContent = fmt(MAX);
    timer.classList.remove("low");
    clearInterval(tick);
    tick = setInterval(() => {
      const left = MAX - (performance.now() - startedAt) / 1000;
      timer.textContent = fmt(left);
      timer.classList.toggle("low", left <= 20);
      if (left <= 0) {
        add(T.endedTime, "sys");
        endCall();
      }
    }, 250);
  }

  function limited(reason) {
    return reason === "daily_limit" || reason === "ip_limit" || reason === "busy";
  }

  function gateMessage(reason) {
    if (reason === "unconfigured") return T.missing;
    if (limited(reason)) return T.limit;
    return T.down;
  }

  function reveal(reason, lock) {
    const box = $("fallback");
    const msg = $("fallbackMsg");
    if (box && msg) {
      msg.textContent = gateMessage(reason);
      box.hidden = false;
    }
    if (lock) {
      blocked = true;
      start.disabled = true;
      start.textContent = T.unavailable;
      status.textContent = reason === "unconfigured" ? T.missingShort : T.limitShort;
    }
  }

  function finish() {
    clearInterval(tick);
    setMode("ended");
    mute.setAttribute("aria-pressed", "false");
    card.classList.remove("muted");
    start.textContent = blocked ? T.unavailable : T.again;
    start.disabled = blocked;
  }

  function stopMic() {
    if (processor) {
      try { processor.disconnect(); } catch (error) { /* already stopped */ }
      processor.onaudioprocess = null;
      processor = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }
  }

  function closeSocket() {
    const current = socket;
    socket = null;
    if (current) {
      current.onclose = null;
      try { current.close(); } catch (error) { /* already closed */ }
    }
  }

  function endCall() {
    if (ending) return;
    ending = true;
    stopMic();
    closeSocket();
    window.__outLvl = window.__inLvl = null;
    finish();
  }

  function resample(samples, fromRate) {
    if (fromRate === RATE) return samples;
    const ratio = fromRate / RATE;
    const length = Math.floor(samples.length / ratio);
    const out = new Float32Array(length);
    for (let i = 0; i < length; i++) {
      const index = i * ratio;
      const left = Math.floor(index);
      const right = Math.min(left + 1, samples.length - 1);
      const mix = index - left;
      out[i] = samples[left] * (1 - mix) + samples[right] * mix;
    }
    return out;
  }

  function pcm16Base64(samples) {
    const bytes = new Uint8Array(samples.length * 2);
    const view = new DataView(bytes.buffer);
    for (let i = 0; i < samples.length; i++) {
      const clamped = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    }
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  }

  function playPcm16(b64) {
    if (!audioCtx) return;
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const view = new DataView(bytes.buffer);
    const count = Math.floor(bytes.length / 2);
    if (!count) return;
    const buffer = audioCtx.createBuffer(1, count, RATE);
    const channel = buffer.getChannelData(0);
    let energy = 0;
    for (let i = 0; i < count; i++) {
      channel[i] = view.getInt16(i * 2, true) / 0x8000;
      energy += channel[i] * channel[i];
    }
    outLevel = Math.min(1, Math.sqrt(energy / count) * 4);
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    const now = audioCtx.currentTime;
    const when = Math.max(now, playAt);
    source.start(when);
    playAt = when + buffer.duration;
  }

  function agentText(delta, done) {
    if (!agentRow) agentRow = add("", "");
    const node = agentRow.querySelector(".m");
    if (done) {
      if (delta) node.textContent = delta;
      agentRow = null;
      return;
    }
    node.textContent += delta || "";
    log.scrollTop = 1e5;
  }

  function responseId(event) {
    return (event && (event.response_id || (event.response && event.response.id))) || "";
  }

  function dropEarly(event) {
    const id = responseId(event);
    if (greetingSent && !(id && blockedIds[id])) return false;
    if (id) blockedIds[id] = true;
    return true;
  }

  function vendorLine(text) {
    return /Grok|xAI|ChatGPT/.test(text || "");
  }

  function heldRow(id) {
    const key = id || "_";
    return heldAudio[key] || (heldAudio[key] = { chunks: [], text: "" });
  }

  function cancelResponse(id) {
    if (id) blockedIds[id] = true;
    const row = heldAudio[id || "_"];
    if (row) row.chunks = [];
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    const cancel = { type: "response.cancel" };
    if (id) cancel.response_id = id;
    socket.send(JSON.stringify(cancel));
  }

  function onEvent(event) {
    const type = event.type || "";
    // The published agent's greeting is a separate console line. It can speak
    // before instructions apply. Configure only after session.created, then
    // speak our line after session.updated. Drop anything earlier.
    if (type === "session.created") {
      configureSession();
      return;
    }
    if (type === "session.updated") {
      speakGreeting();
      sessionReady = true;
      if (!tick) startTimer();
      setMode("listening");
      return;
    }
    if (type === "input_audio_buffer.speech_started") {
      agentRow = null;
      setMode("listening");
      return;
    }
    if (type === "response.created") {
      if (dropEarly(event)) {
        cancelResponse(responseId(event));
        return;
      }
      if (openingSettled) setMode("speaking");
      return;
    }
    if (type === "response.output_audio.delta" || type === "response.audio.delta") {
      if (dropEarly(event)) return;
      if (!openingSettled) {
        const row = heldRow(responseId(event));
        if (event.delta) row.chunks.push(event.delta);
        return;
      }
      setMode("speaking");
      if (event.delta) playPcm16(event.delta);
      return;
    }
    if (type === "response.output_audio_transcript.delta" || type === "response.audio_transcript.delta" || type === "response.output_audio_transcript.done" || type === "response.audio_transcript.done") {
      if (dropEarly(event)) return;
      const done = type.endsWith(".done");
      const id = responseId(event);
      const row = heldRow(id);
      const piece = done ? (event.transcript || "") : (event.delta || "");
      if (done && event.transcript) row.text = event.transcript;
      else row.text += piece;
      if (vendorLine(row.text)) {
        cancelResponse(id);
        return;
      }
      if (!openingSettled) {
        const line = typeof sessionGreeting === "string" ? sessionGreeting.trim() : "";
        const probe = line.slice(0, 8);
        if ((probe && row.text.indexOf(probe) !== -1) || (done && row.text)) {
          openingSettled = true;
          setMode("speaking");
          row.chunks.forEach((chunk) => playPcm16(chunk));
          row.chunks = [];
          agentText(row.text, done);
        }
        return;
      }
      agentText(done ? (event.transcript || row.text) : (event.delta || ""), done);
      return;
    }
    if (type === "conversation.item.input_audio_transcription.completed") {
      const text = event.transcript || (event.item && event.item.transcript) || "";
      if (text) add(text, "u");
      return;
    }
    if (type === "response.done") {
      setMode(mute.getAttribute("aria-pressed") === "true" ? "listening" : "listening");
      outLevel *= 0.4;
      return;
    }
    if (type === "error") {
      const detail = (event.error && (event.error.message || event.error.code)) || event.message || "";
      console.warn("voice session error", { type: event.error && event.error.type, code: event.error && event.error.code, message: detail });
      add(detail ? T.down + " (" + String(detail).slice(0, 160) + ")" : T.down, "sys");
      reveal("upstream", false);
    }
  }

  function closeMessage(event) {
    const code = event && typeof event.code === "number" ? event.code : 0;
    const reason = event && event.reason ? String(event.reason).replace(/\s+/g, " ").slice(0, 160) : "";
    return T.dropped + (code ? " (" + code + ")" : "") + (reason ? " — " + reason : "");
  }

  function sessionOptions(payload) {
    const url = payload.websocket_url;
    const secret = payload.client_secret;
    if (typeof url !== "string" || !url.startsWith("wss://api.x.ai/v1/realtime")) return null;
    if (typeof secret !== "string" || secret.length < 8 || secret.indexOf(" ") >= 0) return null;
    const protocol = secret.startsWith("xai-client-secret.") ? secret : "xai-client-secret." + secret;
    return { url: url, protocol: protocol };
  }

  async function attachMic() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    audioCtx = audioCtx || new Ctx();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    const source = audioCtx.createMediaStreamSource(micStream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    const muteGain = audioCtx.createGain();
    muteGain.gain.value = 0;
    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      let energy = 0;
      for (let i = 0; i < input.length; i++) energy += input[i] * input[i];
      inLevel = Math.min(1, Math.sqrt(energy / input.length) * 4);
      if (!sessionReady || !socket || socket.readyState !== WebSocket.OPEN) return;
      if (mute.getAttribute("aria-pressed") === "true") return;
      if (audioCtx.currentTime < playAt) return;
      const samples = resample(input, audioCtx.sampleRate);
      socket.send(JSON.stringify({ type: "input_audio_buffer.append", audio: pcm16Base64(samples) }));
    };
    source.connect(processor);
    processor.connect(muteGain);
    muteGain.connect(audioCtx.destination);
    window.__outLvl = () => outLevel;
    window.__inLvl = () => inLevel;
  }

  function configureSession() {
    if (personaSent || !socket || socket.readyState !== WebSocket.OPEN) return;
    personaSent = true;
    const hint = EN ? "en" : "ar";
    const session = {
      turn_detection: { type: "server_vad" },
      audio: {
        input: { format: { type: "audio/pcm", rate: RATE }, transcription: { language_hint: hint } },
        output: { format: { type: "audio/pcm", rate: RATE } },
      },
    };
    if (typeof sessionInstructions === "string" && sessionInstructions.trim()) {
      session.instructions = sessionInstructions;
    }
    socket.send(JSON.stringify({ type: "session.update", session: session }));
  }

  function speakGreeting() {
    if (greetingSent || !socket || socket.readyState !== WebSocket.OPEN) return;
    const line = typeof sessionGreeting === "string" ? sessionGreeting.trim() : "";
    greetingSent = true;
    playAt = 0;
    if (!line) return;
    socket.send(JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "force_message",
        role: "assistant",
        interruptible: false,
        content: [{ type: "output_text", text: line }],
      },
    }));
  }

  start.onclick = async () => {
    if (socket || blocked) return;
    ending = false;
    sessionReady = false;
    sessionInstructions = "";
    sessionGreeting = "";
    personaSent = false;
    greetingSent = false;
    openingSettled = false;
    Object.keys(blockedIds).forEach((id) => { delete blockedIds[id]; });
    Object.keys(heldAudio).forEach((id) => { delete heldAudio[id]; });
    agentRow = null;
    playAt = 0;
    start.disabled = true;
    log.innerHTML = "";
    setMode("connecting");
    let payload = {};
    try {
      const response = await fetch("/api/voice/session?lang=" + (EN ? "en" : "ar"), { method: "POST", headers: { Accept: "application/json" } });
      try { payload = await response.json(); } catch (error) { payload = {}; }
      if (!response.ok || !payload.ok) {
        const reason = payload.reason || (response.status === 429 ? "daily_limit" : "upstream");
        add(gateMessage(reason), "sys");
        reveal(reason, reason === "unconfigured" || limited(reason));
        stopMic();
        ending = true;
        finish();
        return;
      }
      sessionInstructions = typeof payload.instructions === "string" ? payload.instructions : "";
      sessionGreeting = typeof payload.greeting === "string" ? payload.greeting : "";
      const options = sessionOptions(payload);
      if (!options) {
        add(T.missing, "sys");
        reveal("unconfigured", true);
        ending = true;
        finish();
        return;
      }
      try {
        await attachMic();
      } catch (error) {
        const name = String(error && error.name || "");
        add(/NotFound|device/i.test(name) ? T.noMic : T.mic, "sys");
        stopMic();
        ending = true;
        finish();
        return;
      }
      socket = new WebSocket(options.url, [options.protocol]);
      socket.onopen = () => {
        console.info("voice websocket open");
      };
      socket.onmessage = (message) => {
        if (typeof message.data !== "string") return;
        try { onEvent(JSON.parse(message.data)); } catch (error) { /* ignore a bad frame */ }
      };
      socket.onerror = () => {
        console.warn("voice websocket error");
        if (!ending) add(T.down, "sys");
      };
      socket.onclose = (event) => {
        const code = event && event.code;
        const reason = event && event.reason ? String(event.reason).slice(0, 160) : "";
        console.warn("voice websocket closed", { code: code, reason: reason, wasClean: !!(event && event.wasClean), ready: sessionReady });
        socket = null;
        if (!ending) {
          ending = true;
          const early = !sessionReady || (code && code !== 1000);
          if (early) {
            add(closeMessage(event), "sys");
            reveal("upstream", false);
          }
          stopMic();
          finish();
          if (early) status.textContent = T.dropped;
        }
      };
      start.disabled = false;
    } catch (error) {
      add(T.down, "sys");
      reveal("upstream", false);
      stopMic();
      closeSocket();
      ending = true;
      finish();
    }
  };

  mute.onclick = () => {
    if (!socket) return;
    const on = mute.getAttribute("aria-pressed") !== "true";
    mute.setAttribute("aria-pressed", on ? "true" : "false");
    card.classList.toggle("muted", on);
    if (!card.classList.contains("speaking")) status.textContent = on ? T.muted : ST.listening;
  };

  $("end").onclick = () => {
    if (socket) add(T.youHung, "sys");
    endCall();
  };

  window.addEventListener("pagehide", () => endCall());

  fetch("/api/voice/status", { headers: { Accept: "application/json" } })
    .then((response) => response.json())
    .then((payload) => {
      if (!payload || payload.ok) return;
      reveal(payload.reason, payload.reason === "unconfigured" || limited(payload.reason));
    })
    .catch(() => { /* the start button still asks the server */ });
})();
