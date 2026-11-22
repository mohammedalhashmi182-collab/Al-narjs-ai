/* Al-Narjis self-serve landing: billing toggle and live demo (checkout is the portal).
   Credits are never counted here; the daily try counter below is a courtesy
   hint only. The real limit is enforced on the server. */
(function () {
  'use strict';
  var AR = document.body.dataset.lang !== 'en';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var period = 'monthly';

  // ---- billing toggle
  var toggles = document.querySelectorAll('.sx-toggle [data-period]');
  function setPeriod(p) {
    period = p;
    toggles.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.period === p ? 'true' : 'false'); });
    document.querySelectorAll('.sx-plan').forEach(function (card) {
      var price = card.querySelector('.sx-price b');
      var billed = card.querySelector('.sx-billed');
      if (price && price.dataset[p]) price.textContent = price.dataset[p];
      if (billed && billed.dataset[p]) billed.textContent = billed.dataset[p];
      var usd = card.querySelector('.sx-usd');
      if (usd && usd.dataset[p]) usd.textContent = usd.dataset[p];
      var link = card.querySelector('a[data-href-monthly]');
      if (link) link.setAttribute('href', p === 'annual' ? link.dataset.hrefAnnual : link.dataset.hrefMonthly);
    });
  }
  toggles.forEach(function (b) { b.addEventListener('click', function () { setPeriod(b.dataset.period); }); });

  // ---- live demo
  var form = document.getElementById('demoForm');
  if (!form) return;
  var mode = 'product';
  var tabs = document.querySelectorAll('.sx-tabs [data-mode]');
  var nameEl = document.getElementById('demoName');
  var detailsEl = document.getElementById('demoDetails');
  var out = document.getElementById('demoOut');
  var msg = document.getElementById('demoMsg');
  var btn = document.getElementById('demoBtn');
  var copy = document.getElementById('demoCopy');
  var left = document.getElementById('demoLeft');
  var KEY = 'narjis_demo_' + new Date().toISOString().slice(0, 10);
  var PER_DAY = 3;

  function used() { try { return parseInt(localStorage.getItem(KEY) || '0', 10) || 0; } catch (e) { return 0; } }
  function bump() { try { localStorage.setItem(KEY, String(used() + 1)); } catch (e) {} }
  function showLeft() { left.textContent = left.dataset.template.replace('{n}', String(Math.max(0, PER_DAY - used()))); }
  showLeft();

  function setMode(m) {
    mode = m;
    tabs.forEach(function (t) { t.setAttribute('aria-selected', t.dataset.mode === m ? 'true' : 'false'); });
    [nameEl, detailsEl].forEach(function (el) {
      var lab = form.querySelector('label[for="' + el.id + '"]');
      lab.textContent = lab.dataset['label' + (m === 'product' ? 'Product' : 'Reply')];
      el.value = el.dataset['sample' + (m === 'product' ? 'Product' : 'Reply')];
    });
  }
  tabs.forEach(function (t) {
    t.addEventListener('click', function () { setMode(t.dataset.mode); });
    t.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var next = mode === 'product' ? 'reply' : 'product';
      setMode(next); document.querySelector('.sx-tabs [data-mode="' + next + '"]').focus();
    });
  });

  function type(text) {
    if (reduce) { out.textContent = text; return; }
    out.textContent = '';
    var i = 0;
    (function step() {
      i = Math.min(text.length, i + 3);
      out.textContent = text.slice(0, i);
      if (i < text.length) window.requestAnimationFrame(step);
    })();
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    msg.hidden = true;
    if (used() >= PER_DAY) { msg.textContent = msg.dataset.limit; msg.hidden = false; return; }
    var label = btn.textContent;
    btn.disabled = true; btn.textContent = btn.dataset.busy;
    fetch('/api/demo/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: mode, name: nameEl.value, details: detailsEl.value, lang: AR ? 'ar' : 'en' })
    }).then(function (r) {
      if (r.status === 429) throw new Error('limit');
      if (!r.ok) throw new Error('http');
      return r.json();
    }).then(function (data) {
      bump(); showLeft();
      type(String(data.text || ''));
      copy.hidden = false;
    }).catch(function (err) {
      msg.textContent = err && err.message === 'limit' ? msg.dataset.limit : msg.dataset.error;
      msg.hidden = false;
    }).finally(function () { btn.disabled = false; btn.textContent = label; });
  });

  copy.addEventListener('click', function () {
    var label = copy.textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(out.textContent).then(function () {
      copy.textContent = copy.dataset.done; setTimeout(function () { copy.textContent = label; }, 1500);
    }).catch(function () {});
  });
})();
