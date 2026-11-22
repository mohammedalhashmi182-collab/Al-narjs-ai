/* Al-Narjis homepage v6 motion ("Pearl Aurora" glass).
   - Lenis smooth scroll, split-word reveals, glass windows rising with depth (GSAP + ScrollTrigger, self-hosted).
   - The hero orb: poster first, then a lazily fetched loop clip (base64 text -> blob URL).
   - Pinned 3D phone story; night band for the agent network; floating rail tracks the chapter.
   - prefers-reduced-motion / Save-Data: html.v5-static, nothing animates. */
(function () {
  'use strict';
  var root = document.documentElement;
  var qs = new URLSearchParams(location.search);
  var CAPTURE = qs.has('capture');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var staticMode = root.classList.contains('v5-static') || reduce;
  var mobile = window.matchMedia('(max-width: 899px)').matches;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  // ——— chrome that works in every mode ———
  var nav = $('#nav');
  var progress = $('#v5-progress');
  function chrome() {
    var y = window.scrollY || 0;
    if (nav) nav.classList.toggle('solid', y > 24);
    if (progress) {
      var max = document.documentElement.scrollHeight - innerHeight;
      progress.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, y / max) : 0) + ')';
    }
  }
  addEventListener('scroll', chrome, { passive: true });
  chrome();

  // floating rail: mark the chapter in view (works in every mode)
  var railLinks = $$('#v6-rail a[data-rail]');
  if (railLinks.length && 'IntersectionObserver' in window) {
    var seen = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { seen[en.target.id] = en.isIntersecting ? en.intersectionRatio : 0; });
      var best = null, bestR = 0;
      railLinks.forEach(function (a) { var r = seen[a.dataset.rail] || 0; if (r > bestR) { bestR = r; best = a; } });
      if (best) railLinks.forEach(function (a) { a.classList.toggle('is-on', a === best); if (a === best) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
    }, { threshold: [0, 0.15, 0.3, 0.5, 0.75], rootMargin: '-35% 0px -35% 0px' });
    railLinks.forEach(function (a) { var el = document.getElementById(a.dataset.rail); if (el) io.observe(el); });
  }

  // how: pill tabs light up their step
  var tabs = $$('[data-step-tab]'), stepEls = $$('[data-step-i]');
  function setStep(i, scroll) {
    tabs.forEach(function (t) { var on = +t.dataset.stepTab === i; t.classList.toggle('is-on', on); t.setAttribute('aria-selected', on ? 'true' : 'false'); });
    stepEls.forEach(function (s) { s.classList.toggle('is-on', +s.dataset.stepI === i); });
    if (scroll && mobile && stepEls[i]) stepEls[i].scrollIntoView({ behavior: staticMode ? 'auto' : 'smooth', block: 'center' });
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { setStep(+t.dataset.stepTab, true); }); });
  setStep(0, false);

  if (staticMode) return;
  if (!window.gsap || !window.ScrollTrigger) { return; }
  var gsap = window.gsap, ST = window.ScrollTrigger;
  gsap.registerPlugin(ST);
  root.classList.add('v5-live');

  // ——— smooth scroll ———
  var lenis = null;
  if (window.Lenis && !CAPTURE) {
    lenis = new window.Lenis({ duration: 1.15, easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); }, smoothWheel: true });
    lenis.on('scroll', ST.update);
    gsap.ticker.add(function (t) { lenis.raf(t * 1000); });
    gsap.ticker.lagSmoothing(0);
    $$('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var id = a.getAttribute('href');
        if (id.length < 2) return;
        var el = document.querySelector(id);
        if (!el) return;
        e.preventDefault();
        // layout can shift while travelling (lazy sections, pin spacers): settle on the real target
        var tries = 0;
        var go = function () {
          lenis.scrollTo(el, { offset: -70, onComplete: function () {
            var top = el.getBoundingClientRect().top;
            if (Math.abs(top - 70) > 12 && ++tries < 3) { ST.refresh(); go(); }
          } });
        };
        go();
      });
    });
  }
  var SCRUB = CAPTURE ? true : 0.8;

  // ——— split words + reveals ———
  $$('[data-split]').forEach(function (el) {
    var walk = function (node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var parts = n.textContent.split(/(\s+)/);
          var frag = document.createDocumentFragment();
          parts.forEach(function (p) {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
            var w = document.createElement('span'); w.className = 'v5-w';
            var i = document.createElement('span'); i.textContent = p; w.appendChild(i); frag.appendChild(w);
          });
          n.parentNode.replaceChild(frag, n);
        } else if (n.nodeType === 1 && !n.classList.contains('v5-grad')) { walk(n); }
        else if (n.nodeType === 1) {
          // keep gradient text intact (background-clip), wrap the whole em
          var w2 = document.createElement('span'); w2.className = 'v5-w';
          n.parentNode.insertBefore(w2, n); var inner = document.createElement('span'); w2.appendChild(inner); inner.appendChild(n);
        }
      });
    };
    walk(el);
    var words = $$('.v5-w > span', el);
    gsap.fromTo(words, { yPercent: 110, rotate: 3 }, {
      yPercent: 0, rotate: 0, duration: 1.1, ease: 'expo.out', stagger: 0.07,
      scrollTrigger: { trigger: el, start: 'top 88%', once: true }
    });
  });
  $$('[data-rise]').forEach(function (el, i) {
    gsap.to(el, { opacity: 1, y: 0, duration: 1, ease: 'expo.out', delay: el.closest('.v5-hero') ? 0.35 + (i % 4) * 0.08 : 0,
      scrollTrigger: { trigger: el, start: 'top 90%', once: true } });
  });


  // hero: frame recedes, floating glass drifts at different depths, orb follows the pointer
  var frame = $('#v6-frame');
  if (frame) gsap.to(frame, { scale: 0.94, yPercent: 4, borderRadius: 56, ease: 'none', scrollTrigger: { trigger: '.v6-hero', start: 'top top', end: 'bottom top', scrub: SCRUB } });
  $$('.v6-float').forEach(function (g, i) {
    gsap.to(g, { yPercent: -40 - i * 35, ease: 'none', scrollTrigger: { trigger: '.v6-hero', start: 'top top', end: 'bottom top', scrub: SCRUB } });
  });
  var orb = $('#v6-orb');
  if (orb) gsap.to(orb, { yPercent: 18, ease: 'none', scrollTrigger: { trigger: '.v6-hero', start: 'top top', end: 'bottom top', scrub: SCRUB } });
  if (!mobile) {
    addEventListener('pointermove', function (e) {
      var x = e.clientX / innerWidth - 0.5, y = e.clientY / innerHeight - 0.5;
      $$('.v6-float').forEach(function (g, i) { gsap.to(g, { x: x * (12 + i * 8), y: y * (10 + i * 6), duration: 1.2, ease: 'power3.out', overwrite: 'auto' }); });
      if (orb) gsap.to(orb, { x: x * -26, rotateY: x * 10, rotateX: -y * 10, duration: 1.4, ease: 'power3.out', overwrite: 'auto' });
    }, { passive: true });
  }
  gsap.to('.v6-hero-copy', { yPercent: -10, opacity: 0.25, ease: 'none', scrollTrigger: { trigger: '.v6-hero', start: '35% top', end: 'bottom top', scrub: SCRUB } });
  // the room drifts slower than the glass
  gsap.to('.v6-bg-photo', { yPercent: -6, ease: 'none', scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: SCRUB } });

  // glass windows rise in with depth
  $$('.v6-window').forEach(function (w) {
    gsap.fromTo(w, { y: 90, scale: 0.96, opacity: 0.4 }, { y: 0, scale: 1, opacity: 1, ease: 'none', scrollTrigger: { trigger: w, start: 'top bottom', end: 'top 55%', scrub: SCRUB } });
  });
  stepEls.forEach(function (s, i) {
    gsap.fromTo(s, { y: 50 + i * 30 }, { y: 0, ease: 'none', scrollTrigger: { trigger: s, start: 'top bottom', end: 'top 50%', scrub: SCRUB } });
    ST.create({ trigger: s, start: 'top 60%', end: 'bottom 40%', onEnter: function () { setStep(i); }, onEnterBack: function () { setStep(i); } });
  });
  $$('.v5-net-card').forEach(function (c, i) {
    gsap.fromTo(c, { y: 60 + (i % 3) * 24 }, { y: 0, ease: 'none', scrollTrigger: { trigger: c, start: 'top bottom', end: 'top 60%', scrub: SCRUB } });
  });
  // ——— story: pinned 3D phone ———
  var phone = $('#v5-phone');
  var pin = $('#v5-story-pin');
  if (phone && pin) {
    var beats = $$('.v5-beat');
    var steps = $$('.v5-thread [data-step]');
    var typing = $('.v5-typing');
    var glare = $('.v5-ph-glare');
    var lastBeat = 0;
    var setBeat = function (n) {
      if (n === lastBeat) return; lastBeat = n;
      beats.forEach(function (b) { b.classList.toggle('is-on', +b.dataset.beat === n); });
      steps.forEach(function (s) {
        var k = +s.dataset.step;
        var on = s === typing ? (n === 2) : (k <= n);
        s.classList.toggle('is-on', on);
      });
      if (typing) {
        typing.classList.toggle('is-done', n !== 2);
        clearTimeout(typing._t);
        if (n === 2) {
          var out = $('.v5-bubble.out'); if (out) out.classList.remove('is-on');
          typing._t = setTimeout(function () { typing.classList.add('is-done'); if (out) out.classList.add('is-on'); }, CAPTURE ? 0 : 650);
          if (CAPTURE) { typing.classList.add('is-done'); if (out) out.classList.add('is-on'); }
        }
      }
    };
    setBeat(1);
    var tl = gsap.timeline({
      scrollTrigger: {
        trigger: pin, start: 'top top', end: mobile ? '+=170%' : '+=230%', pin: true, scrub: SCRUB, anticipatePin: 1,
        onUpdate: function (self) { var p = self.progress; setBeat(p < 0.3 ? 1 : p < 0.64 ? 2 : 3); }
      }
    });
    tl.fromTo(phone, { rotateY: -32, rotateX: 14, rotateZ: 3, y: 40, scale: 0.92 },
                     { rotateY: -6, rotateX: 4, rotateZ: 0, y: 0, scale: 1, ease: 'power2.out', duration: 0.45 })
      .to(phone, { rotateY: 14, rotateX: 6, rotateZ: -2, scale: 1.02, ease: 'sine.inOut', duration: 0.55 });
    if (glare) tl.fromTo(glare, { '--glare': '-60%' }, { '--glare': '70%', ease: 'none', duration: 1 }, 0);
  }


  // ——— the night band ———
  $$('[data-bg]').forEach(function (sec) {
    var key = sec.getAttribute('data-bg');
    var go = function () { root.classList.toggle('v5-ondark', key === 'team'); };
    ST.create({ trigger: sec, start: 'top 55%', end: 'bottom 55%', onEnter: go, onEnterBack: go });
  });
  var afterTeam = $('#ceo-desk');
  if (afterTeam) ST.create({ trigger: afterTeam, start: 'top 55%', onEnter: function () { root.classList.remove('v5-ondark'); } });
  var foot = $('#site-footer');
  if (foot) ST.create({ trigger: foot, start: 'top 70%', onEnter: function () { root.classList.add('v5-ondark'); }, onLeaveBack: function () { root.classList.remove('v5-ondark'); } });

  // ——— the orb clip (lazy, base64 text -> blob; see /static/media/v6-*.b64) ———
  var video = $('#v5-video');
  function loadVideo() {
    if (!video || !orb || !window.fetch || !window.Blob || !window.atob) return;
    var small = mobile || (navigator.connection && /2g|3g/.test(navigator.connection.effectiveType || ''));
    var webm = video.canPlayType('video/webm; codecs="vp9"');
    var ext = webm ? 'webm' : 'mp4';
    var url = video.dataset.src + (orb.dataset.clip || 'orb') + '-' + (small ? 480 : 720) + '.' + ext + '.b64';
    fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (b64) {
      var bin = atob(b64.trim()), n = bin.length, buf = new Uint8Array(n);
      for (var i = 0; i < n; i++) buf[i] = bin.charCodeAt(i);
      video.src = URL.createObjectURL(new Blob([buf], { type: 'video/' + ext }));
      var on = function () { root.classList.add('v6-clip-on'); };
      if (CAPTURE) { video.addEventListener('loadeddata', on, { once: true }); video.load(); }
      else { video.addEventListener('playing', on, { once: true }); var p = video.play(); if (p && p.catch) p.catch(function () {}); }
    }).catch(function () {});
  }
  function startClip() {
    // Phones keep the poster for first paint and fetch the clip on the first touch or scroll.
    if (mobile && !CAPTURE) {
      var evs = ['scroll', 'touchstart', 'pointerdown', 'keydown'];
      var go = function () { evs.forEach(function (ev) { window.removeEventListener(ev, go); }); loadVideo(); };
      evs.forEach(function (ev) { window.addEventListener(ev, go, { passive: true }); });
    } else loadVideo();
  }
  var kick = function () { (window.requestIdleCallback || function (f) { return setTimeout(f, 200); })(startClip, { timeout: 1500 }); };
  if (CAPTURE) startClip();
  else if (document.readyState === 'complete') kick(); else addEventListener('load', kick);
  addEventListener('resize', function () { mobile = window.matchMedia('(max-width: 899px)').matches; });

  // ——— capture hooks: deterministic frames for the review video ———
  if (CAPTURE) {
    gsap.ticker.sleep();
    var seenAnim = new WeakMap();
    window.__v5 = {
      step: function (t) {
        gsap.updateRoot(t);
        ST.update();
        document.getAnimations().forEach(function (a) {
          if (!seenAnim.has(a)) seenAnim.set(a, t);
          try { a.pause(); a.currentTime = (a instanceof CSSTransition ? (t - seenAnim.get(a)) : t) * 1000; } catch (e) {}
        });
        if (video && video.duration) { try { video.pause(); video.currentTime = t % video.duration; } catch (e) {} }
        chrome();
      }
    };
  }
})();
