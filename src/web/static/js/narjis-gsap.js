/**
 * Homepage scroll choreography: one pinned device, GSAP + ScrollTrigger.
 * Lenis only on wide, motion-capable desktops. Never required for first paint.
 * The first customer message plays on load (typing, then arrival) on every width.
 */
(function () {
  var html = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) html.setAttribute("data-reduce", "1");

  var bar = document.getElementById("v3-progress");
  var journey = document.getElementById("v3-journey");
  var frame = document.getElementById("v3-frame");
  if (!journey || !frame) return;

  var typing = journey.querySelector(".v3-typing");
  var b1 = journey.querySelector('.v3-bubble[data-step="1"]');
  var b2 = journey.querySelector('.v3-bubble[data-step="2"]');
  var alert = journey.querySelector('.v3-alert[data-step="3"]');
  var thread = journey.querySelector(".v3-thread");

  function showFirstMessage() {
    if (typing) typing.classList.remove("is-on");
    if (b1) b1.classList.add("is-on");
    if (thread) thread.classList.add("is-live");
  }

  function playIntro() {
    if (reduce || html.classList.contains("v3-static")) {
      showFirstMessage();
      return;
    }
    if (typing) typing.classList.add("is-on");
    window.setTimeout(showFirstMessage, 1100);
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    playIntro();
  } else {
    document.addEventListener("DOMContentLoaded", playIntro, { once: true });
  }

  if (html.classList.contains("v3-static") || reduce) return;

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
      revealOnScroll();
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
    if (!("IntersectionObserver" in window)) {
      beats.forEach(function (el) { el.classList.add("is-on"); });
      journey.querySelectorAll("[data-step]").forEach(function (el) { el.classList.add("is-on"); });
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
    var glare = frame.querySelector(".v3-glare");
    var copy = frame.querySelector(".v3-copy");
    var display = frame.querySelector(".display");
    var heroExit = frame.querySelectorAll(".eyebrow, .lead, .nj-voice-inline");
    var beats = gsap.utils.toArray(frame.querySelectorAll(".v3-beat"));
    var resolve = document.getElementById("v3-resolve");

    var toCenter = 0;
    if (phone) {
      var fr = frame.getBoundingClientRect();
      var pr = phone.getBoundingClientRect();
      toCenter = (fr.left + fr.width / 2) - (pr.left + pr.width / 2);
    }

    gsap.set(phone, { rotateY: 22, rotateX: 7, y: 16, scale: 0.96, transformPerspective: 1600 });
    gsap.set(field, { opacity: 0, x: -28 });
    if (glare) gsap.set(glare, { xPercent: -8 });
    beats.forEach(function (el) { gsap.set(el, { opacity: 0, y: 18 }); });
    if (resolve) gsap.set(resolve, { opacity: 0, y: 14, scale: 0.94 });

    var tl = gsap.timeline({
      defaults: { ease: ease },
      scrollTrigger: {
        trigger: journey,
        start: "top top",
        end: "+=380%",
        pin: frame,
        pinSpacing: true,
        scrub: 0.7,
        anticipatePin: 1,
        onUpdate: function (self) {
          window.__v3st = self;
          if (bar) bar.style.transform = "scaleX(" + self.progress + ")";
        }
      }
    });

    /* Signature: headline scales and leaves, phone walks to centre. */
    tl.to(display, { scale: 1.18, opacity: 0, y: -24, duration: 1.1 }, 0.15)
      .to(heroExit, { opacity: 0, y: -8, duration: 0.5 }, 0.15)
      .add(function () { if (frame) frame.classList.add("is-focus"); }, 0.35)
      .to(phone, { rotateY: 0, rotateX: 0, x: toCenter, y: -40, scale: 1.02, duration: 1.25 }, 0.2)
      .to(field, { x: 36, opacity: 0.04, duration: 1.25 }, 0.2)
      .to(glare, { xPercent: 14, duration: 1.25 }, 0.2)
      .to(beats[0], { opacity: 1, y: 0, duration: 0.4 }, 1.15)
      .to(beats[0], { opacity: 0, y: -14, duration: 0.25 }, 2.15)
      .to(beats[1], { opacity: 1, y: 0, duration: 0.35 }, 2.2)
      .to(b2, { opacity: 1, y: 0, duration: 0.35 }, 2.25)
      .to(phone, { rotateY: -10, rotateX: 2, duration: 0.7 }, 2.2)
      .to(glare, { xPercent: -6, duration: 0.7 }, 2.2)
      .to(beats[1], { opacity: 0, y: -14, duration: 0.25 }, 3.25)
      .to(beats[2], { opacity: 1, y: 0, duration: 0.35 }, 3.3)
      .to(alert, { opacity: 1, y: 0, duration: 0.35 }, 3.35)
      .to(phone, { rotateY: 0, rotateX: 0, y: -36, scale: 1.03, duration: 0.6 }, 3.3)
      .to(glare, { xPercent: 4, duration: 0.6 }, 3.3)
      .to(beats[2], { opacity: 0, y: -10, duration: 0.3 }, 3.6)
      .add(function () { if (frame) frame.classList.add("is-resolve"); }, 3.6)
      .to(resolve, { opacity: 1, y: 0, scale: 1, duration: 0.5 }, 3.65)
      .to({}, { duration: 0.85 });
  }
})();
