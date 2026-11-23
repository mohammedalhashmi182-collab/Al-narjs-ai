/*
 * Al-Narjis — CEO concierge.
 *
 * The AI CEO greets the visitor in the hero, asks three short questions,
 * then shows an initial offer on the same page (team + plan + price from the
 * real /api/ceo/consult response — nothing here invents a price). After the
 * offer exists, a small docked pill keeps the CEO with the visitor while they
 * scroll and across reloads (sessionStorage) until they close: subscribe or
 * continue on WhatsApp.
 *
 * DOM is built with textContent only (never raw HTML strings), and the visitor's text is
 * never stored server-side by this script.
 */
(function () {
  'use strict';
  var root = document.getElementById('ngConcierge');
  var form = document.getElementById('ngHeroForm');
  var area = document.getElementById('ngHeroProblem');
  var thread = document.getElementById('ngcThread');
  var quick = document.getElementById('ngcQuick');
  if (!root || !form || !area || !thread || !quick) return;

  var AR = document.body.dataset.lang !== 'en';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var WA = root.getAttribute('data-wa-href') || ''; // the public WhatsApp link lives in the template
  var KEY = 'narjis_ceo_concierge_v1';
  var MIN_DIRECT = 20; // free text this long is treated as a full description

  var T = AR ? {
    q2: 'تمام. وش أكثر شي تبي تحلّه الحين؟',
    q3: 'آخر سؤال: تقريباً كم رسالة أو استفسار يوصلك باليوم؟',
    reading: 'الرئيس التنفيذي يجهّز عرضك المبدئي…',
    ready: 'جهّزت لك عرضاً مبدئياً. راجعه، وأنا معك لين تقرر.',
    fail: 'تعذّر الوصول الآن. جرّب مرة ثانية، أو كمّل معي على واتساب.',
    offerTitle: 'عرض مبدئي',
    team: 'الفريق المرشّح',
    plan: 'الباقة المرشّحة',
    perMonth: ' ر.س / شهرياً',
    total: 'الإجمالي: ',
    note: 'عرض مبدئي غير ملزم، مبني على وصفك. نعتمد التفاصيل معك قبل أي تفعيل أو ربط.',
    subscribe: 'اعتمد العرض وابدأ',
    request: 'اطلب الباقة',
    wa: 'كمّل مع الرئيس التنفيذي على واتساب',
    save: 'احفظ العرض',
    restart: 'ابدأ من جديد',
    dock: 'الرئيس التنفيذي · عرضك جاهز',
    dockClose: 'إخفاء',
    waText: function (r) {
      var p = r.plan || {};
      // Name the add-on agents, or the total looks like a wrong plan price.
      var extra = p.addons ? ' (' + num(p.price) + ' ر.س) + ' + p.addons + ' وكيل إضافي (' + num(p.addon_price) + ' ر.س لكل وكيل)' : '';
      return 'السلام عليكم، جهّز لي الرئيس التنفيذي في النرجس عرضاً مبدئياً: باقة ' + (p.name || '') + extra +
        ' — الإجمالي ' + num(p.monthly_price || p.price) + ' ر.س شهرياً. أبغى أكمل.';
    },
    compose: function (a) {
      var s = a.biz || '';
      if (a.pain) s += (s ? '، ' : '') + 'وأحتاج: ' + a.pain;
      if (a.vol) s += '. حجم الاستفسارات تقريباً: ' + a.vol + ' يومياً';
      return s + '.';
    }
  } : {
    q2: 'Got it. What do you most want to fix right now?',
    q3: 'Last one: roughly how many messages or enquiries reach you per day?',
    reading: 'The CEO is preparing your initial offer…',
    ready: 'Here is your initial offer. Review it — I stay with you until you decide.',
    fail: 'Could not reach the CEO right now. Try again, or continue with me on WhatsApp.',
    offerTitle: 'Initial offer',
    team: 'Proposed team',
    plan: 'Recommended plan',
    perMonth: ' SAR / month',
    total: 'Total: ',
    note: 'A non-binding initial offer based on your description. We confirm details with you before any activation.',
    subscribe: 'Approve and start',
    request: 'Request this plan',
    wa: 'Continue with the CEO on WhatsApp',
    save: 'Save the offer',
    restart: 'Start over',
    dock: 'AI CEO · your offer is ready',
    dockClose: 'Hide',
    waText: function (r) {
      var p = r.plan || {};
      var extra = p.addons ? ' (SAR ' + num(p.price) + ') + ' + p.addons + ' add-on agent' + (p.addons === 1 ? '' : 's') + ' (SAR ' + num(p.addon_price) + ' each)' : '';
      return 'Hello, the Al-Narjis AI CEO prepared an initial offer for me: the ' + (p.name_en || '') + ' plan' + extra +
        ', total SAR ' + num(p.monthly_price || p.price) + '/month. I would like to continue.';
    },
    compose: function (a) {
      var s = a.biz || '';
      if (a.pain) s += (s ? ', and I need: ' : 'I need: ') + a.pain;
      if (a.vol) s += '. Roughly ' + a.vol + ' enquiries per day';
      return s + '.';
    }
  };

  var STEPS = AR ? [
    null,
    ['الرد على واتساب يتأخر ونخسر عملاء', 'العملاء يسألون وما يكملون الشراء', 'متابعة عروض الأسعار والعملاء المحتملين', 'محتوى وتسويق منتظم', 'تقارير وأرقام واضحة لقراراتي'],
    ['أقل من 20', 'من 20 إلى 100', 'أكثر من 100', 'ما أدري بالضبط']
  ] : [
    null,
    ['WhatsApp replies are slow and we lose customers', 'Customers ask but do not buy', 'Following up quotes and leads', 'Regular content and marketing', 'Clear reports and numbers'],
    ['Under 20', '20 to 100', 'Over 100', 'Not sure']
  ];

  var state = load() || { step: 0, answers: {}, log: [], result: null, closed: false, dockHidden: false };

  function num(v) { var n = Number(v); return isFinite(n) ? n.toLocaleString('en') : String(v || ''); }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
  function load() { try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }
  function scrollThread() { thread.scrollTop = thread.scrollHeight; }

  function bubble(who, text, record) {
    var m = el('div', 'ngc-msg ' + (who === 'me' ? 'me' : 'ceo'));
    m.appendChild(el('p', null, text));
    thread.appendChild(m);
    if (record !== false) { state.log.push([who, text]); save(); }
    scrollThread();
    return m;
  }

  function setQuick(options) {
    quick.replaceChildren();
    (options || []).forEach(function (label) {
      var b = el('button', 'ngc-chip', label);
      b.type = 'button';
      b.addEventListener('click', function () { answer(label); });
      quick.appendChild(b);
    });
    quick.hidden = !options || !options.length;
  }

  function bindFirstStepChips() {
    quick.querySelectorAll('[data-ng-example]').forEach(function (b) {
      b.addEventListener('click', function () { answer(b.getAttribute('data-ng-example') || b.textContent, b.textContent); });
    });
  }

  function answer(value, shown) {
    value = String(value || '').trim();
    if (!value || state.busy) return;
    bubble('me', shown || value);
    if (state.step === 0) state.answers.biz = value;
    else if (state.step === 1) state.answers.pain = value;
    else state.answers.vol = value;
    state.step += 1;
    save();
    if (state.step === 1) { bubble('ceo', T.q2); setQuick(STEPS[1]); }
    else if (state.step === 2) { bubble('ceo', T.q3); setQuick(STEPS[2]); }
    else consult(T.compose(state.answers));
  }

  function consult(problem) {
    state.busy = true; setQuick([]);
    var wait = bubble('ceo', T.reading, false); wait.classList.add('is-typing');
    form.setAttribute('aria-busy', 'true');
    var target = document.getElementById('ceoProblem');
    if (target) target.value = problem; // keeps the full diagnosis section in sync
    fetch('/api/ceo/consult', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem: problem, lang: AR ? 'ar' : 'en' })
    }).then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
      .then(function (r) {
        wait.remove();
        state.result = r; state.step = 3; save();
        bubble('ceo', T.ready);
        offer(r);
        if (window.NarjisCEO && window.NarjisCEO.render) {
          try { window.NarjisCEO.render(r, { quiet: true }); } catch (e) {}
        }
      })
      .catch(function () { wait.remove(); bubble('ceo', T.fail, false); setQuick(state.step < 3 ? STEPS[Math.min(state.step, 2)] : []); })
      .finally(function () { state.busy = false; form.removeAttribute('aria-busy'); save(); });
  }

  function waHref(r) { return WA ? WA + '?text=' + encodeURIComponent(T.waText(r)) : ''; }

  function offer(r) {
    var p = r.plan || {};
    var card = el('section', 'ngc-offer');
    card.setAttribute('aria-label', T.offerTitle);
    var head = el('header', 'ngc-offer-head');
    head.appendChild(el('span', 'ngc-offer-kicker', T.offerTitle));
    head.appendChild(el('p', 'ngc-offer-diag', AR ? r.diagnosis_ar : r.diagnosis_en));
    card.appendChild(head);

    if (r.offer !== false) {
      card.appendChild(el('b', 'ngc-offer-label', T.team));
      var ul = el('ul', 'ngc-offer-team');
      (r.agents || []).slice(0, 6).forEach(function (a) {
        var li = el('li');
        li.appendChild(el('span', 'no', a.no));
        var t = el('span');
        t.appendChild(el('b', null, AR ? a.title_ar : a.title_en));
        t.appendChild(el('small', null, AR ? a.why_ar : a.why_en));
        li.appendChild(t); ul.appendChild(li);
      });
      card.appendChild(ul);

      var plan = el('div', 'ngc-offer-plan');
      var l = el('div'); l.appendChild(el('small', null, T.plan)); l.appendChild(el('strong', null, AR ? p.name : p.name_en));
      var rgt = el('div', 'ngc-offer-price');
      rgt.appendChild(el('strong', null, num(p.monthly_price || p.price) + T.perMonth));
      if (p.total_sar) rgt.appendChild(el('small', null, T.total + p.total_sar));
      plan.appendChild(l); plan.appendChild(rgt);
      card.appendChild(plan);
    }
    card.appendChild(el('p', 'ngc-offer-note', T.note));

    var acts = el('div', 'ngc-offer-actions');
    var closedPay = r.offer === false || r.notice === 'payments_closed';
    var sub = el('a', 'btn ngc-primary', closedPay ? T.request : T.subscribe);
    sub.href = closedPay ? '/consult' : ((r.cta && r.cta.subscribe) || '/portal');
    sub.addEventListener('click', close);
    acts.appendChild(sub);
    var w = waHref(r);
    if (w) {
      var wa = el('a', 'btn-sec ngc-wa', T.wa);
      wa.href = w; wa.target = '_blank'; wa.rel = 'noopener noreferrer';
      wa.addEventListener('click', close);
      acts.appendChild(wa);
    }
    var sv = el('button', 'ngc-link', T.save); sv.type = 'button';
    sv.addEventListener('click', function () {
      card.classList.add('ngc-print'); document.body.classList.add('ngc-printing');
      var done = function () { card.classList.remove('ngc-print'); document.body.classList.remove('ngc-printing'); window.removeEventListener('afterprint', done); };
      window.addEventListener('afterprint', done);
      window.print();
    });
    acts.appendChild(sv);
    var rs = el('button', 'ngc-link', T.restart); rs.type = 'button';
    rs.addEventListener('click', restart);
    acts.appendChild(rs);
    card.appendChild(acts);

    thread.appendChild(card);
    scrollThread();
    dock();
  }

  function close() { state.closed = true; save(); var d = document.getElementById('ngcDock'); if (d) d.hidden = true; }

  function restart() {
    try { sessionStorage.removeItem(KEY); } catch (e) {}
    state = { step: 0, answers: {}, log: [], result: null, closed: false, dockHidden: false };
    thread.querySelectorAll('.ngc-msg:not([data-static]), .ngc-offer').forEach(function (n) { n.remove(); });
    quick.replaceChildren.apply(quick, firstChips);
    quick.hidden = false;
    var d = document.getElementById('ngcDock'); if (d) d.hidden = true;
    area.focus();
  }

  // Docked CEO: appears once an offer exists and the hero is out of view.
  function dock() {
    if (state.closed || state.dockHidden || !state.result) return;
    var d = document.getElementById('ngcDock');
    if (!d) {
      d = el('div', 'ngc-dock'); d.id = 'ngcDock'; d.hidden = true;
      var open = el('button', 'ngc-dock-open'); open.type = 'button';
      var img = document.createElement('img'); img.src = '/static/logo.svg'; img.alt = ''; img.width = 28; img.height = 28;
      open.appendChild(img); open.appendChild(el('span', null, T.dock));
      open.addEventListener('click', function () { root.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' }); });
      var x = el('button', 'ngc-dock-x', '×'); x.type = 'button'; x.setAttribute('aria-label', T.dockClose);
      x.addEventListener('click', function () { state.dockHidden = true; save(); d.hidden = true; });
      d.appendChild(open); d.appendChild(x);
      document.body.appendChild(d);
    }
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { d.hidden = state.closed || state.dockHidden || e.isIntersecting; });
      }, { threshold: 0.15 }).observe(root);
    } else { d.hidden = false; }
  }

  // Composer: free text answers the current step; a full description goes straight to the CEO.
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = (area.value || '').trim();
    if (!text || state.busy) { area.focus(); return; }
    area.value = '';
    if (state.step >= 3 || text.length >= MIN_DIRECT) {
      bubble('me', text);
      state.step = Math.max(state.step, 2);
      consult(state.step >= 3 && state.answers.biz ? T.compose(state.answers) + ' ' + text : text);
      return;
    }
    answer(text);
  });
  area.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (form.requestSubmit) form.requestSubmit(); else form.dispatchEvent(new Event('submit', { cancelable: true })); }
  });

  var firstChips = Array.prototype.slice.call(quick.children);
  bindFirstStepChips();

  // Restore an in-progress conversation (same tab, until the visitor closes).
  if (state.log && state.log.length) {
    state.log.forEach(function (m) { bubble(m[0], m[1], false); });
    if (state.result) offer(state.result);
    else if (state.step === 1) setQuick(STEPS[1]);
    else if (state.step === 2) setQuick(STEPS[2]);
  }
  state.busy = false;
})();
