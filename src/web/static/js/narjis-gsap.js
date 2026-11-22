/**
 * Homepage scroll choreography: one pinned photoreal phone, GSAP + ScrollTrigger.
 * Lenis only on wide desktops. First customer message plays on load at every width.
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
  var alertCard = journey.querySelector('.v3-alert[data-step="3"]');
  var thread = journey.querySelector(".v3-thread");
  var beats = journey.querySelectorAll(".v3-beat");

  function setChapter(name) {
    frame.setAttribute("data-chapter", name);
    var focus = name === "1" || name === "2" || name === "3";
    frame.classList.toggle("is-focus", focus);
    frame.classList.toggle("is-resolve", name === "resolve");
    beats.forEach(function (el) {
      el.classList.toggle("is-on", el.getAttribute("data-beat") === name);
    });
  }

  function showFirstMessage() {
    if (typing) typing.classList.remove("is-on");
    if (b1) b1.classList.add("is-on");
    if (thread) thread.classList.add("is-live");
  }

  function playIntro() {
    if (reduce || html.classList.contains("v3-static")) {
      showFirstMessage();
      if (b2) b2.classList.add("is-on");
      if (alertCard) alertCard.classList.add("is-on");
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
    var loaders = [
      loadScript("/static/vendor/gsap.min.js"),
      loadScript("/static/vendor/ScrollTrigger.min.js")
    ];
    if (wide) loaders.push(loadScript("/static/vendor/lenis.min.js"));
    Promise.all(loaders).then(start).catch(function () {
      revealOnScroll();
    });
  });

  function revealOnScroll() {
    if (!("IntersectionObserver" in window)) {
      beats.forEach(function (el) { el.classList.add("is-on"); });
      journey.querySelectorAll("[data-step]").forEach(function (el) { el.classList.add("is-on"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var n = e.target.getAttribute("data-beat") || "1";
        setChapter(n);
        journey.querySelectorAll("[data-step]").forEach(function (el) {
          var step = Number(el.getAttribute("data-step") || "0");
          el.classList.toggle("is-on", step <= Number(n));
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

    if (wide && typeof Lenis === "function") {
      var lenis = new Lenis({ lerp: 0.085, smoothWheel: true });
      window.__v3lenis = lenis;
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
      gsap.ticker.lagSmoothing(0);
    }

    var ease = "power3.out";
    var phone = frame.querySelector(".v3-phone");
    var copy = frame.querySelector(".v3-copy");
    var display = frame.querySelector(".display");
    var heroExit = frame.querySelectorAll(".eyebrow, .lead, .nj-voice-inline");
    var actions = frame.querySelector(".v3-actions");
    var beatEls = gsap.utils.toArray(frame.querySelectorAll(".v3-beat"));
    var resolve = document.getElementById("v3-resolve");
    var flower = frame.querySelector(".v3-flower");
    var toast = frame.querySelector(".v3-toast");

    setChapter("hero");
    if (phone) gsap.set(phone, { y: wide ? 8 : 20, scale: wide ? 0.98 : 0.94 });
    beatEls.forEach(function (el) { gsap.set(el, { opacity: 0, y: 18 }); });
    if (resolve) gsap.set(resolve, { opacity: 0, y: 14, scale: 0.94 });

    var tl = gsap.timeline({
      defaults: { ease: ease },
      scrollTrigger: {
        trigger: journey,
        start: "top top",
        end: wide ? "+=380%" : "+=300%",
        pin: frame,
        pinSpacing: true,
        scrub: wide ? 0.7 : 0.55,
        anticipatePin: 1,
        onUpdate: function (self) {
          window.__v3st = self;
          if (bar) bar.style.transform = "scaleX(" + self.progress + ")";
        }
      }
    });

    tl.to(display, { scale: wide ? 1.12 : 1.06, opacity: 0, y: -20, duration: 0.9 }, 0.12)
      .to(heroExit, { opacity: 0, y: -8, duration: 0.4 }, 0.12)
      .to(actions, { opacity: 0, duration: 0.35 }, 0.15)
      .add(function () { setChapter("1"); }, 0.4)
      .to(phone, { y: wide ? -12 : -8, scale: wide ? 1.04 : 1.02, duration: 1.1 }, 0.2)
      .to(beatEls[0], { opacity: 1, y: 0, duration: 0.4 }, 1.05)
      .add(function () { if (b1) b1.classList.add("is-on"); }, 1.05)
      .to(beatEls[0], { opacity: 0, y: -14, duration: 0.25 }, 2.05)
      .add(function () { setChapter("2"); }, 2.1)
      .to(beatEls[1], { opacity: 1, y: 0, duration: 0.35 }, 2.15)
      .add(function () { if (b2) b2.classList.add("is-on"); }, 2.2)
      .to(phone, { y: wide ? -4 : 0, scale: 1, duration: 0.6 }, 2.15)
      .to(beatEls[1], { opacity: 0, y: -14, duration: 0.25 }, 3.15)
      .add(function () { setChapter("3"); }, 3.2)
      .to(beatEls[2], { opacity: 1, y: 0, duration: 0.35 }, 3.25)
      .add(function () { if (alertCard) alertCard.classList.add("is-on"); }, 3.3)
      .to(phone, { y: wide ? -16 : -6, scale: wide ? 1.03 : 1.01, duration: 0.55 }, 3.25)
      .to(beatEls[2], { opacity: 0, y: -10, duration: 0.28 }, 3.7)
      .add(function () { setChapter("resolve"); }, 3.75)
      .to(actions, { opacity: 1, duration: 0.4 }, 3.8)
      .to(resolve, { opacity: 1, y: 0, scale: 1, duration: 0.45 }, 3.8)
      .to({}, { duration: 0.7 });
  }
})();
