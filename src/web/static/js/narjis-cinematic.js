/**
 * Homepage cinematic layer: optional Three.js mirror (the ن and its reflection), scroll colour shift,
 * pin/parallax on capable desktops. Never required for first paint.
 */
(function () {
  var html = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) html.setAttribute("data-reduce", "1");

  var stage = document.getElementById("cineStage");
  var bg = document.getElementById("cineBg");

  function setShift(t) {
    if (bg) bg.style.setProperty("--cine-shift", String(t));
    document.body && document.body.style.setProperty("--cine-shift", String(t));
  }

  function progress() {
    var max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    return Math.min(1, Math.max(0, window.scrollY / max));
  }

  function onScrollLite() {
    setShift(progress());
  }

  var rises = document.querySelectorAll(".cine-rise");
  if (rises.length && !reduce && html.classList.contains("cine-on")) {
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) e.target.classList.add("is-in");
        });
      }, { threshold: 0.18, rootMargin: "0px 0px -8% 0px" });
      rises.forEach(function (el) { io.observe(el); });
    } else {
      rises.forEach(function (el) { el.classList.add("is-in"); });
    }
  } else {
    rises.forEach(function (el) { el.classList.add("is-in"); });
  }

  if (html.classList.contains("cine-fallback") || reduce) {
    window.addEventListener("scroll", onScrollLite, { passive: true });
    onScrollLite();
    return;
  }

  var enhancePins = window.matchMedia("(min-width: 900px)").matches && !reduce;

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
    if (ric) ric(fn, { timeout: 1800 });
    else setTimeout(fn, 400);
  }

  afterPaint(function () {
    // Owner decision (Nov 2026): the brand is about reflection, not the flower.
    // The scene is the letter nun and its reflection in still water.
    startMirror();
    if (enhancePins) startPins();
    else {
      window.addEventListener("scroll", onScrollLite, { passive: true });
      onScrollLite();
    }
  });

  function startPins() {
    Promise.all([
      loadScript("/static/vendor/gsap.min.js"),
      loadScript("/static/vendor/ScrollTrigger.min.js"),
      loadScript("/static/vendor/lenis.min.js")
    ]).then(function () {
      var gsap = window.gsap;
      var ScrollTrigger = window.ScrollTrigger;
      var Lenis = window.Lenis;
      if (!gsap || !ScrollTrigger) {
        window.addEventListener("scroll", onScrollLite, { passive: true });
        return;
      }
      gsap.registerPlugin(ScrollTrigger);
      var lenis = null;
      if (typeof Lenis === "function") {
        lenis = new Lenis({ lerp: 0.08, smoothWheel: true });
        lenis.on("scroll", ScrollTrigger.update);
        gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
        gsap.ticker.lagSmoothing(0);
      }
      document.querySelectorAll(".cine-chapter").forEach(function (section) {
        ScrollTrigger.create({
          trigger: section,
          start: "top top",
          end: "+=90%",
          pin: true,
          pinSpacing: true,
          anticipatePin: 1
        });
      });
      ScrollTrigger.create({
        trigger: document.body,
        start: "top top",
        end: "bottom bottom",
        onUpdate: function (self) { setShift(self.progress); }
      });
    }).catch(function () {
      window.addEventListener("scroll", onScrollLite, { passive: true });
      onScrollLite();
    });
  }

  // The Narcissus myth, not the flower: the letter ن (Al-Narjis) leans over
  // still water and meets its own reflection. Reflection = mirrored clone.
  function startMirror() {
    if (!stage) return;
    import("/static/vendor/three.module.min.js").then(function (THREE) {
      buildMirror(THREE, stage);
    }).catch(function () {
      html.classList.remove("cine-on");
      html.classList.add("cine-fallback");
    });
  }

  function buildMirror(THREE, host) {
    var w = host.clientWidth || window.innerWidth;
    var h = host.clientHeight || window.innerHeight;
    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    renderer.setSize(w, h, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    host.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(32, w / Math.max(1, h), 0.1, 40);
    camera.position.set(-0.4, 0.9, 7.2);
    camera.lookAt(-1.05, 0.0, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.35));
    var key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(-2.4, 4.2, 5.2);
    scene.add(key);
    var rim = new THREE.DirectionalLight(0xffffff, 1.2);
    rim.position.set(3.0, 2.6, -4.4);
    scene.add(rim);

    var root = new THREE.Group();
    root.position.set(-0.68, 0.3, 0);
    root.scale.setScalar(0.5);
    scene.add(root);

    function letterNun(opacity) {
      var g = new THREE.Group();
      var bodyMat = new THREE.MeshStandardMaterial({
        color: 0xf6f5f4, roughness: 0.3, metalness: 0.25,
        transparent: opacity < 1, opacity: opacity
      });
      var dotMat = new THREE.MeshStandardMaterial({
        color: 0xff5a36, roughness: 0.25, metalness: 0.15,
        emissive: 0xff5a36, emissiveIntensity: 0.55,
        transparent: opacity < 1, opacity: opacity
      });
      var pts = [];
      pts.push(new THREE.Vector3(-0.9, 0.55, 0));
      for (var i = 0; i <= 24; i++) {
        var a = Math.PI + (i / 24) * Math.PI;
        pts.push(new THREE.Vector3(Math.cos(a) * 0.9, 0.2 + Math.sin(a) * 0.9 * 0.85, 0));
      }
      pts.push(new THREE.Vector3(0.9, 0.55, 0));
      var curve = new THREE.CatmullRomCurve3(pts);
      g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 80, 0.12, 20, false), bodyMat));
      [-0.9, 0.9].forEach(function (x) {
        var cap = new THREE.Mesh(new THREE.SphereGeometry(0.12, 20, 20), bodyMat);
        cap.position.set(x, 0.55, 0);
        g.add(cap);
      });
      var dot = new THREE.Mesh(new THREE.SphereGeometry(0.2, 32, 32), dotMat);
      dot.position.set(0, 1.05, 0);
      g.add(dot);
      return g;
    }

    var WATER = -0.55;
    var figure = letterNun(1);
    figure.position.y = WATER + 0.95;
    root.add(figure);
    var mirror = letterNun(0.28);
    mirror.scale.y = -1;
    mirror.position.y = WATER - 0.95;
    root.add(mirror);

    var glow = new THREE.PointLight(0xff5a36, 1.4, 3.5);
    glow.position.set(0, figure.position.y + 1.1, 0.5);
    root.add(glow);

    var ripples = [];
    for (var r = 0; r < 4; r++) {
      var ring = new THREE.Mesh(
        new THREE.RingGeometry(0.98, 1.0, 96),
        new THREE.MeshBasicMaterial({ color: 0xff5a36, transparent: true, opacity: 0.0, side: THREE.DoubleSide })
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = WATER;
      ring.userData.phase = r / 4;
      root.add(ring);
      ripples.push(ring);
    }
    var line = new THREE.Mesh(
      new THREE.PlaneGeometry(6, 0.012),
      new THREE.MeshBasicMaterial({ color: 0xff5a36, transparent: true, opacity: 0.55 })
    );
    line.position.y = WATER;
    root.add(line);

    var running = true;
    var rot = 0;
    var t0 = performance.now();
    function tick() {
      if (!running) return;
      requestAnimationFrame(tick);
      var p = progress();
      setShift(p);
      var t = (performance.now() - t0) / 1000;
      rot += (p * Math.PI * 0.9 - rot) * 0.06;
      var bob = Math.sin(t * 0.9) * 0.06;
      figure.position.y = WATER + 0.95 + bob;
      mirror.position.y = WATER - 0.95 - bob;
      figure.rotation.y = mirror.rotation.y = rot + Math.sin(t * 0.35) * 0.25;
      ripples.forEach(function (ring) {
        var k = (t * 0.18 + ring.userData.phase) % 1;
        ring.scale.setScalar(0.4 + k * 2.4);
        ring.material.opacity = 0.35 * (1 - k);
      });
      renderer.render(scene, camera);
    }
    tick();

    function onResize() {
      var cw = host.clientWidth || window.innerWidth;
      var ch = host.clientHeight || window.innerHeight;
      camera.aspect = cw / Math.max(1, ch);
      camera.updateProjectionMatrix();
      renderer.setSize(cw, ch, false);
    }
    window.addEventListener("resize", onResize, { passive: true });
    document.addEventListener("visibilitychange", function () {
      running = document.visibilityState !== "hidden";
      if (running) tick();
    });
  }
})();
