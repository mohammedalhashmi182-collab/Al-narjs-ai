/* Narjis CEO — adaptive visual blueprint, no paid model calls and no fake live data.
   Uses the existing /api/ceo/consult response, with DOM-safe rendering. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  function node(tag, cls, value) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (value !== undefined && value !== null) el.textContent = String(value);
    return el;
  }
  function svgNode(tag, props, value) {
    var el = document.createElementNS(NS, tag);
    Object.keys(props || {}).forEach(function (key) { el.setAttribute(key, String(props[key])); });
    if (value !== undefined && value !== null) el.textContent = String(value);
    return el;
  }
  function addSvg(svg, tag, props, value) {
    var el = svgNode(tag, props, value);
    svg.appendChild(el);
    return el;
  }
  function agentNames(response, ar) {
    return (Array.isArray(response.agents) ? response.agents : [])
      .filter(function (a) { return a && typeof a === 'object'; })
      .slice(0, 6).map(function (a) {
        return (ar ? a.title_ar : a.title_en) || '';
      }).filter(Boolean);
  }
  function short(value, max) {
    var x = String(value || '').replace(/\s+/g, ' ').trim();
    return x.length > max ? x.slice(0, max - 1) + '…' : x;
  }
  function sectorFor(problem) {
    var value = String(problem || '').toLowerCase();
    if (/عياد|طبي|طبيب|مريض|موعد|حجز|clinic|patient|appointment|medical/.test(value)) return 'clinic';
    if (/متجر|سلة|زد|سلات|منتج|طلبية|shop|store|ecommerce|salla|zid|cart/.test(value)) return 'store';
    if (/عقار|مكتب عقار|property|real estate/.test(value)) return 'property';
    return 'services';
  }
  function scenario(ar, sector) {
    var data = {
      clinic: {
        ar: ['عيادة', 'تجميع الاستفسارات', 'ترتيب الردود', 'مراجعة تسلسل الرد', 'متابعة الرسائل'],
        en: ['Clinic', 'Collect enquiries', 'Draft replies', 'Review responses', 'Follow messages']
      },
      store: {
        ar: ['متجر إلكتروني', 'فهم طلبات الشراء', 'توزيع خدمة المتجر', 'صياغة المتابعات', 'استعادة الفرص'],
        en: ['Online store', 'Identify buying intent', 'Route store support', 'Draft follow-ups', 'Recover opportunities']
      },
      property: {
        ar: ['شركة عقارية', 'فرز استفسارات العقارات', 'توجيه المستشارين', 'ترتيب العروض', 'متابعة المهتمين'],
        en: ['Real estate', 'Qualify enquiries', 'Assign advisors', 'Plan offers', 'Follow interested buyers']
      },
      services: {
        ar: ['شركة خدمات', 'فهم طلب العميل', 'توزيع مهام الفريق', 'إعداد تصور العرض', 'متابعة العملاء'],
        en: ['Services company', 'Understand needs', 'Assign specialists', 'Prepare proposal', 'Follow prospects']
      }
    };
    return data[sector][ar ? 'ar' : 'en'];
  }
  function createBlueprint(ar, sector, response, businessName, problem) {
    var visual = svgNode('svg', {
      xmlns: NS, viewBox: '0 0 1120 372',
      role: 'img', 'aria-labelledby': 'ngSvgTitle ngSvgDesc',
      preserveAspectRatio: 'xMidYMid meet'
    });
    visual.appendChild(svgNode('title', { id: 'ngSvgTitle' }, ar ? 'الرسم المقترح لرحلة عملك مع النرجس' : 'Your proposed workflow with Narjis AI'));
    visual.appendChild(svgNode('desc', { id: 'ngSvgDesc' }, ar ? 'رسم تخطيطي قابل للتنزيل: الطلب، التشخيص، فريق الوكلاء، آلية العمل، المراجعة. لا توجد عمليات مفعلة.' : 'Downloadable workflow illustration. No live integrations are active.'));
    addSvg(visual, 'rect', { x: 0, y: 0, width: 1120, height: 372, rx: 22, fill: '#17191b' });
    for (var x = 12; x < 1120; x += 42) {
      addSvg(visual, 'line', { x1: x, y1: 0, x2: x, y2: 372, stroke: '#34383d', 'stroke-opacity': .20 });
    }
    addSvg(visual, 'text', {
      x: ar ? 1078 : 40, y: 39, fill: '#e5e9ed',
      'font-family': 'IBM Plex Sans Arabic, Segoe UI, sans-serif',
      'font-size': 17, 'font-weight': 700, 'text-anchor': ar ? 'end' : 'start'
    }, short(businessName || (ar ? 'تصور أعمالك مع النرجس' : 'Your Narjis AI blueprint'), 55));
    var labels = ar ? ['الطلب', 'الرئيس التنفيذي', 'الفريق', 'خطة العمل', 'التسليم'] : ['Request', 'AI CEO', 'Team', 'Workflow', 'Review'];
    var texts = scenario(ar, sector);
    var names = agentNames(response, ar);
    var sub = [
      short(problem, 20),
      short(ar ? response.diagnosis_ar : response.diagnosis_en, 22),
      short(names.slice(0, 2).join(' / ') || (ar ? 'فريق متخصص' : 'Specialist team'), 22),
      short(texts[3], 22),
      ar ? 'بعد التفعيل والمراجعة' : 'After activation & review'
    ];
    for (var i = 0; i < 5; i++) {
      var xp = ar ? 899 - i * 220 : 20 + i * 220;
      addSvg(visual, 'rect', {
        x: xp, y: 83, width: 198, height: 225, rx: 14,
        fill: i === 1 ? '#2c3034' : '#24272a',
        stroke: i === 1 ? '#ff5a36' : '#464b50', 'stroke-width': i === 1 ? 2 : 1
      });
      addSvg(visual, 'rect', { x: xp + 17, y: 101, width: 36, height: 30, rx: 6, fill: i === 1 ? '#ff5a36' : '#41464a' });
      addSvg(visual, 'text', {
        x: xp + 35, y: 122, 'text-anchor': 'middle',
        'font-family': 'IBM Plex Sans, sans-serif', 'font-weight': 700,
        'font-size': 14, fill: i === 1 ? '#191a1b' : '#eceff1'
      }, '0' + (i + 1));
      addSvg(visual, 'text', {
        x: ar ? xp + 177 : xp + 18, y: 173, 'text-anchor': ar ? 'end' : 'start',
        'font-family': 'IBM Plex Sans Arabic, Segoe UI, sans-serif',
        'font-size': 18, 'font-weight': 700, fill: '#f1f3f4'
      }, labels[i]);
      addSvg(visual, 'text', {
        x: ar ? xp + 177 : xp + 18, y: 211, 'text-anchor': ar ? 'end' : 'start',
        'font-family': 'IBM Plex Sans Arabic, Segoe UI, sans-serif',
        'font-size': 13, fill: '#cbd1d6'
      }, short(sub[i], 23));
      addSvg(visual, 'path', {
        d: 'M' + (xp + 18) + ' 266H' + (xp + 180),
        stroke: i === 1 ? '#ff5a36' : '#61696d',
        'stroke-width': 2, 'stroke-linecap': 'round'
      });
      if (i < 4) {
        var a = ar ? xp - 11 : xp + 205;
        addSvg(visual, 'path', {
          d: ar
            ? 'M' + a + ' 198 l-8 7 l8 7'
            : 'M' + a + ' 198 l8 7 l-8 7',
          fill: 'none', stroke: '#adb5ba', 'stroke-width': 2
        });
      }
    }
    addSvg(visual, 'text', {
      x: ar ? 1078 : 40, y: 345, 'text-anchor': ar ? 'end' : 'start',
      'font-family': 'IBM Plex Sans Arabic, Segoe UI, sans-serif',
      'font-size': 13, fill: '#ced5da'
    }, ar ? 'تصور توضيحي — لا يمثل نظامًا مفعلًا أو عميلًا حقيقيًا' : 'Illustrative only — no live system or real client data');
    return visual;
  }
  function card(label, description) {
    var item = node('article', 'ng-preview-card');
    item.appendChild(node('strong', '', label));
    item.appendChild(node('small', '', description));
    return item;
  }
  function render(host, response, problem, businessName, ar) {
    if (!host || !response || typeof response !== 'object') return;
    var state = sectorFor(problem);
    var names = agentNames(response, ar);
    function repaint(sector) {
      var descriptions = scenario(ar, sector);
      var wrap = node('section', 'ng-visual-shell');
      var header = node('div', 'ng-workspace-heading');
      var heading = node('div', 'ng-workspace-titles');
      heading.appendChild(node('span', 'ng-kicker', 'NARJIS / AI CEO'));
      heading.appendChild(node('h4', 'ng-preview-title',
        businessName || (ar ? 'مساحة عملك المقترحة' : 'Your proposed workspace')));
      heading.appendChild(node('p', 'ng-preview-note',
        ar ? 'نتيجة مبنية على تشخيص الرئيس التنفيذي، وتصوّر بصري لمراحل التنفيذ قبل بدء الخدمة.'
          : 'Based on the CEO diagnosis. A visual blueprint of the intended delivery before activation.'));
      header.appendChild(heading);
      header.appendChild(node('span', 'ng-preview-badge', ar ? 'تصور مبدئي · غير مفعل' : 'Preview · not activated'));
      wrap.appendChild(header);
      var choices = node('div', 'ng-vertical-tabs');
      choices.setAttribute('role', 'group');
      choices.setAttribute('aria-label', ar ? 'اختر نوع النشاط للمعاينة' : 'Choose a business preview');
      [
        ['clinic', ar ? 'عيادة' : 'Clinic'],
        ['store', ar ? 'متجر' : 'Store'],
        ['services', ar ? 'خدمات' : 'Services'],
        ['property', ar ? 'عقار' : 'Real estate']
      ].forEach(function (option) {
        var button = node('button', 'ng-sector-choice', option[1]);
        button.type = 'button';
        button.setAttribute('aria-pressed', String(option[0] === sector));
        button.addEventListener('click', function () { repaint(option[0]); });
        choices.appendChild(button);
      });
      wrap.appendChild(choices);
      var dashboard = node('div', 'ng-mini-dash');
      var topline = node('div', 'ng-dash-title');
      topline.appendChild(node('span', 'ng-dash-dot'));
      topline.appendChild(node('strong', '', descriptions[0]));
      topline.appendChild(node('span', 'ng-dash-right', ar ? 'نموذج لوحة تشغيل' : 'Workspace concept'));
      dashboard.appendChild(topline);
      var grid = node('div', 'ng-preview-grid');
      [descriptions[1], descriptions[2], descriptions[4]].forEach(function (name) {
        grid.appendChild(card(name, ar ? 'جاهز للتصميم بعد الربط' : 'Available to configure after integration'));
      });
      dashboard.appendChild(grid);
      var bottom = node('div', 'ng-dash-footer');
      bottom.appendChild(node('span', '', ar ? 'نقطة البداية' : 'Starting point'));
      bottom.appendChild(node('span', '', ar ? 'التشخيص ← الفريق ← التنفيذ ← المراجعة' : 'Diagnosis → team → delivery → review'));
      dashboard.appendChild(bottom);
      wrap.appendChild(dashboard);
      var flowHeading = node('div', 'ng-flow-heading');
      flowHeading.appendChild(node('h5', '', ar ? 'صورة مسار العمل المقترح' : 'Illustrated workflow blueprint'));
      var download = node('button', 'ng-download-blueprint', ar ? 'تنزيل الرسم SVG' : 'Download SVG');
      download.type = 'button';
      flowHeading.appendChild(download);
      wrap.appendChild(flowHeading);
      var svgWrap = node('div', 'ng-blueprint-scroll');
      var svg = createBlueprint(ar, sector, response, businessName, problem);
      svgWrap.appendChild(svg);
      wrap.appendChild(svgWrap);
      download.addEventListener('click', function () {
        var copy = svg.cloneNode(true);
        copy.setAttribute('xmlns', NS);
        var blob = new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url; a.download = 'narjis-workflow-preview.svg';
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      });
      var team = node('div', 'ng-preview-team');
      team.appendChild(node('strong', '', ar ? 'الوكلاء الذين رشحهم الرئيس التنفيذي' : 'Agents selected by the AI CEO'));
      var chips = node('div', 'ng-agent-chips');
      (Array.isArray(response.agents) ? response.agents : []).slice(0, 6).forEach(function (agent) {
        if (!agent || typeof agent !== 'object') return;
        var label = (ar ? agent.title_ar : agent.title_en) || '';
        if (!label) return;
        var slug = String(agent.slug || '');
        var link = /^[a-z0-9_-]{1,80}$/.test(slug)
          ? node('a', '', label)
          : node('span', '', label);
        if (link.tagName === 'A') link.href = '/ai-agent/' + encodeURIComponent(slug);
        chips.appendChild(link);
      });
      if (!chips.childElementCount) chips.appendChild(node('span', '', ar ? 'سيتم تحديد الفريق بعد التشخيص' : 'Team selection pending diagnosis'));
      team.appendChild(chips);
      team.appendChild(node('p', 'ng-preview-disclaimer',
        ar ? 'هذا العرض تصوري فقط. تبدأ الوظائف الفعلية بعد اختيار الخدمة وربط الأنظمة اللازمة والموافقة.'
          : 'Illustrative preview. Real functions begin only after service selection, integration and approval.'));
      wrap.appendChild(team);
      host.replaceChildren(wrap);
    }
    repaint(state);
  }
  window.NarjisPreview = { render: render };
})();
