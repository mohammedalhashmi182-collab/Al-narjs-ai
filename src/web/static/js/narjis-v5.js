/* Al-Narjis homepage v5 motion.
   - One dominant liquid object (raw WebGL raymarch, ~no dependencies) that
     travels between chapter anchors and morphs with scroll.
   - GSAP + ScrollTrigger (self-hosted) for reveals, the pinned phone story,
     the flowing step line and the background colour shift; Lenis smooth scroll.
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
        lenis.scrollTo(el, { offset: -70 });
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

  // hero glass cards: parallax on scroll + pointer
  $$('.v5-glass').forEach(function (g, i) {
    gsap.to(g, { yPercent: -60 - i * 30, ease: 'none', scrollTrigger: { trigger: '.v5-hero', start: 'top top', end: 'bottom top', scrub: SCRUB } });
  });
  var stage = $('#v5-hero-stage');
  if (stage && !mobile) {
    addEventListener('pointermove', function (e) {
      var x = e.clientX / innerWidth - 0.5, y = e.clientY / innerHeight - 0.5;
      $$('.v5-glass', stage).forEach(function (g, i) {
        gsap.to(g, { x: x * (14 + i * 8), y: y * (10 + i * 6), duration: 1.2, ease: 'power3.out', overwrite: 'auto' });
      });
    }, { passive: true });
  }
  gsap.to('.v5-hero-copy', { yPercent: -12, opacity: 0.2, ease: 'none', scrollTrigger: { trigger: '.v5-hero', start: '30% top', end: 'bottom top', scrub: SCRUB } });

  // marquee: scroll-linked
  var mq = $('#v5-marquee');
  if (mq) {
    var dir = document.dir === 'rtl' ? 1 : -1;
    gsap.fromTo(mq, { xPercent: dir * -8 }, { xPercent: dir * 22, ease: 'none', scrollTrigger: { trigger: '.v5-marquee', start: 'top bottom', end: 'bottom top', scrub: SCRUB } });
  }

  // flowing step line
  var flow = $('.v5-flow-line');
  if (flow && flow.getTotalLength) {
    var len = flow.getTotalLength();
    flow.style.strokeDasharray = len; flow.style.strokeDashoffset = len;
    gsap.to(flow, { strokeDashoffset: 0, ease: 'none', scrollTrigger: { trigger: '.v5-steps-wrap', start: 'top 75%', end: 'bottom 60%', scrub: SCRUB } });
  }
  var sw = $('.v5-steps-wrap');
  if (sw && mobile) {
    gsap.fromTo(sw, { '--flow': 0 }, { '--flow': 1, ease: 'none', scrollTrigger: { trigger: sw, start: 'top 70%', end: 'bottom 70%', scrub: SCRUB } });
  }
  $$('.v5-step').forEach(function (s, i) {
    gsap.fromTo(s, { y: 80 + i * 30 }, { y: 0, ease: 'none', scrollTrigger: { trigger: s, start: 'top bottom', end: 'top 45%', scrub: SCRUB } });
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

  // ——— background colour shift + dark band ———
  var bg = $('#v5-bg');
  var palette = {
    hero:  { base: '#F7F3EE', g1: 'rgba(255,171,61,0.30)', g2: 'rgba(229,38,43,0.12)' },
    how:   { base: '#FBF1E8', g1: 'rgba(255,90,31,0.18)', g2: 'rgba(255,171,61,0.26)' },
    story: { base: '#F5ECE6', g1: 'rgba(229,38,43,0.14)', g2: 'rgba(255,171,61,0.22)' },
    team:  { base: '#17120E', g1: 'rgba(255,90,31,0.20)', g2: 'rgba(229,38,43,0.16)' },
    desk:  { base: '#F7F3EE', g1: 'rgba(255,171,61,0.24)', g2: 'rgba(229,38,43,0.10)' }
  };
  var bgState = { base: palette.hero.base, g1: palette.hero.g1, g2: palette.hero.g2 };
  var paintBg = function () { if (!bg) return; bg.style.setProperty('--base', bgState.base); bg.style.setProperty('--g1', bgState.g1); bg.style.setProperty('--g2', bgState.g2); };
  $$('[data-bg]').forEach(function (sec) {
    var key = sec.getAttribute('data-bg');
    var go = function () {
      var c = palette[key]; if (!c) return;
      gsap.to(bgState, { base: c.base, g1: c.g1, g2: c.g2, duration: 0.9, ease: 'power2.out', onUpdate: paintBg, overwrite: true });
      root.classList.toggle('v5-ondark', key === 'team');
    };
    ST.create({ trigger: sec, start: 'top 55%', end: 'bottom 55%', onEnter: go, onEnterBack: go });
  });
  var lastLegacy = $('#results');
  if (lastLegacy) ST.create({ trigger: lastLegacy, start: 'top 55%', onEnter: function () { root.classList.remove('v5-ondark'); } });

  // ——— the liquid object ———
  var anchors = $$('[data-anchor]');
  var canvas = $('#v5-liquid');
  var fallback = $('#v5-blob-fallback');
  var state = { x: innerWidth * 0.3, y: innerHeight * 0.5, r: 200, morph: 0, alpha: 1, hero: 1 };
  var video = $('#v5-video'), videoOn = false, orbitArt = $('.v5-orbit-art');
  var smooth = { x: state.x, y: state.y, r: state.r, morph: 0 };
  var ease = function (t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  function measure() {
    var mid = innerHeight * 0.5;
    var rects = anchors.map(function (a) {
      var r = a.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2, r: r.width / 2, m: parseFloat(a.dataset.morph || '0') };
    });
    var A = rects[0], B = rects[0], t = 0;
    if (rects.length) {
      if (mid <= rects[0].y) { A = B = rects[0]; }
      else if (mid >= rects[rects.length - 1].y) { A = B = rects[rects.length - 1]; }
      else {
        for (var i = 0; i < rects.length - 1; i++) {
          if (mid >= rects[i].y && mid < rects[i + 1].y) { A = rects[i]; B = rects[i + 1]; t = (mid - A.y) / Math.max(1, B.y - A.y); break; }
        }
      }
    }
    var e = ease(Math.max(0, Math.min(1, t)));
    state.hero = rects.length ? (mid <= rects[0].y ? 1 : (A === rects[0] && B !== A ? Math.max(0, 1 - t / 0.28) : 0)) : 0;
    state.x = A.x + (B.x - A.x) * e;
    state.y = A.y + (B.y - A.y) * e;
    // swell mid-flight like a drop in motion
    state.r = (A.r + (B.r - A.r) * e) * (1 + Math.sin(Math.PI * e) * 0.12);
    state.morph = A.m + (B.m - A.m) * e;
    var last = rects[rects.length - 1];
    state.alpha = last ? Math.max(0, Math.min(1, 1 - (mid - last.y - innerHeight * 0.6) / (innerHeight * 0.5))) : 1;
  }

  var gl = null, prog = null, uni = {}, glOk = false;
  var MODE = qs.get('liquid') === 'gl' ? 'gl' : 'img';
  var sculpt = $('#v5-sculpt');
  var layers = sculpt ? { a: $('.s-a', sculpt), b: $('.s-b', sculpt), c: $('.s-c', sculpt) } : null;
  var vel = 0, lastY = window.scrollY || 0, tilt = 0;
  function drawSculpt() {
    var y = window.scrollY || 0;
    vel += ((y - lastY) - vel) * 0.2; lastY = y;
    tilt += (Math.max(-18, Math.min(18, vel * 0.35)) - tilt) * 0.12;
    var m = smooth.morph;
    // A (hero swirl) -> C (story) -> B (splash) as the object travels.
    var wa = Math.max(0, 1 - m / 0.45), wb = Math.max(0, Math.min(1, (m - 0.5) / 0.45)), wc = Math.max(0, 1 - wa - wb);
    var d = smooth.r * 2.25;
    var breath = 1 + Math.sin(clock * 1.3) * 0.015;
    sculpt.style.width = d + 'px'; sculpt.style.height = d + 'px';
    sculpt.style.transform = 'translate3d(' + (smooth.x - d / 2) + 'px,' + (smooth.y - d / 2) + 'px,0) perspective(900px) rotateX(' + (tilt * 0.8) + 'deg) rotateY(' + (Math.sin(clock * 0.35) * 8) + 'deg) scale(' + breath + ')';
    sculpt.style.opacity = state.alpha * (1 - state.hero);
    if (videoOn) video.style.opacity = state.hero;
    var spin = y * 0.045 + clock * 4;
    if (orbitArt) { orbitArt.style.opacity = videoOn ? 0 : state.hero; if (!videoOn) orbitArt.style.transform = 'rotate(' + spin + 'deg)'; }
    layers.a.style.opacity = wa; layers.b.style.opacity = wb; layers.c.style.opacity = wc;
    layers.a.style.transform = 'rotate(' + spin + 'deg)';
    layers.c.style.transform = 'rotate(' + (spin * 0.8 - 20) + 'deg) scale(1.04)';
    layers.b.style.transform = 'rotate(' + (-spin * 0.6 + 10) + 'deg) scale(' + (1.08 + 0.04 * Math.sin(clock)) + ')';
  }
  function isSoftware(g) {
    try {
      var ext = g.getExtension('WEBGL_debug_renderer_info');
      var name = ext ? g.getParameter(ext.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER);
      return /swiftshader|llvmpipe|software|basic render/i.test(String(name));
    } catch (e) { return false; }
  }
  var VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  var FS = [
    'precision highp float;',
    'uniform vec2 uRes;uniform vec2 uC;uniform float uR,uT,uM,uRot,uA,uPx;',
    'mat2 r2(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}',
    'float smin(float a,float b,float k){float h=clamp(.5+.5*(b-a)/k,0.,1.);return mix(b,a,h)-k*h*(1.-h);}',
    'float map(vec3 p){',
    ' float t=uT*.5;',
    ' p.yz*=r2(.55+uRot*.35);p.xz*=r2(uRot+t*.18);p.xy*=r2(-.35+uRot*.2);',
    ' vec3 q=p;q.xz*=r2(q.y*.9*sin(t*.4+uRot));',
    ' float ring=length(vec2(length(q.xz)-.86,q.y*(1.+.25*sin(atan(q.z,q.x)*2.+t))))-(.31+.07*sin(atan(q.z,q.x)*3.-t*1.2));',
    ' float ball=length(p)-.98;',
    ' float m=clamp(uM*.7,0.,1.);',
    ' float d=mix(ring,ball,m);',
    ' d+=(.035+.03*uM)*sin(3.1*p.x+t*1.3)*sin(2.7*p.y-t)*sin(2.9*p.z+t*.7);',
    ' vec3 c1=p-vec3(1.18*cos(t*.7+1.),.75*sin(t*.55),.45*sin(t*.8));',
    ' d=smin(d,length(c1)-(.15+.11*m),.32);',
    ' vec3 c2=p-vec3(-1.05*cos(t*.43),-.95+.15*sin(t*.9),.5*cos(t*.5+2.));',
    ' d=smin(d,length(c2)-(.11+.13*m),.28);',
    ' return d;}',
    'vec3 nrm(vec3 p){vec2 e=vec2(.002,-.002);return normalize(e.xyy*map(p+e.xyy)+e.yyx*map(p+e.yyx)+e.yxy*map(p+e.yxy)+e.xxx*map(p+e.xxx));}',
    'vec3 env(vec3 r){',
    ' vec3 c=mix(vec3(.95,.42,.24),vec3(1.,.95,.9),smoothstep(-.4,.75,r.y));',
    ' float box=smoothstep(.55,.62,r.y)*smoothstep(.55,.35,abs(r.x+.15))*smoothstep(-.2,.3,r.z);',
    ' c+=3.2*box;',
    ' c+=2.2*smoothstep(.06,.0,abs(r.x-.72))*smoothstep(-.5,.4,r.y)*step(0.,r.z);',
    ' c+=1.2*smoothstep(.05,.0,abs(r.x+.85))*smoothstep(-.3,.5,r.y);',
    ' c+=vec3(1.,.5,.2)*.9*smoothstep(-.5,-.85,r.y);',
    ' return c;}',
    'void main(){',
    ' vec2 uv=(gl_FragCoord.xy-uC)/uR*.78;',
    ' if(length(uv)>1.3){gl_FragColor=vec4(0.);return;}',
    ' vec3 ro=vec3(0.,0.,4.3),rd=normalize(vec3(uv,-2.9));',
    ' float t=2.4,md=1e3,d;bool hit=false;',
    ' for(int i=0;i<72;i++){vec3 p=ro+rd*t;d=map(p);md=min(md,d);if(d<.0012){hit=true;break;}t+=d*.85;if(t>6.5)break;}',
    ' float px=1.4/uR;',
    ' float a=hit?1.:1.-smoothstep(0.,px,md);',
    ' if(a<=0.){gl_FragColor=vec4(0.);return;}',
    ' vec3 p=ro+rd*t;vec3 n=nrm(p);vec3 v=-rd;',
    ' float ndv=max(dot(n,v),0.);',
    ' float fr=.05+.95*pow(1.-ndv,4.);',
    ' vec3 L=normalize(vec3(-.55,.8,.55));',
    ' float wrap=clamp(dot(n,L)*.5+.5,0.,1.);',
    ' float ao=clamp(.5+.5*map(p+n*.25)/.25,0.,1.);',
    ' vec3 deep=vec3(.42,.02,.05),red=vec3(.86,.07,.1),org=vec3(1.,.33,.07),amb=vec3(1.,.66,.2);',
    ' float k=clamp(dot(n,normalize(vec3(-.35,.9,.3)))*.5+.5,0.,1.);',
    ' vec3 base=mix(red,org,smoothstep(.35,.7,k));base=mix(base,amb,smoothstep(.72,.97,k));',
    ' base=mix(deep,base,smoothstep(.05,.55,wrap));',
    ' vec3 col=base*(.3+.85*wrap)*(.55+.45*ao);',
    ' col+=vec3(1.,.38,.12)*pow(1.-ndv,2.)*.35;',
    ' vec3 r=reflect(rd,n);',
    ' col=mix(col,env(r)*mix(vec3(1.),base*1.6,.25),fr*.9);',
    ' col+=env(r)*.07*ao;',
    ' col+=vec3(1.)*pow(max(dot(r,L),0.),180.)*2.2;',
    ' col=col/(1.+col*.12);',
    ' gl_FragColor=vec4(col*a*uA,a*uA);}'
  ].join('\n');

  function initGL() {
    if (!canvas) return false;
    try {
      gl = canvas.getContext('webgl', { premultipliedAlpha: true, antialias: false, alpha: true, powerPreference: 'high-performance' });
    } catch (e) { gl = null; }
    if (!gl) return false;
    if (isSoftware(gl) && qs.get('gl') !== 'force') { gl = null; return false; }
    var sh = function (type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { throw new Error(gl.getShaderInfoLog(s)); } return s; };
    try {
      prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error('link');
    } catch (e) { if (window.console) console.warn('v5 liquid', e); gl = null; return false; }
    gl.useProgram(prog);
    var buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    ['uRes', 'uC', 'uR', 'uT', 'uM', 'uRot', 'uA', 'uPx'].forEach(function (n) { uni[n] = gl.getUniformLocation(prog, n); });
    gl.clearColor(0, 0, 0, 0);
    return true;
  }
  var scale = 1;
  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    scale = dpr * (mobile ? 0.6 : 0.8);
    if (CAPTURE) scale = Math.min(dpr, 1);
    if (canvas) { canvas.width = Math.round(innerWidth * scale); canvas.height = Math.round(innerHeight * scale); }
    if (gl) gl.viewport(0, 0, canvas.width, canvas.height);
  }
  var t0 = performance.now(), clock = 0, visible = true;
  document.addEventListener('visibilitychange', function () { visible = !document.hidden; });
  function frame(now, forced) {
    if (!forced) clock = (now - t0) / 1000;
    measure();
    var k = forced ? 1 : 0.14;
    smooth.x += (state.x - smooth.x) * k; smooth.y += (state.y - smooth.y) * k;
    smooth.r += (state.r - smooth.r) * k; smooth.morph += (state.morph - smooth.morph) * k;
    var on = state.alpha > 0.01 && smooth.y + smooth.r * 2 > 0 && smooth.y - smooth.r * 2 < innerHeight;
    if (MODE === 'img' && sculpt) {
      if (on) drawSculpt();
    } else if (glOk && gl) {
      gl.clear(gl.COLOR_BUFFER_BIT);
      if (on) {
        gl.uniform2f(uni.uRes, canvas.width, canvas.height);
        gl.uniform2f(uni.uC, smooth.x * scale, (innerHeight - smooth.y) * scale);
        gl.uniform1f(uni.uR, smooth.r * scale);
        gl.uniform1f(uni.uT, clock);
        gl.uniform1f(uni.uM, smooth.morph);
        gl.uniform1f(uni.uRot, (window.scrollY || 0) * 0.0016);
        gl.uniform1f(uni.uA, state.alpha);
        gl.uniform1f(uni.uPx, 1.0);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
    } else if (fallback) {
      var d = smooth.r * 1.5;
      fallback.style.width = d + 'px'; fallback.style.height = d + 'px';
      fallback.style.transform = 'translate(' + (smooth.x - d / 2) + 'px,' + (smooth.y - d / 2) + 'px) rotate(' + ((window.scrollY || 0) * 0.05) + 'deg)';
      fallback.style.opacity = state.alpha;
    }
  }
  function loop(now) { if (visible) frame(now, false); if (!CAPTURE) requestAnimationFrame(loop); }
  function startLiquid() {
    if (MODE === 'img') {
      // Phones get the still sculpture first (it spins with the clock) and fetch the clip on the
      // first touch or scroll, so the hero paints fast on mobile data.
      if (mobile && !CAPTURE) {
        var go = function () { ['scroll', 'touchstart', 'pointerdown', 'keydown'].forEach(function (ev) { window.removeEventListener(ev, go); }); loadVideo(); };
        ['scroll', 'touchstart', 'pointerdown', 'keydown'].forEach(function (ev) { window.addEventListener(ev, go, { passive: true }); });
      } else loadVideo();
      var more = document.createElement('link'); more.rel = 'stylesheet'; more.href = '/static/css/narjis-v5-art-more.css'; document.head.appendChild(more);
    }
    if (MODE === 'img' && sculpt) { root.classList.add('v5-img'); }
    else { glOk = initGL(); root.classList.add(glOk ? 'v5-gl' : 'v5-nogl'); }
    resize();
    measure(); smooth.x = state.x; smooth.y = state.y; smooth.r = state.r;
    addEventListener('resize', function () { mobile = window.matchMedia('(max-width: 899px)').matches; resize(); ST.refresh(); });
    if (!CAPTURE) requestAnimationFrame(loop); else frame(0, true);
  }
  function loadVideo() {
    if (!video || !window.fetch || !window.Blob || !window.atob) return;
    var small = mobile || (navigator.connection && /2g|3g/.test(navigator.connection.effectiveType || ''));
    var webm = video.canPlayType('video/webm; codecs="vp9"');
    var ext = webm ? 'webm' : 'mp4';
    var url = video.dataset.src + '-' + (small ? 480 : 720) + '.' + ext + '.b64';
    fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (b64) {
      var bin = atob(b64.trim()), n = bin.length, buf = new Uint8Array(n);
      for (var i = 0; i < n; i++) buf[i] = bin.charCodeAt(i);
      video.src = URL.createObjectURL(new Blob([buf], { type: 'video/' + ext }));
      video.addEventListener('playing', function () { videoOn = true; root.classList.add('v5-video'); }, { once: true });
      if (CAPTURE) { video.addEventListener('loadeddata', function () { videoOn = true; root.classList.add('v5-video'); }, { once: true }); video.load(); }
      else { var p = video.play(); if (p && p.catch) p.catch(function () {}); }
    }).catch(function () {});
  }
  var kick = function () { (window.requestIdleCallback || function (f) { return setTimeout(f, 200); })(startLiquid, { timeout: 1200 }); };
  if (CAPTURE) startLiquid();
  else if (document.readyState === 'complete') kick(); else addEventListener('load', kick);

  // ——— capture hooks: deterministic frames for the review video ———
  if (CAPTURE) {
    gsap.ticker.sleep();
    var seen = new WeakMap();
    window.__v5 = {
      step: function (t) {
        clock = t;
        gsap.updateRoot(t);
        ST.update();
        document.getAnimations().forEach(function (a) {
          if (!seen.has(a)) seen.set(a, t);
          try { a.pause(); a.currentTime = (a instanceof CSSTransition ? (t - seen.get(a)) : t) * 1000; } catch (e) {}
        });
        if (videoOn && video.duration) { try { video.pause(); video.currentTime = t % video.duration; } catch (e) {} }
        frame(0, true);
        chrome();
      }
    };
  }
})();
