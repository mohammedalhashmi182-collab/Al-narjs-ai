/* Lightweight xAI-style voice ribbon — original rendering, no Grok assets.
   Driven by live in/out PCM level functions from voice-live-app.js; never records.
   No added libraries, GPU, network calls or microphone permissions. */
(() => {
  "use strict";
  const canvas = document.getElementById("ribbon");
  const card = document.getElementById("p");
  const vid = document.getElementById("vid");
  const bars = document.getElementById("wave");
  if (!canvas || !card || !vid || !canvas.getContext) return;

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  let width = 660, height = 190, clock = 0, previous = 0;
  let level = 0, target = 0, raf = null, lastBarFrame = 0;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = Math.max(140, Math.min(canvas.clientWidth || 660, 800));
    height = Math.max(90, Math.min(canvas.clientHeight || 190, 280));
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    render();
  }

  function amplitude() {
    const talking = card.classList.contains("speaking");
    const listening = card.classList.contains("listening");
    const sample = talking ? window.__outLvl : listening ? window.__inLvl : null;
    const raw = typeof sample === "function" ? Number(sample()) : 0;
    const safe = Number.isFinite(raw) ? Math.max(0, Math.min(raw, 1)) : 0;
    return { val: safe, engaged: talking || listening };
  }

  function render() {
    ctx.clearRect(0, 0, width, height);
    const center = height * 0.5;
    const spread = height * 0.26;
    const glow = ctx.createRadialGradient(width / 2, center, 8, width / 2, center, width * 0.39);
    glow.addColorStop(0, "rgba(214,237,244,.105)");
    glow.addColorStop(0.44, "rgba(201,162,122,.028)");
    glow.addColorStop(1, "rgba(214,237,244,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);

    // Seven flowing ribbons read as a continuous voice field rather than a sphere.
    for (let band = 0; band < 7; band++) {
      ctx.beginPath();
      const offset = (band - 3) * 5.7;
      const thickness = 1.05 + (band === 3 ? .65 : 0);
      const energy = (reduce.matches ? 0 : level);
      const amp = 4 + (energy * 41) + (band % 2) * 2;
      for (let x = 0; x <= width + 2; x += 5) {
        const t = x / width;
        const envelope = Math.pow(Math.max(0, Math.sin(t * Math.PI)), 2.0);
        const phase = (reduce.matches ? 0 : clock * (1.45 + band * .07));
        const wave = Math.sin(t * 15 - phase + band * .53) * .72
          + Math.sin(t * 25 + phase * 1.3 - band * .31) * .21;
        const drift = (reduce.matches ? 0 : Math.sin(clock * .6 + band) * 2.2);
        const y = center + offset + (wave * amp * envelope) + drift;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = band === 3 ? "rgba(248,251,253,.92)"
        : (band % 2 ? "rgba(201,162,122,.39)" : "rgba(214,237,244,.54)");
      ctx.shadowColor = band === 3 ? "rgba(214,237,244,.60)" : "rgba(214,237,244,.12)";
      ctx.shadowBlur = band === 3 ? 16 : 7;
      ctx.lineWidth = thickness;
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }

  function frame(time) {
    if (document.hidden) {
      raf = null;
      return;
    }
    // Cap redraws to ~30fps on mobile and protect the 0.5 CPU site.
    if (time - previous >= 32) {
      const dt = Math.min(.06, Math.max(0, time - previous) / 1000);
      previous = time;
      clock += dt;
      const state = amplitude();
      target = state.val;
      level += (target - level) * Math.min(1, dt * 12);
      if (state.engaged && bars && time - lastBarFrame > 95) {
        lastBarFrame = time;
        const all = bars.querySelectorAll("i");
        for (let i = 0; i < all.length; i++) {
          const widthFactor = Math.max(0, Math.sin((i / Math.max(1, all.length - 1)) * Math.PI));
          const heightPx = 5 + Math.round((8 + level * 30) * widthFactor *
            (0.48 + 0.52 * Math.abs(Math.sin(clock * 4 + i * .46))));
          all[i].style.height = heightPx + "px";
        }
      }
      render();
    }
    raf = window.requestAnimationFrame(frame);
  }

  function start() {
    if (raf !== null || document.hidden || reduce.matches) return;
    previous = 0;
    raf = window.requestAnimationFrame(frame);
  }
  function stop() {
    if (raf !== null) window.cancelAnimationFrame(raf);
    raf = null;
  }
  function motion() {
    stop();
    clock = 0; level = 0;
    render();
    start();
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });
  window.addEventListener("resize", resize, { passive: true });
  if (reduce.addEventListener) reduce.addEventListener("change", motion);
  resize();
  start();
})();
