/**
 * Homepage cinematic layer: optional Three.js flower, scroll colour shift,
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
    startFlower();
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

  var flowerApi = null;
  function startFlower() {
    if (!stage) return;
    import("/static/vendor/three.module.min.js").then(function (THREE) {
      buildFlower(THREE, stage);
    }).catch(function () {
      html.classList.remove("cine-on");
      html.classList.add("cine-fallback");
    });
  }

  function buildFlower(THREE, host) {
    var w = host.clientWidth || window.innerWidth;
    var h = host.clientHeight || window.innerHeight;
    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    renderer.setSize(w, h, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    host.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(32, w / Math.max(1, h), 0.1, 40);
    camera.position.set(-0.2, 0.2, 6.6);
    camera.lookAt(-0.55, 0.05, 0);

    scene.add(new THREE.AmbientLight(0x3a3a3a, 0.7));
    var key = new THREE.DirectionalLight(0xffb08a, 2.8);
    key.position.set(-2.2, 3.4, 4.2);
    scene.add(key);
    var rim = new THREE.DirectionalLight(0xff8a64, 1.1);
    rim.position.set(4, 2, -3);
    scene.add(rim);
    var fill = new THREE.PointLight(0xff5a36, 6, 12);
    fill.position.set(0.2, 1.4, 2.2);
    scene.add(fill);

    var root = new THREE.Group();
    root.rotation.z = -0.1;
    root.position.set(-0.62, -1.35, 0);
    var baseScale = 0.82;
    root.scale.setScalar(baseScale);
    scene.add(root);

    var stemMat = new THREE.MeshStandardMaterial({ color: 0x2a2a2a, roughness: 0.7, metalness: 0.05 });
    var stem = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.1, 3.2, 16), stemMat);
    stem.position.y = 0.2;
    root.add(stem);

    function leaf(x, rot, scale) {
      var g = new THREE.SphereGeometry(1, 16, 12);
      g.scale(0.22, 1.15, 0.06);
      var m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: 0x2e2e2e, roughness: 0.65 }));
      m.position.set(x, -0.15, 0);
      m.rotation.z = rot;
      m.scale.multiplyScalar(scale);
      root.add(m);
    }
    leaf(-0.35, 0.7, 1);
    leaf(0.4, -0.55, 0.85);

    var head = new THREE.Group();
    head.position.y = 1.85;
    root.add(head);

    var petalMat = new THREE.MeshStandardMaterial({
      color: 0xf5f5f5,
      roughness: 0.45,
      metalness: 0.04,
      side: THREE.DoubleSide
    });
    for (var i = 0; i < 6; i++) {
      var petal = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 14), petalMat);
      petal.scale.set(0.32, 0.82, 0.07);
      petal.position.y = 0.55;
      var wrap = new THREE.Group();
      wrap.rotation.y = (i / 6) * Math.PI * 2;
      wrap.rotation.x = 0.55;
      wrap.add(petal);
      head.add(wrap);
    }

    var coronaPts = [];
    for (var k = 0; k <= 12; k++) {
      var t = k / 12;
      coronaPts.push(new THREE.Vector2(0.12 + 0.22 * Math.sin(t * Math.PI), t * 0.55));
    }
    var corona = new THREE.Mesh(
      new THREE.LatheGeometry(coronaPts, 28),
      new THREE.MeshStandardMaterial({ color: 0xff5a36, roughness: 0.32, metalness: 0.18, emissive: 0x5a1208, emissiveIntensity: 0.35 })
    );
    corona.position.y = 0.12;
    head.add(corona);

    var stamenMat = new THREE.MeshStandardMaterial({ color: 0xff5a36, roughness: 0.4, metalness: 0.2 });
    for (var s = 0; s < 6; s++) {
      var st = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 8), stamenMat);
      var a = (s / 6) * Math.PI * 2;
      st.position.set(Math.cos(a) * 0.09, 0.52, Math.sin(a) * 0.09);
      head.add(st);
    }

    var targetRot = 0, targetScale = 1;
    flowerApi = {
      setScroll: function (p) {
        targetRot = p * Math.PI * 1.25;
        targetScale = 1 + p * 0.16;
      }
    };

    var running = true;
    var rot = 0, sc = 1;
    function tick() {
      if (!running) return;
      requestAnimationFrame(tick);
      var p = progress();
      flowerApi.setScroll(p);
      setShift(p);
      rot += (targetRot - rot) * 0.08;
      sc += (targetScale - sc) * 0.08;
      root.rotation.y = rot;
      root.scale.setScalar(baseScale * sc);
      head.rotation.y += 0.0025;
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
