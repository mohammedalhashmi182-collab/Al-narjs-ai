/* Public voice and text advisor. The optional xAI session uses a short-lived client secret. */
(function () {
  const MAX = 180;
  const RATE = 24000;
  const EN = document.documentElement.lang === "en";
  const T = EN
    ? {
        idle: "Ready",
        connecting: "Connecting…",
        listening: "Listening…",
        thinking: "Thinking",
        speaking: "Speaking",
        ended: "Call ended",
        noRec: "This browser cannot hear you. Use the chat button and type your question.",
        muted: "Microphone muted",
        again: "Start another call",
        endedTime: "The call reached its 3-minute limit.",
        mic: "We could not use the microphone. Type here and we will reply in text.",
        noMic: "No microphone was found on this device. Type here and we will reply in text.",
        limit: "The voice line is busy or at its daily limit. Use text chat or try again later.",
        missing: "Voice is temporarily unavailable. You can still use text chat.",
        down: "The connection failed. Check your connection and try again.",
        dropped: "The call dropped before it started.",
        youHung: "The call has ended. You can start another one.",
        missingShort: "Unavailable",
        limitShort: "Daily limit reached",
        unavailable: "Call unavailable",
        title: "Talk to the Al-Narjis AI advisor",
        textChat: "Text chat",
        noSpeech: "We couldn't hear you. Try another call or use text chat.",
        noAudio: "We couldn't play audio on this device. You can continue in text.",
        hello: "Welcome to Al-Narjis. I'm the Al-Narjis AI advisor. How can I help?",
        placeholder: "Type to the Al-Narjis advisor",
      }
    : {
        idle: "جاهز",
        connecting: "يتصل…",
        listening: "يسمعك",
        thinking: "يفكر",
        speaking: "يتحدث",
        ended: "انتهت المكالمة",
        noRec: "هذا المتصفح لا يدعم الاستماع. استخدم زر الدردشة واكتب سؤالك.",
        muted: "المايك مكتوم",
        again: "ابدأ مكالمة جديدة",
        endedTime: "انتهى وقت المكالمة (3 دقائق).",
        mic: "ما قدرنا نستخدم المايك. اكتب هنا، ونرد عليك كتابة.",
        noMic: "ما لقينا مايك في جهازك. اكتب هنا، ونرد عليك كتابة.",
        limit: "الخط مشغول أو بلغ الحد اليومي للمكالمات. استخدم الدردشة النصية أو جرّب لاحقًا.",
        missing: "الصوت غير متاح مؤقتًا. تقدر تستخدم الدردشة النصية.",
        down: "صار خلل في الاتصال. تأكد من اتصالك وجرّب مرة ثانية.",
        dropped: "انقطعت المكالمة قبل أن تبدأ.",
        youHung: "انتهت المكالمة. تقدر تبدأ مكالمة جديدة.",
        missingShort: "غير متاحة",
        limitShort: "الحد اليومي",
        unavailable: "المكالمة غير متاحة",
        title: "تحدّث مع مستشار النرجس الذكي",
        textChat: "دردشة نصية",
        noSpeech: "ما قدرنا نسمعك. جرّب مكالمة جديدة أو استخدم الدردشة النصية.",
        noAudio: "ما قدرنا نشغّل الصوت على جهازك. تقدر تكمّل كتابة.",
        hello: "حياك الله في النرجس. معك مستشار النرجس الذكي. كيف أقدر أساعدك؟",
        placeholder: "اكتب لمستشار النرجس",
      };

  const $ = (id) => document.getElementById(id);
  const card = $("p");
  const status = $("s");
  const log = $("log");
  const mute = $("mute");
  const end = $("end");
  const timer = $("tm");
  const start = $("start");
  const wave = $("wave");
  const chatBtn = $("chat");
  const chatPanel = $("chatPanel");
  const say = $("say");
  const composer = $("composer");
  const send = $("send");
  if (!card || !start || !wave || !chatBtn || !chatPanel || !say || !composer) return;

  document.title = T.title;
  say.placeholder = T.placeholder;
  log.setAttribute("aria-label", EN ? "Chat with the Al-Narjis advisor" : "دردشة مستشار النرجس");
  if (EN) {
    mute.setAttribute("aria-label", "Mute microphone");
    end.setAttribute("aria-label", "End call");
    card.setAttribute("aria-label", "Live call with the Al-Narjis agent");
  }
  const motion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  const waveBars = [];
  for (let index = 0; index < 23; index++) {
    const bar = document.createElement("i");
    bar.style.setProperty("--n", String(index));
    wave.append(bar);
    waveBars.push(bar);
  }

  const ST = { idle: T.idle, connecting: T.connecting, listening: T.listening, thinking: T.thinking, speaking: T.speaking, ended: T.ended };
  let voiceMode = "speech";
  let mode = "idle";
  let callVersion = 0;
  let speechActive = false;
  let recognition = null;
  let cancelRecognition = null;
  let cancelSpeech = null;
  let resumeListening = null;
  let speechHistory = [];
  let socket = null;
  let audioCtx = null;
  let micStream = null;
  let micRequestId = 0;
  let processor = null;
  let micSource = null;
  let tick = null;
  let startedAt = 0;
  let ending = false;
  let blocked = false;
  let playAt = 0;
  let micAnalyser = null;
  let micSilence = null;
  let outAnalyser = null;
  let waveFrame = null;
  let connectionTimer = null;
  let playbackTimer = null;
  const playing = new Set();
  let agentRow = null;
  let sessionReady = false;
  let sessionInstructions = "";
  let sessionGreeting = "";
  let personaSent = false;
  let greetingSent = false;
  let greetingDone = false;
  let openingSettled = false;
  let chatOpen = false;
  let starting = null;
  const blockedIds = new Set();
  const heldAudio = new Map();
  const typedQueue = [];

  function isMuted() { return mute.getAttribute("aria-pressed") === "true"; }

  function setMode(name) {
    mode = name;
    card.classList.remove("idle", "listening", "speaking", "thinking", "ready", "ended", "connecting");
    card.classList.add(name === "connecting" ? "ready" : name);
    card.classList.toggle("call-active", speechActive || name === "connecting" || !!socket);
    if (name === "connecting") card.classList.add("connecting");
    status.textContent = chatOpen && name !== "thinking" ? T.textChat : name === "listening" && isMuted() ? T.muted : ST[name];
    updateWave();
  }

  let waveSignal = null;
  let waveData = null;
  function updateWave() {
    const signal = chatOpen || (motion && motion.matches) ? null : mode === "speaking" ? outAnalyser
      : mode === "listening" && !isMuted() ? micAnalyser : null;
    if (signal !== waveSignal) {
      waveSignal = signal;
      waveData = signal ? new Uint8Array(signal.frequencyBinCount) : null;
      if (!signal) waveBars.forEach((bar) => bar.style.setProperty("--amplitude", "1"));
    }
    if (!signal || waveFrame !== null || !window.requestAnimationFrame) return;
    waveFrame = window.requestAnimationFrame(() => {
      waveFrame = null;
      if (!waveSignal || (motion && motion.matches)) return;
      waveSignal.getByteFrequencyData(waveData);
      waveBars.forEach((bar, index) => {
        const sample = waveData[1 + Math.abs(index - 11) * 3];
        bar.style.setProperty("--amplitude", (1 + sample / 36).toFixed(2));
      });
      updateWave();
    });
  }
  if (motion && motion.addEventListener) motion.addEventListener("change", updateWave);

  let userRow = null;

  function add(text, cls) {
    const row = document.createElement("div");
    row.className = "row" + (cls ? " " + cls : "");
    row.innerHTML = '<div class="av" aria-hidden="true">' + (cls === "u" ? "👤" : "") + '</div><div class="m"></div>';
    row.lastChild.textContent = text;
    log.append(row);
    log.scrollTop = 1e5;
    return row;
  }

  function userText(text, done) {
    if (!userRow) userRow = add("", "u");
    const node = userRow.querySelector(".m");
    if (done) {
      if (text) node.textContent = text;
      userRow = null;
    } else {
      node.textContent = text || "";
    }
    log.scrollTop = 1e5;
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
    tick = null;
    clearTimeout(connectionTimer);
    connectionTimer = null;
    setMode("ended");
    mute.setAttribute("aria-pressed", "false");
    card.classList.remove("muted");
    start.textContent = blocked ? T.unavailable : T.again;
    start.disabled = blocked;
  }

  function stopMic() {
    micRequestId++;
    if (processor) {
      try { processor.disconnect(); } catch (error) { /* already stopped */ }
      processor.onaudioprocess = null;
      processor = null;
    }
    if (micAnalyser) {
      try { micAnalyser.disconnect(); } catch (error) { /* already stopped */ }
      micAnalyser = null;
    }
    if (micSilence) {
      try { micSilence.disconnect(); } catch (error) { /* already stopped */ }
      micSilence = null;
    }
    if (micSource) {
      try { micSource.disconnect(); } catch (error) { /* already stopped */ }
      micSource = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }
    updateWave();
  }

  function ensureOutAnalyser() {
    if (outAnalyser || !audioCtx || typeof audioCtx.createAnalyser !== "function") return outAnalyser;
    try {
      const node = audioCtx.createAnalyser();
      node.fftSize = 1024;
      node.smoothingTimeConstant = 0.45;
      node.connect(audioCtx.destination);
      outAnalyser = node;
      updateWave();
      return node;
    } catch (error) {
      return null;
    }
  }

  function closeSocket() {
    const current = socket;
    socket = null;
    if (current) {
      current.onmessage = null;
      current.onclose = null;
      try { current.close(); } catch (error) { /* already closed */ }
    }
  }

  function stopPlayback() {
    clearTimeout(playbackTimer);
    playbackTimer = null;
    for (const source of playing) {
      try { source.stop(); } catch (error) { /* already stopped */ }
      source.disconnect();
    }
    playing.clear();
    playAt = 0;
    if (cancelSpeech) cancelSpeech();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function endCall() {
    if (ending) return;
    ending = true;
    callVersion++;
    speechActive = false;
    sessionReady = false;
    stopMic();
    stopRecognition();
    if (resumeListening) resumeListening();
    stopPlayback();
    closeSocket();
    if (audioCtx && audioCtx.close) audioCtx.close().catch(() => {});
    audioCtx = null;
    outAnalyser = null;
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
    for (let i = 0; i < count; i++) {
      channel[i] = view.getInt16(i * 2, true) / 0x8000;
    }
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    const tap = ensureOutAnalyser();
    source.connect(tap || audioCtx.destination);
    const now = audioCtx.currentTime;
    const when = Math.max(now, playAt);
    playing.add(source);
    source.onended = () => {
      if (playing.delete(source)) source.disconnect();
    };
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
    if (greetingSent && !(id && blockedIds.has(id))) return false;
    if (id) blockedIds.add(id);
    return true;
  }

  function vendorLine(text) {
    return /Grok|xAI|ChatGPT/.test(text || "");
  }

  function heldRow(id) {
    const key = id || "_";
    if (!heldAudio.has(key)) heldAudio.set(key, { chunks: [], text: "" });
    return heldAudio.get(key);
  }

  function cancelResponse(id) {
    if (id) blockedIds.add(id);
    const row = heldAudio.get(id || "_");
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
      clearTimeout(connectionTimer);
      connectionTimer = null;
      if (chatOpen) greetInText();
      else speakGreeting();
      sessionReady = true;
      if (!tick) startTimer();
      setMode("listening");
      return;
    }
    if (type === "input_audio_buffer.speech_started") {
      agentRow = null;
      userRow = null;
      setMode("listening");
      return;
    }
    if (type === "input_audio_buffer.speech_stopped") {
      setMode("thinking");
      return;
    }
    if (type === "response.created") {
      if (dropEarly(event)) {
        cancelResponse(responseId(event));
        return;
      }
      if (openingSettled) setMode("thinking");
      return;
    }
    if (type === "response.output_audio.delta" || type === "response.audio.delta") {
      if (dropEarly(event)) return;
      if (!openingSettled) {
        const row = heldRow(responseId(event));
        if (event.delta) row.chunks.push(event.delta);
        return;
      }
      if (chatOpen) return;
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
          if (!chatOpen) {
            setMode("speaking");
            row.chunks.forEach((chunk) => playPcm16(chunk));
          }
          row.chunks = [];
          agentText(row.text, done);
        }
        return;
      }
      agentText(done ? (event.transcript || row.text) : (event.delta || ""), done);
      return;
    }
    if (type === "conversation.item.input_audio_transcription.updated") {
      const text = event.transcript || (event.item && event.item.transcript) || "";
      if (text) userText(text, false);
      return;
    }
    if (type === "conversation.item.input_audio_transcription.completed") {
      const text = event.transcript || (event.item && event.item.transcript) || "";
      if (text) userText(text, true);
      if (wantsChat(text)) openChat();
      return;
    }
    if (type === "response.done") {
      const doneId = responseId(event);
      if (greetingSent && !greetingDone && !(doneId && blockedIds.has(doneId))) {
        greetingDone = true;
        flushTyped();
      }
      clearTimeout(playbackTimer);
      if (!chatOpen && audioCtx && playAt > audioCtx.currentTime) {
        playbackTimer = setTimeout(() => setMode("listening"), (playAt - audioCtx.currentTime) * 1000);
      } else setMode("listening");
      heldAudio.delete(doneId || "_");
      return;
    }
    if (type === "error") {
      showMicProblem(T.down);
      endCall();
    }
  }

  function sessionOptions(payload) {
    const url = payload.websocket_url;
    const secret = payload.client_secret;
    if (typeof url !== "string" || !url.startsWith("wss://api.x.ai/v1/realtime")) return null;
    if (typeof secret !== "string" || secret.length < 8 || secret.indexOf(" ") >= 0) return null;
    const protocol = secret.startsWith("xai-client-secret.") ? secret : "xai-client-secret." + secret;
    return { url: url, protocol: protocol };
  }

  async function ensureAudio() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audioCtx = audioCtx || new Ctx();
    if (audioCtx.state === "suspended") await audioCtx.resume();
  }

  async function attachMic(version) {
    const requestId = ++micRequestId;
    await ensureAudio();
    if (version !== callVersion || requestId !== micRequestId || chatOpen) return;
    if (!audioCtx || !navigator.mediaDevices) throw new Error("Audio capture unavailable");
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    if (version !== callVersion || requestId !== micRequestId || chatOpen) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    micStream = stream;
    if (isMuted()) stream.getAudioTracks().forEach((track) => { track.enabled = false; });
    micSource = audioCtx.createMediaStreamSource(micStream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    micSilence = audioCtx.createGain();
    micSilence.gain.value = 0;
    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      if (!sessionReady || !socket || socket.readyState !== WebSocket.OPEN) return;
      if (chatOpen || isMuted()) return;
      if (audioCtx.currentTime < playAt) return;
      const samples = resample(input, audioCtx.sampleRate);
      socket.send(JSON.stringify({ type: "input_audio_buffer.append", audio: pcm16Base64(samples) }));
    };
    micSource.connect(processor);
    processor.connect(micSilence);
    micSilence.connect(audioCtx.destination);
    if (typeof audioCtx.createAnalyser === "function") {
      try {
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.45;
        micSource.connect(analyser);
        analyser.connect(micSilence);
        micAnalyser = analyser;
        updateWave();
      } catch (error) { /* the call still sends audio without a visual tap */ }
    }
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
    if (!line) {
      greetingDone = true;
      openingSettled = true;
      flushTyped();
      return;
    }
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

  function greetInText() {
    if (greetingSent) return;
    greetingSent = true;
    openingSettled = true;
    greetingDone = true;
    const line = typeof sessionGreeting === "string" ? sessionGreeting.trim() : "";
    if (line) add(line, "");
    flushTyped();
  }

  function wantsChat(text) {
    return /دردش|بالكتاب|اكتب|أكتب|كتابة|كتابه|شات|\bchat\b|\btyping\b|\btype\b/i.test(text || "");
  }

  function openChat() {
    if (!chatOpen) {
      chatOpen = true;
      stopMic();
      stopPlayback();
      if (speechActive) endCall();
      setMode(mode);
    }
    card.classList.add("chat-open");
    chatPanel.hidden = false;
    chatBtn.setAttribute("aria-expanded", "true");
    if (say.focus) say.focus();
  }

  function closeChat() {
    chatOpen = false;
    card.classList.remove("chat-open");
    chatPanel.hidden = true;
    chatBtn.setAttribute("aria-expanded", "false");
    setMode(mode);
  }

  function showMicProblem(note) {
    card.classList.add("no-mic");
    const box = $("micNote");
    if (box) {
      box.hidden = false;
      box.textContent = note;
    }
    openChat();
  }

  function clearMicProblem() {
    const note = $("micNote");
    if (note) note.hidden = true;
    card.classList.remove("no-mic");
  }

  function sendTyped(line) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text: line }],
      },
    }));
    socket.send(JSON.stringify({ type: "response.create" }));
  }

  function flushTyped() {
    if (!greetingDone || !socket || socket.readyState !== WebSocket.OPEN) return;
    while (typedQueue.length) sendTyped(typedQueue.shift());
  }

  async function beginCall() {
    if (blocked) return false;
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return true;
    if (starting) return starting;
    starting = startRealtime();
    try { return await starting; }
    finally { starting = null; }
  }

  async function startRealtime() {
    const version = ++callVersion;
    ending = false;
    sessionReady = false;
    sessionInstructions = "";
    sessionGreeting = "";
    personaSent = false;
    greetingSent = false;
    greetingDone = false;
    openingSettled = false;
    typedQueue.splice(0, typedQueue.length);
    blockedIds.clear();
    heldAudio.clear();
    agentRow = null;
    playAt = 0;
    start.disabled = true;
    log.innerHTML = "";
    setMode("connecting");
    let payload = {};
    try {
      const response = await fetch("/api/voice/session?lang=" + (EN ? "en" : "ar"), { method: "POST", headers: { Accept: "application/json" } });
      try { payload = await response.json(); } catch (error) { payload = {}; }
      if (version !== callVersion) return false;
      if (!response.ok || !payload.ok) {
        const reason = payload.reason || (response.status === 429 ? "daily_limit" : "upstream");
        add(gateMessage(reason), "sys");
        reveal(reason, reason === "unconfigured" || limited(reason));
        endCall();
        return false;
      }
      sessionInstructions = typeof payload.instructions === "string" ? payload.instructions : "";
      sessionGreeting = typeof payload.greeting === "string" ? payload.greeting : "";
      const options = sessionOptions(payload);
      if (!options) {
        add(T.missing, "sys");
        reveal("unconfigured", true);
        endCall();
        return false;
      }
      try {
        await attachMic(version);
      } catch (error) {
        if (version !== callVersion) return false;
        const name = String(error && error.name || "");
        showMicProblem(/NotFound|device/i.test(name) ? T.noMic : T.mic);
      }
      if (version !== callVersion) return false;
      socket = new WebSocket(options.url, [options.protocol]);
      connectionTimer = setTimeout(() => {
        showMicProblem(T.dropped);
        endCall();
      }, 15000);
      socket.onmessage = (message) => {
        if (typeof message.data !== "string") return;
        try { onEvent(JSON.parse(message.data)); } catch (error) { /* ignore a bad frame */ }
      };
      socket.onclose = (event) => {
        const code = event && event.code;
        socket = null;
        if (!ending) {
          const early = !sessionReady || (code && code !== 1000);
          if (early) showMicProblem(T.dropped);
          endCall();
        }
      };
      start.disabled = false;
      return true;
    } catch (error) {
      if (version === callVersion) {
        showMicProblem(T.down);
        endCall();
      }
      return false;
    }
  }

  function speechInput() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function stopRecognition() {
    const current = recognition;
    recognition = null;
    if (!current) return;
    current.onresult = current.onerror = current.onend = null;
    try { current.abort(); } catch (error) { /* already stopped */ }
    if (cancelRecognition) cancelRecognition();
    cancelRecognition = null;
  }

  function pickVoice() {
    if (!window.speechSynthesis || !window.speechSynthesis.getVoices) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    if (EN) return voices.find((voice) => /en[-_]US/i.test(voice.lang)) || voices.find((voice) => /^en/i.test(voice.lang)) || null;
    return voices.find((voice) => /^ar/i.test(voice.lang)) || voices.find((voice) => /ar/i.test(voice.lang)) || null;
  }

  function speakAloud(text) {
    return new Promise((resolve) => {
      if (!text || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
        resolve(false);
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new window.SpeechSynthesisUtterance(text);
      utterance.lang = EN ? "en-US" : "ar-SA";
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      const done = (played) => {
        utterance.onend = utterance.onerror = null;
        cancelSpeech = null;
        resolve(played);
      };
      cancelSpeech = () => done(false);
      utterance.onend = () => done(true);
      utterance.onerror = () => done(false);
      setMode("speaking");
      try { window.speechSynthesis.speak(utterance); } catch (error) { done(false); }
    });
  }

  function listenOnce() {
    const Ctor = speechInput();
    if (!Ctor || ending) return Promise.resolve({ error: "aborted" });
    stopRecognition();
    return new Promise((resolve) => {
      let settled = false;
      const done = (result) => {
        if (settled) return;
        settled = true;
        resolve(result);
      };
      const rec = new Ctor();
      recognition = rec;
      cancelRecognition = () => done({ error: "cancelled" });
      rec.lang = EN ? "en-US" : "ar-SA";
      rec.interimResults = false;
      rec.continuous = false;
      rec.onresult = (event) => {
        const result = event.results && event.results[0] && event.results[0][0];
        done({ text: (result && result.transcript || "").trim() });
      };
      rec.onerror = (event) => done({ error: event.error });
      rec.onend = () => {
        if (recognition === rec) {
          recognition = null;
          cancelRecognition = null;
        }
        done({ error: "no-speech" });
      };
      setMode("listening");
      try { rec.start(); } catch (error) { done({ error: "not-allowed" }); }
    });
  }

  async function askReply(line) {
    try {
      const response = await fetch("/api/voice/reply", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ text: line.slice(0, 500), lang: EN ? "en" : "ar", history: speechHistory.slice(-8) }),
      });
      const payload = await response.json();
      if (response.ok && payload.ok && payload.reply) return payload.reply;
    } catch (error) { /* report a localized connection failure */ }
    return "";
  }

  function rememberReply(line, reply) {
    speechHistory = speechHistory.slice(-6);
    speechHistory.push({ role: "user", content: line.slice(0, 500) }, { role: "assistant", content: reply });
  }

  async function beginSpeech() {
    if (speechActive) return;
    if (!speechInput()) {
      showMicProblem(T.noRec);
      return;
    }
    const version = ++callVersion;
    ending = false;
    speechActive = true;
    start.disabled = true;
    const hello = sessionGreeting || T.hello;
    startTimer();
    add(hello, "");
    if (!await speakAloud(hello) && version === callVersion) {
      showMicProblem(T.noAudio);
      return;
    }
    while (version === callVersion) {
      setMode("listening");
      if (isMuted()) {
        await new Promise((resolve) => { resumeListening = resolve; });
        resumeListening = null;
        continue;
      }
      const { text, error } = await listenOnce();
      if (version !== callVersion) return;
      if (error === "cancelled") continue;
      if (!text) {
        const note = error === "audio-capture" ? T.noMic : error === "no-speech" ? T.noSpeech : T.mic;
        showMicProblem(note);
        return;
      }
      add(text, "u");
      if (wantsChat(text)) {
        openChat();
        return;
      }
      setMode("thinking");
      const reply = await askReply(text);
      if (version !== callVersion) return;
      if (!reply) {
        showMicProblem(T.down);
        return;
      }
      rememberReply(text, reply);
      add(reply, "");
      if (!await speakAloud(reply) && version === callVersion) {
        showMicProblem(T.noAudio);
        return;
      }
    }
  }

  start.onclick = () => {
    if (chatOpen || start.disabled) return;
    clearMicProblem();
    const call = voiceMode === "xai" ? beginCall() : beginSpeech();
    if (!chatOpen && end.focus) end.focus();
    return call;
  };

  chatBtn.onclick = openChat;

  composer.onsubmit = async (event) => {
    event.preventDefault();
    openChat();
    const line = say.value.trim();
    if (!line || send.disabled) return;
    say.value = "";
    add(line, "u");
    if (socket || starting) {
      typedQueue.push(line);
      if (socket || await starting) {
        flushTyped();
        return;
      }
      typedQueue.length = 0;
    }
    send.disabled = true;
    const previous = mode;
    setMode("thinking");
    const reply = await askReply(line);
    send.disabled = false;
    if (!reply) add(T.down, "sys");
    else {
      rememberReply(line, reply);
      add(reply, "");
    }
    if (mode === "thinking") setMode(previous);
  };

  $("voiceBack").onclick = async () => {
    closeChat();
    if (!socket || blocked) {
      (start.disabled ? chatBtn : start).focus();
      return;
    }
    try {
      await attachMic(callVersion);
      if (micStream && !chatOpen) clearMicProblem();
    } catch (error) {
      const name = String(error && error.name || "");
      showMicProblem(/NotFound|device/i.test(name) ? T.noMic : T.mic);
    }
  };

  mute.onclick = () => {
    if (!socket && !speechActive) return;
    const on = !isMuted();
    mute.setAttribute("aria-pressed", on ? "true" : "false");
    card.classList.toggle("muted", on);
    if (on) stopRecognition();
    else if (resumeListening) resumeListening();
    if (micStream) micStream.getAudioTracks().forEach((track) => { track.enabled = !on; });
    setMode(mode);
  };

  end.onclick = () => {
    if (socket) add(T.youHung, "sys");
    endCall();
    if (!chatOpen && !start.disabled) start.focus();
  };

  window.addEventListener("pagehide", () => endCall());

  fetch("/api/voice/status", { headers: { Accept: "application/json" } })
    .then((response) => response.json())
    .then((payload) => {
      if (payload && payload.greeting) sessionGreeting = payload.greeting;
      if (payload && payload.mode === "xai") voiceMode = "xai";
      if (!payload || payload.ok || voiceMode !== "xai") return;
      reveal(payload.reason, payload.reason === "unconfigured" || limited(payload.reason));
    })
    .catch(() => { /* the start button still asks the server */ });
})();
