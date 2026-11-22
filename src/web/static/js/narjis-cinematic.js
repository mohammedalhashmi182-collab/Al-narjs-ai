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
    // Owner decision (Nov 2026): the brand is about reflection, not the flower.
    // The 3D flower stays in the file but is no longer started on the homepage.
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
    camera.position.set(-0.35, 0.42, 7.0);
    camera.lookAt(-1.02, 0.28, 0);

    renderer.toneMappingExposure = 1.05;
    scene.add(new THREE.AmbientLight(0xffffff, 0.32));
    var key = new THREE.DirectionalLight(0xffffff, 1.35);
    key.position.set(-2.4, 4.2, 5.2);
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xf0f0f0, 0.4);
    fill.position.set(3.2, 0.8, 3.4);
    scene.add(fill);
    var rim = new THREE.DirectionalLight(0xffffff, 1.85);
    rim.position.set(3.0, 2.6, -4.4);
    scene.add(rim);

    var root = new THREE.Group();
    root.rotation.z = -0.1;
    root.position.set(-1.08, -1.28, 0);
    var baseScale = 0.66;
    root.scale.setScalar(baseScale);
    scene.add(root);

    var stemMat = new THREE.MeshStandardMaterial({
      color: 0x152a18, roughness: 0.72, metalness: 0.04
    });
    var stem = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.036, 3.15, 20), stemMat);
    stem.position.y = 0.15;
    root.add(stem);

    function makeBladeShape(len, half) {
      var s = new THREE.Shape();
      s.moveTo(0, 0);
      s.bezierCurveTo(-half, len * 0.18, -half * 0.85, len * 0.62, 0, len);
      s.bezierCurveTo(half * 0.85, len * 0.62, half, len * 0.18, 0, 0);
      return s;
    }
    var leafMat = new THREE.MeshStandardMaterial({
      color: 0x1a2618, roughness: 0.7, metalness: 0.03, side: THREE.DoubleSide
    });
    function leaf(x, rotZ, rotY, len, half) {
      var g = new THREE.ExtrudeGeometry(makeBladeShape(len, half), {
        depth: 0.018, bevelEnabled: false, curveSegments: 10
      });
      var m = new THREE.Mesh(g, leafMat);
      m.position.set(x, -0.35, 0.02);
      m.rotation.set(0.15, rotY, rotZ);
      root.add(m);
    }
    leaf(-0.08, 0.62, 0.35, 1.85, 0.055);
    leaf(0.1, -0.52, -0.4, 1.55, 0.048);

    var head = new THREE.Group();
    head.position.y = 1.78;
    head.rotation.x = -0.26;
    root.add(head);

    var glow = new THREE.PointLight(0xff5a36, 1.6, 3.2);
    glow.position.set(0, 0.22, 0.35);
    head.add(glow);

    var petalMat = new THREE.MeshStandardMaterial({
      color: 0xf6f5f4,
      roughness: 0.36,
      metalness: 0.03,
      side: THREE.DoubleSide
    });
    var petalShape = new THREE.Shape();
    petalShape.moveTo(0, 0);
    petalShape.bezierCurveTo(-0.05, 0.1, -0.2, 0.3, -0.22, 0.55);
    petalShape.bezierCurveTo(-0.2, 0.78, -0.08, 0.96, 0, 1.12);
    petalShape.bezierCurveTo(0.08, 0.96, 0.2, 0.78, 0.22, 0.55);
    petalShape.bezierCurveTo(0.2, 0.3, 0.05, 0.1, 0, 0);
    var petalGeom = new THREE.ExtrudeGeometry(petalShape, {
      depth: 0.022,
      bevelEnabled: true,
      bevelThickness: 0.012,
      bevelSize: 0.016,
      bevelSegments: 2,
      curveSegments: 18
    });
    petalGeom.translate(0, 0, -0.011);
    for (var i = 0; i < 6; i++) {
      var wrap = new THREE.Group();
      wrap.rotation.z = (i / 6) * Math.PI * 2;
      var petal = new THREE.Mesh(petalGeom, petalMat);
      petal.rotation.x = 0.16;
      petal.position.y = 0.08;
      wrap.add(petal);
      head.add(wrap);
    }

    var coronaPts = [];
    var cProfile = [
      [0.12, 0], [0.17, 0.04], [0.2, 0.1], [0.22, 0.18],
      [0.26, 0.26], [0.33, 0.32], [0.36, 0.36], [0.33, 0.38]
    ];
    for (var k = 0; k < cProfile.length; k++) {
      coronaPts.push(new THREE.Vector2(cProfile[k][0], cProfile[k][1]));
    }
    var corona = new THREE.Mesh(
      new THREE.LatheGeometry(coronaPts, 48),
      new THREE.MeshStandardMaterial({
        color: 0xff5a36,
        roughness: 0.3,
        metalness: 0.12,
        emissive: 0x5a1208,
        emissiveIntensity: 0.28,
        side: THREE.DoubleSide
      })
    );
    corona.position.z = 0.02;
    head.add(corona);
    var lip = new THREE.Mesh(
      new THREE.TorusGeometry(0.345, 0.016, 10, 48),
      new THREE.MeshStandardMaterial({
        color: 0xff7a55, roughness: 0.28, metalness: 0.14,
        emissive: 0x5a1208, emissiveIntensity: 0.2
      })
    );
    lip.position.z = 0.02;
    lip.position.y = 0.365;
    lip.rotation.x = Math.PI / 2;
    head.add(lip);

    var filamentMat = new THREE.MeshStandardMaterial({ color: 0xf6f5f4, roughness: 0.5 });
    var antherMat = new THREE.MeshStandardMaterial({ color: 0xff5a36, roughness: 0.4, metalness: 0.12 });
    for (var s = 0; s < 6; s++) {
      var a = (s / 6) * Math.PI * 2;
      var fx = Math.cos(a) * 0.07;
      var fy = Math.sin(a) * 0.07;
      var fil = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.01, 0.22, 6), filamentMat);
      fil.position.set(fx, 0.18, 0.06 + fy * 0.12);
      head.add(fil);
      var an = new THREE.Mesh(new THREE.SphereGeometry(0.022, 8, 8), antherMat);
      an.position.set(fx, 0.3, 0.08 + fy * 0.12);
      head.add(an);
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
