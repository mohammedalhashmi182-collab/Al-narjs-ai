/* ==========================================================================
   ODSF v0.3 — cinematic scroll layer for the luxury public presentation.

   Responsibility: Lenis smooth-scroll + GSAP ScrollTrigger reveals, applied
   only when the vendor libraries actually loaded and the visitor has not
   asked for reduced motion. Every keystroke is intentional:

   - NEVER toggles classes. Motion is written with inline styles only, so the
     CSS/JS contract (tests/test_css_js_contract.py) is never violated by a
     runtime-created class name.
   - If the vendor files are missing, this file returns early: the storefront
     stays fully static and readable (progressive enhancement).
   ========================================================================== */
(function (window, document) {
  "use strict";

  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var HAS_GSAP = !!(window.gsap && window.ScrollTrigger);
  if (!HAS_GSAP) return;

  gsap.registerPlugin(window.ScrollTrigger);

  /* ---- Lenis smooth wheel pass ---------------------------------------- */
  var lenis = null;
  if (window.Lenis && !REDUCED) {
    var smooth = 0;
    try {
      smooth = parseInt(document.documentElement.getAttribute("data-lux-duration") || "1.15", 10);
    } catch (e) {
      smooth = 1.15;
    }
    lenis = new Lenis({ duration: smooth, smoothWheel: true, touchMultiplier: 1.6 });
    window.lenis = lenis;
    gsap.ticker.add(function (time) {
      lenis.raf(time * 1000);
    });
    gsap.ticker.lagSmoothing(0);
    lenis.on("scroll", ScrollTrigger.update);
  }

  if (REDUCED) return;

  /* ---- hero film-sequence intro (opacity + transform only) ------------- */
  var hero = document.querySelector(".lux-hero");
  if (hero) {
    gsap.timeline({ defaults: { ease: "power2.out" } })
      .fromTo(hero.querySelectorAll(".lux-reveal"),
        { y: 26, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.9, stagger: 0.12 });
  }

  /* ---- scroll-triggered reveals ---------------------------------------- */
  document.querySelectorAll("[data-lux-reveal]").forEach(function (el) {
    gsap.fromTo(el,
      { opacity: 0, y: 18 },
      {
        opacity: 1,
        y: 0,
        duration: 0.8,
        ease: "power2.out",
        scrollTrigger: { trigger: el, start: "top 88%" }
      });
  });

  /* ---- ambient orb drift (transform only) ------------------------------ */
  document.querySelectorAll(".lux-orb[data-drift]").forEach(function (orb) {
    var dx = parseInt(orb.getAttribute("data-drift") || "40", 10) || 40;
    var dy = -Math.min(30, dx >> 1);
    gsap.to(orb, {
      x: dx, y: dy, duration: 14, yoyo: true, repeat: -1, ease: "sine.inOut"
    });
  });
})(window, document);