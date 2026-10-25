/* Al-Narjis site helpers (owner pack items 05, 06, 07).
   - theme toggle (dark default, saved choice only, never automatic)
   - lazy/async images below the hero, IntersectionObserver reveal
   - calm "talk to the CEO" links that scroll to / focus the CEO box
   - newsletter popup: opens only when the API reports storage is ready */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } return null; }

  /* ---- theme ---- */
  function syncTheme() {
    var light = root.getAttribute('data-theme') === 'light';
    var btns = doc.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < btns.length; i++) btns[i].setAttribute('aria-pressed', light ? 'true' : 'false');
  }
  doc.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-theme-toggle]');
    if (!b) return;
    if (root.getAttribute('data-theme') === 'light') { root.removeAttribute('data-theme'); store('nj-theme', 'dark'); }
    else { root.setAttribute('data-theme', 'light'); store('nj-theme', 'light'); }
    syncTheme();
  });
  syncTheme();

  /* ---- images: the hero/LCP image keeps eager loading ---- */
  var imgs = doc.querySelectorAll('img');
  for (var i = 0; i < imgs.length; i++) {
    var im = imgs[i];
    if (!im.hasAttribute('decoding')) im.setAttribute('decoding', 'async');
    if (im.getAttribute('fetchpriority') === 'high' || im.closest('.hero,.nj-nav,header')) continue;
    if (!im.hasAttribute('loading')) im.setAttribute('loading', 'lazy');
  }

  /* ---- reveal: [data-reveal] on pages without the landing's own .rv observer ---- */
  var rv = doc.querySelectorAll('[data-reveal]');
  if (rv.length) {
    if (reduce || !('IntersectionObserver' in window)) {
      for (var r = 0; r < rv.length; r++) rv[r].classList.add('is-in');
    } else {
      root.classList.add('nj-reveal-on');
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
      for (var q = 0; q < rv.length; q++) io.observe(rv[q]);
    }
  }

  /* ---- bot CTA: go to the CEO box, then focus its textarea ---- */
  function focusCeo() {
    var box = doc.getElementById('ceo'), ta = doc.getElementById('ceoProblem');
    if (!box && !ta) return false;
    (box || ta).scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    if (ta) setTimeout(function () { try { ta.focus({ preventScroll: true }); } catch (e) { ta.focus(); } }, reduce ? 0 : 450);
    return true;
  }
  doc.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-bot-cta]');
    if (a && focusCeo()) e.preventDefault();
  });
  if (location.hash === '#ceo') setTimeout(focusCeo, 300);

  /* ---- newsletter popup ---- */
  var nl = doc.getElementById('njNewsletter');
  if (!nl || !window.fetch) return;
  var DAY = 864e5, KEY = 'nj-nl-dismissed', DONE = 'nj-nl-done';
  if (/\/voice(\/|$)/.test(location.pathname) || store(DONE)) return;
  var last = parseInt(store(KEY) || '0', 10);
  if (last && Date.now() - last < 30 * DAY) return;

  var ar = nl.getAttribute('data-lang') === 'ar';
  var form = nl.querySelector('[data-nl-form]'), msg = nl.querySelector('.nj-nl-msg');
  var shown = false, ready = false, prevFocus = null, timer = null;

  function ceoBusy() {
    var box = doc.getElementById('ceo');
    if (!box) return false;
    if (box.contains(doc.activeElement)) return true;
    var r = box.getBoundingClientRect();
    return r.top < window.innerHeight && r.bottom > 0;
  }
  function otherDialogOpen() { return !!doc.querySelector('dialog[open]'); }
  function tryOpen() {
    if (shown || !ready) return;
    if (ceoBusy() || otherDialogOpen()) { clearTimeout(timer); timer = setTimeout(tryOpen, 8000); return; }
    shown = true; prevFocus = doc.activeElement;
    nl.hidden = false; root.classList.add('nj-nl-open');
    var f = nl.querySelector('#njNlEmail'); if (f) f.focus();
    doc.removeEventListener('mouseout', onExit);
  }
  function close() {
    if (nl.hidden) return;
    nl.hidden = true; root.classList.remove('nj-nl-open');
    if (!store(DONE)) store(KEY, String(Date.now()));
    if (prevFocus && prevFocus.focus) prevFocus.focus();
  }
  function onExit(e) { if (!e.relatedTarget && e.clientY <= 0) tryOpen(); }

  nl.addEventListener('click', function (e) { if (e.target.closest('[data-nl-close]')) close(); });
  doc.addEventListener('keydown', function (e) {
    if (nl.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Tab') {
      var f = nl.querySelectorAll('a[href],button,input:not([tabindex="-1"])');
      var first = f[0], lastEl = f[f.length - 1];
      if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); lastEl.focus(); }
      else if (!e.shiftKey && doc.activeElement === lastEl) { e.preventDefault(); first.focus(); }
    }
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var email = form.email.value.trim();
    msg.className = 'nj-nl-msg';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { msg.textContent = ar ? 'اكتب بريداً إلكترونياً صحيحاً.' : 'Enter a valid email address.'; msg.classList.add('is-err'); return; }
    if (!form.consent.checked) { msg.textContent = ar ? 'نحتاج موافقتك على استلام النشرة.' : 'We need your consent to send the newsletter.'; msg.classList.add('is-err'); return; }
    var btn = form.querySelector('button[type=submit]'); btn.disabled = true;
    msg.textContent = ar ? 'جارٍ الإرسال…' : 'Sending…';
    fetch('/api/newsletter/subscribe', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ email: email, consent: true, website: form.website.value, lang: ar ? 'ar' : 'en' })
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (d) { return { ok: res.ok, d: d, st: res.status }; });
    }).then(function (r) {
      btn.disabled = false;
      if (r.ok && r.d && r.d.ok === true) {
        msg.textContent = r.d.message || (ar ? 'تم الاشتراك.' : 'Subscribed.');
        msg.classList.add('is-ok'); store(DONE, '1'); form.reset();
        setTimeout(close, 2500);
      } else {
        msg.textContent = (r.d && r.d.message) || (r.st === 429 ? (ar ? 'محاولات كثيرة، حاول لاحقاً.' : 'Too many attempts, try later.') : (ar ? 'تعذّر الاشتراك الآن، حاول لاحقاً.' : 'Could not subscribe right now, try later.'));
        msg.classList.add('is-err');
      }
    }).catch(function () {
      btn.disabled = false;
      msg.textContent = ar ? 'تعذّر الاتصال، حاول لاحقاً.' : 'Connection failed, try later.'; msg.classList.add('is-err');
    });
  });

  fetch('/api/newsletter/status', { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : { available: false }; })
    .then(function (d) {
      if (!d || d.available !== true) return;  /* fail closed: popup stays hidden */
      ready = true;
      timer = setTimeout(tryOpen, 20000);
      if (window.matchMedia && window.matchMedia('(pointer: fine)').matches) doc.addEventListener('mouseout', onExit);
    })
    .catch(function () {});
})();
