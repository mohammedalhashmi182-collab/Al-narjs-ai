/**
 * Homepage scroll choreography: one pinned device, GSAP + ScrollTrigger.
 * Lenis only on wide, motion-capable desktops. Never required for first paint.
 */
(function () {
  var html = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) html.setAttribute("data-reduce", "1");
  if (html.classList.contains("v3-static") || reduce) return;

  var bar = document.getElementById("v3-progress");
  var journey = document.getElementById("v3-journey");
  var frame = document.getElementById("v3-frame");
  if (!journey || !frame) return;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  function afterPaint(fn) {
    var ric = window.requestIdleCallback;
    if (ric) ric(fn, { timeout: 1600 });
    else setTimeout(fn, 350);
  }

  var wide = window.matchMedia("(min-width: 900px)").matches;

  afterPaint(function () {
    if (!wide) {
      var viewTimeline = false;
      try { viewTimeline = CSS.supports("animation-timeline: view()"); } catch (e) {}
      if (!viewTimeline) revealOnScroll();
      return;
    }
    Promise.all([
      loadScript("/static/vendor/gsap.min.js"),
      loadScript("/static/vendor/ScrollTrigger.min.js"),
      loadScript("/static/vendor/lenis.min.js")
    ]).then(start).catch(function () {
      revealOnScroll();
    });
  });

  function revealOnScroll() {
    var beats = journey.querySelectorAll(".v3-beat");
    var thread = journey.querySelector(".v3-thread");
    if (!("IntersectionObserver" in window)) {
      beats.forEach(function (el) { el.classList.add("is-on"); });
      journey.querySelectorAll("[data-step]").forEach(function (el) { el.classList.add("is-on"); });
      if (thread) thread.classList.add("is-live");
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var beat = e.target;
        beats.forEach(function (b) { b.classList.toggle("is-on", b === beat); });
        var n = Number(beat.getAttribute("data-beat") || "0");
        journey.querySelectorAll("[data-step]").forEach(function (el) {
          var step = Number(el.getAttribute("data-step") || "0");
          el.classList.toggle("is-on", step <= n);
        });
        if (thread) thread.classList.toggle("is-live", n >= 1);
      });
    }, { threshold: 0.45, rootMargin: "0px 0px -10% 0px" });
    beats.forEach(function (el) { io.observe(el); });
  }

  function start() {
    var gsap = window.gsap;
    var ScrollTrigger = window.ScrollTrigger;
    var Lenis = window.Lenis;
    if (!gsap || !ScrollTrigger) {
      revealOnScroll();
      return;
    }
    gsap.registerPlugin(ScrollTrigger);

    if (typeof Lenis === "function") {
      var lenis = new Lenis({ lerp: 0.085, smoothWheel: true });
      window.__v3lenis = lenis;
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
      gsap.ticker.lagSmoothing(0);
    }

    var ease = "power3.out";
    var phone = frame.querySelector(".v3-phone");
    var field = frame.querySelector(".v3-field");
    var copy = frame.querySelector(".v3-copy");
    var heroGhost = frame.querySelectorAll(".display, .nj-voice-inline");
    var heroExit = frame.querySelectorAll(".eyebrow, .lead");
    var em = frame.querySelectorAll(".display em");
    var beats = gsap.utils.toArray(frame.querySelectorAll(".v3-beat"));
    var thread = frame.querySelector(".v3-thread");
    var b1 = journey.querySelector('.v3-bubble[data-step="1"]');
    var b2 = journey.querySelector('.v3-bubble[data-step="2"]');
    var alert = journey.querySelector('.v3-alert[data-step="3"]');

    gsap.set(phone, { rotateY: 26, rotateX: 8, y: 28, scale: 0.92, transformPerspective: 1400 });
    gsap.set(field, { opacity: 0.04, x: 24 });
    beats.forEach(function (el) { gsap.set(el, { opacity: 0, y: 18 }); });

    var tl = gsap.timeline({
      defaults: { ease: ease },
      scrollTrigger: {
        trigger: journey,
        start: "top top",
        end: "+=360%",
        pin: frame,
        pinSpacing: true,
        scrub: 0.65,
        anticipatePin: 1,
        onUpdate: function (self) {
          window.__v3st = self;
          if (bar) bar.style.transform = "scaleX(" + self.progress + ")";
        }
      }
    });

    tl.to(phone, { rotateY: 0, rotateX: 0, y: 0, scale: 1, duration: 1.0 }, 0)
      .to(field, { opacity: 0.05, x: 0, duration: 1.0 }, 0)
      .to(heroGhost, { opacity: 0.16, duration: 0.45 }, 1.0)
      .to(heroExit, { opacity: 0, duration: 0.4 }, 1.0)
      .add(function () { if (copy) copy.classList.add("is-dimmed"); }, 1.0)
      .to(em, { color: "#f5f5f5", duration: 0.45 }, 1.0)
      .to(beats[0], { opacity: 1, y: 0, duration: 0.35 }, 1.1)
      .to(b1, { opacity: 1, y: 0, duration: 0.35 }, 1.15)
      .add(function () { if (thread) thread.classList.add("is-live"); }, 1.15)
      .to(beats[0], { opacity: 0, y: -14, duration: 0.25 }, 2.15)
      .to(beats[1], { opacity: 1, y: 0, duration: 0.35 }, 2.2)
      .to(b2, { opacity: 1, y: 0, duration: 0.35 }, 2.25)
      .to(phone, { rotateY: -12, rotateX: 2, duration: 0.7 }, 2.2)
      .to(beats[1], { opacity: 0, y: -14, duration: 0.25 }, 3.25)
      .to(beats[2], { opacity: 1, y: 0, duration: 0.35 }, 3.3)
      .to(alert, { opacity: 1, y: 0, duration: 0.35 }, 3.35)
      .to(phone, { rotateY: 0, rotateX: 0, scale: 1.015, duration: 0.55 }, 3.3)
      .to({}, { duration: 0.8 });
  }
})();
