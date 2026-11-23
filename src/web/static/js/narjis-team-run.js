/*
 * Al-Narjis — live team run panel (homepage).
 *
 * The visitor describes a problem. The AI CEO assigns up to four real agents,
 * and the endpoint streams their work as server-sent events. The stream is read
 * with fetch and a ReadableStream, because the endpoint takes POST. Each agent
 * gets a card; the CEO's combined answer closes the run.
 *
 * Text from the server is only ever written with textContent. A card shows what
 * an event carries and nothing more. The panel stays hidden unless this script runs.
 */
(function () {
  'use strict';

  var section = document.getElementById('teamRun');
  var form = document.getElementById('teamRunForm');
  var field = document.getElementById('teamRunProblem');
  var submit = document.getElementById('teamRunSubmit');
  var count = document.getElementById('teamRunCount');
  var statusBox = document.getElementById('teamRunStatus');
  var cards = document.getElementById('teamRunCards');
  if (!section || !form || !field || !submit || !count || !statusBox || !cards) return;
  if (!window.fetch || !window.TextDecoder) return;

  var LANG = /^en/i.test(document.documentElement.lang || '') ? 'en' : 'ar';
  var AR = LANG === 'ar';
  var MAX_CHARS = 600; // the visitor limit, also the textarea maxlength
  var MIN_CHARS = 8; // mirrors ceo_advisor.MIN_PROBLEM_CHARS
  var MAX_AGENTS = 4; // mirrors ceo_live.MAX_AGENTS

  var T = AR ? {
    empty: 'اكتب مشكلتك أو هدفك أولاً.',
    running: 'يختار الرئيس التنفيذي الوكلاء المناسبين…',
    started: 'بدأ الفريق العمل.',
    queued: 'في الانتظار',
    working: 'يعمل الآن',
    done: 'اكتمل',
    ended: 'انتهى',
    pending: 'جارٍ العمل على جزئه…',
    incomplete: 'لم يكتمل عمل هذا الوكيل',
    finished: 'وصلت الإجابة النهائية من الرئيس التنفيذي.',
    limit: 'استُخدمت التجربة المجانية لهذا اليوم. جرّب مرة أخرى لاحقاً، أو تواصل معنا.',
    unavailable: 'الفريق غير متاح الآن، جرّب لاحقاً أو تواصل معنا.',
    noAgents: 'وضّح طلبك أكثر حتى يعرف الفريق من يشتغل عليه.',
    error: 'تعذّر إكمال التشغيل الآن. حاول مرة أخرى.',
    ceo: 'الرئيس التنفيذي الافتراضي'
  } : {
    empty: 'Describe your problem or goal first.',
    running: 'The AI CEO is choosing the right agents…',
    started: 'The team has started.',
    queued: 'Queued',
    working: 'Working',
    done: 'Done',
    ended: 'Ended',
    pending: 'Working on this part…',
    incomplete: 'This agent did not finish',
    finished: 'The final answer from the AI CEO is ready.',
    limit: "You have used today's free run. Try again later, or contact us.",
    unavailable: 'The team is not available right now. Try again later or contact us.',
    noAgents: 'Describe your request in more detail so the team knows who should work on it.',
    error: 'The run could not be completed. Please try again.',
    ceo: 'Virtual CEO'
  };

  var busy = false;
  var current = null; // the run on screen: { cards: [], finished: false }

  function updateCount() {
    count.textContent = field.value.length + ' / ' + MAX_CHARS;
  }

  function node(tag, className, text) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function clearCards() {
    while (cards.firstChild) cards.removeChild(cards.firstChild);
  }

  function finish(message) {
    if (current) {
      current.finished = true;
      // A stream that ends early must not leave a card pulsing as if it were still working.
      current.cards.forEach(function (card) {
        if (card.state === 'working' || card.state === 'queued') {
          setCard(card, 'ended', T.ended);
          card.body.textContent = T.incomplete;
        }
      });
    }
    if (message) statusBox.textContent = message;
  }

  function fail() {
    if (!current || !current.finished) finish(T.error);
  }

  function setBusy(on) {
    busy = on;
    submit.disabled = on;
    if (on) section.setAttribute('aria-busy', 'true');
    else section.removeAttribute('aria-busy');
  }

  function addCard(slug, name) {
    var article = node('article', 'ntr-card is-queued');
    var head = node('header', 'ntr-card-head');
    var dot = node('span', 'ntr-dot');
    dot.setAttribute('aria-hidden', 'true');
    var title = node('h3', 'ntr-card-name', name);
    var badge = node('span', 'ntr-badge', T.queued);
    var body = node('p', 'ntr-text');
    head.appendChild(dot);
    head.appendChild(title);
    head.appendChild(badge);
    article.appendChild(head);
    article.appendChild(body);
    cards.appendChild(article);
    return { slug: slug, article: article, badge: badge, body: body, state: 'queued' };
  }

  function findCard(slug, name) {
    for (var i = 0; i < current.cards.length; i++) {
      if (current.cards[i].slug === slug) return current.cards[i];
    }
    var card = addCard(slug, name);
    current.cards.push(card);
    return card;
  }

  function setCard(card, state, label) {
    card.state = state;
    card.article.className = 'ntr-card is-' + state;
    card.badge.textContent = label;
  }

  function onTeam(agents) {
    if (!Array.isArray(agents)) return;
    agents.slice(0, MAX_AGENTS).forEach(function (agent) {
      var item = agent || {};
      var slug = String(item.slug || '');
      findCard(slug, String(item.name || slug));
    });
    statusBox.textContent = T.started;
  }

  function onStart(event) {
    var name = String(event.name || event.slug || '');
    var card = findCard(String(event.slug || ''), name);
    setCard(card, 'working', T.working);
    card.body.textContent = T.pending;
    statusBox.textContent = name + ': ' + T.working;
  }

  function onDone(event) {
    var card = findCard(String(event.slug || ''), String(event.name || event.slug || ''));
    var text = String(event.text || '').trim();
    if (text) {
      setCard(card, 'done', T.done);
      card.body.textContent = text;
    } else {
      setCard(card, 'ended', T.ended);
      card.body.textContent = T.incomplete;
    }
  }

  function onFinal(text) {
    var answer = String(text || '').trim();
    if (!answer) {
      finish(T.error);
      return;
    }
    var article = node('article', 'ntr-card is-final');
    var head = node('header', 'ntr-card-head');
    var roleName = section.getAttribute(AR ? 'data-ceo-ar' : 'data-ceo-en') || T.ceo;
    head.appendChild(node('h3', 'ntr-card-name', roleName));
    article.appendChild(head);
    article.appendChild(node('p', 'ntr-text', answer));
    cards.appendChild(article);
    finish(T.finished);
  }

  function onEvent(event) {
    if (!event || typeof event !== 'object') return;
    switch (event.type) {
      case 'team': onTeam(event.agents); break;
      case 'agent_start': onStart(event); break;
      case 'agent_done': onDone(event); break;
      case 'final': onFinal(event.text); break;
      case 'unavailable': finish(T.unavailable); break;
      case 'no_agents': finish(T.noAgents); break;
      case 'error': finish(T.error); break;
      default: break;
    }
  }

  // Reads a text/event-stream body. An event ends at a blank line and may arrive
  // split across chunks, so the buffer is kept until its end shows up.
  function readEvents(response) {
    var decoder = new TextDecoder();
    var buffer = '';

    function emit(block) {
      var lines = [];
      block.split('\n').forEach(function (line) {
        if (line.indexOf('data:') === 0) {
          var value = line.slice(5);
          lines.push(value.charAt(0) === ' ' ? value.slice(1) : value);
        }
      });
      if (!lines.length) return;
      var payload;
      try {
        payload = JSON.parse(lines.join('\n'));
      } catch (err) {
        return;
      }
      onEvent(payload);
    }

    function drain(flushAll) {
      buffer = buffer.replace(/\r\n/g, '\n');
      var end = buffer.indexOf('\n\n');
      while (end !== -1) {
        emit(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        end = buffer.indexOf('\n\n');
      }
      if (flushAll && buffer.trim()) {
        emit(buffer);
        buffer = '';
      }
    }

    if (!response.body || !response.body.getReader) {
      return response.text().then(function (text) {
        buffer = text;
        drain(true);
      });
    }

    var reader = response.body.getReader();
    function pump() {
      return reader.read().then(function (chunk) {
        if (chunk.done) {
          buffer += decoder.decode();
          drain(true);
          return null;
        }
        buffer += decoder.decode(chunk.value, { stream: true });
        drain(false);
        return pump();
      });
    }
    return pump();
  }

  function run(text) {
    var submitHadFocus = document.activeElement === submit;
    setBusy(true);
    clearCards();
    current = { cards: [], finished: false };
    statusBox.textContent = T.running;

    fetch('/api/ceo/team-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      credentials: 'same-origin',
      body: JSON.stringify({ problem: text, lang: LANG })
    }).then(function (response) {
      if (response.status === 429) {
        // Daily free run used: no cards, only the limit message.
        finish(T.limit);
        return null;
      }
      if (!response.ok) throw new Error('http ' + response.status);
      return readEvents(response);
    }).then(function () {
      fail();
    }).catch(function () {
      fail();
    }).then(function () {
      setBusy(false);
      // A disabled button drops focus; give it back so keyboard users keep their place.
      if (submitHadFocus) submit.focus({ preventScroll: true });
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (busy) return;
    var text = field.value.trim();
    if (!text) {
      statusBox.textContent = T.empty;
      field.focus();
      return;
    }
    if (text.length < MIN_CHARS) {
      statusBox.textContent = T.noAgents;
      field.focus();
      return;
    }
    run(text);
  });

  field.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit.click();
    }
  });
  field.addEventListener('input', updateCount);

  updateCount();
  section.hidden = false;
})();
