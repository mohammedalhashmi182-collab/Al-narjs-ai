/* 3D silver narcissus emblem. Line-curves in WebGL, not audio, no points, no CDN.
   If WebGL is missing, the image stays and CSS breathes it.
   prefers-reduced-motion keeps that image still. */
(() => {
  "use strict";

  const stage = document.getElementById("emblem");
  const canvas = document.getElementById("emblemGl");
  const image = document.getElementById("emblemImg");
  if (!stage || !canvas || !image) return;

  const reduceQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  const reduced = () => !!reduceQuery.matches;
  const BREATH = 4;
  const PETALS = 8;
  const LINES = 13;
  const STEPS = 42;

  let gl = null;
  let lineProg = null;
  let blurProg = null;
  let copyProg = null;
  let lineLoc = null;
  let blurLoc = null;
  let copyLoc = null;
  let flowerBuf = null;
  let flowerCount = 0;
  let clipBuf = null;
  let targets = null;
  let raf = null;
  let clock = 0;
  let previous = 0;

  window.__emblemMode = "image";

  function showImage() {
    window.__emblemMode = "image";
    stage.classList.remove("is-live");
    canvas.hidden = true;
    if (raf !== null) {
      window.cancelAnimationFrame(raf);
      raf = null;
    }
  }

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function norm(a) {
    const l = Math.hypot(a[0], a[1], a[2]) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  }

  function bez(t, a, b, c, d) {
    const u = 1 - t;
    return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d;
  }

  function buildFlower() {
    const data = [];
    const tilt = 0.34;
    const ct = Math.cos(tilt);
    const st = Math.sin(tilt);
    function put(x, y, z, c, s) {
      const y2 = ct * y - st * z;
      const z2 = st * y + ct * z;
      return [c * x - s * y2, s * x + c * y2, z2];
    }
    function push(center, side, across, along, kind, shade) {
      data.push(
        center[0], center[1], center[2],
        side[0], side[1], side[2],
        across, along, kind, shade
      );
    }
    for (let p = 0; p < PETALS; p++) {
      const ang = (p / PETALS) * Math.PI * 2;
      const c = Math.cos(ang);
      const s = Math.sin(ang);
      for (let li = 0; li < LINES; li++) {
        const spread = (li / (LINES - 1) - 0.5) * 2;
        const shade = 1 - Math.abs(spread) * 0.38;
        const pts = [];
        const sides = [];
        for (let i = 0; i <= STEPS; i++) {
          const t = i / STEPS;
          const edge = bez(t, 0, 0.52, 0.2, 0);
          const x = spread * edge;
          const y = bez(t, 0.02, 0.32, 0.78, 1);
          const z = Math.sin(t * Math.PI) * 0.15 * (0.5 + 0.5 * (1 - spread * spread));
          const center = put(x, y, z, c, s);
          const across = norm(sub(put(x + 1, y, z, c, s), center));
          pts.push(center);
          sides.push(across);
        }
        for (let i = 0; i < STEPS; i++) {
          const a = pts[i];
          const b = pts[i + 1];
          const sa = sides[i];
          const sb = sides[i + 1];
          const ta = i / STEPS;
          const tb = (i + 1) / STEPS;
          push(a, sa, -1, ta, 0, shade);
          push(a, sa, 1, ta, 0, shade);
          push(b, sb, -1, tb, 0, shade);
          push(a, sa, 1, ta, 0, shade);
          push(b, sb, 1, tb, 0, shade);
          push(b, sb, -1, tb, 0, shade);
        }
      }
    }
    const radius = 0.062;
    const core = [0, 0, 0.04];
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, -1], [1, 1], [-1, 1]];
    for (let i = 0; i < corners.length; i++) {
      const u = corners[i][0];
      const v = corners[i][1];
      push([core[0] + u * radius, core[1] + v * radius, core[2]], [0, 0, 0], u, v, 1, 1);
    }
    return new Float32Array(data);
  }

  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      window.__emblemError = gl.getShaderInfoLog(shader) || "shader";
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function link(vs, fs, binds) {
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    for (let i = 0; i < binds.length; i++) gl.bindAttribLocation(program, i, binds[i]);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      window.__emblemError = gl.getProgramInfoLog(program) || "link";
      return null;
    }
    return program;
  }

  const LINE_VS = [
    "attribute vec3 aCenter;",
    "attribute vec3 aSide;",
    "attribute float aAcross;",
    "attribute float aAlong;",
    "attribute float aKind;",
    "attribute float aShade;",
    "uniform mat4 uMVP;",
    "uniform float uHalf;",
    "varying float vAcross;",
    "varying float vAlong;",
    "varying float vKind;",
    "varying float vShade;",
    "void main(){",
    "  vec3 pos=aCenter+aSide*(aAcross*uHalf);",
    "  gl_Position=uMVP*vec4(pos,1.0);",
    "  vAcross=aAcross; vAlong=aAlong; vKind=aKind; vShade=aShade;",
    "}",
  ].join("\n");

  const LINE_FS = [
    "precision mediump float;",
    "varying float vAcross, vAlong, vKind, vShade;",
    "uniform float uLight;",
    "void main(){",
    "  vec3 silver=vec3(0.93,0.945,0.97);",
    "  if(vKind>0.5){",
    "    float r=length(vec2(vAcross,vAlong));",
    "    if(r>1.0) discard;",
    "    float heart=exp(-r*r*4.2);",
    "    gl_FragColor=vec4(silver*heart*uLight*1.15,1.0);",
    "    return;",
    "  }",
    "  float edge=pow(max(1.0-abs(vAcross),0.0),1.45);",
    "  float taper=smoothstep(0.0,0.045,vAlong)*smoothstep(1.0,0.9,vAlong);",
    "  float mag=edge*taper*(0.62+0.38*vShade)*uLight;",
    "  gl_FragColor=vec4(silver*mag,1.0);",
    "}",
  ].join("\n");

  const BLUR_VS = [
    "attribute vec2 aClip;",
    "varying vec2 vUv;",
    "void main(){",
    "  vUv=aClip*0.5+0.5;",
    "  gl_Position=vec4(aClip,0.0,1.0);",
    "}",
  ].join("\n");

  const BLUR_FS = [
    "precision mediump float;",
    "varying vec2 vUv;",
    "uniform sampler2D uTex;",
    "uniform vec2 uDir;",
    "void main(){",
    "  vec3 c=texture2D(uTex,vUv).rgb*0.227;",
    "  c+=texture2D(uTex,vUv+uDir*1.4).rgb*0.194;",
    "  c+=texture2D(uTex,vUv-uDir*1.4).rgb*0.194;",
    "  c+=texture2D(uTex,vUv+uDir*3.2).rgb*0.122;",
    "  c+=texture2D(uTex,vUv-uDir*3.2).rgb*0.122;",
    "  c+=texture2D(uTex,vUv+uDir*5.4).rgb*0.071;",
    "  c+=texture2D(uTex,vUv-uDir*5.4).rgb*0.071;",
    "  gl_FragColor=vec4(c,1.0);",
    "}",
  ].join("\n");

  const COPY_FS = [
    "precision mediump float;",
    "varying vec2 vUv;",
    "uniform sampler2D uSharp;",
    "uniform sampler2D uGlow;",
    "uniform float uBloom;",
    "void main(){",
    "  vec3 sharp=texture2D(uSharp,vUv).rgb;",
    "  vec3 glow=texture2D(uGlow,vUv).rgb;",
    "  gl_FragColor=vec4(sharp+glow*uBloom,1.0);",
    "}",
  ].join("\n");

  function locations(program, names) {
    const out = {};
    for (let i = 0; i < names.length; i++) out[names[i]] = gl.getUniformLocation(program, names[i]);
    return out;
  }

  function makeTarget(w, h) {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    const fb = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return ok ? { tex: tex, fb: fb, w: w, h: h } : null;
  }

  function allocTargets() {
    if (targets) {
      gl.deleteTexture(targets.scene.tex);
      gl.deleteFramebuffer(targets.scene.fb);
      gl.deleteTexture(targets.blurA.tex);
      gl.deleteFramebuffer(targets.blurA.fb);
      gl.deleteTexture(targets.blurB.tex);
      gl.deleteFramebuffer(targets.blurB.fb);
      targets = null;
    }
    const w = Math.max(2, canvas.width);
    const h = Math.max(2, canvas.height);
    const bw = Math.max(2, w >> 1);
    const bh = Math.max(2, h >> 1);
    const scene = makeTarget(w, h);
    const blurA = makeTarget(bw, bh);
    const blurB = makeTarget(bw, bh);
    if (!scene || !blurA || !blurB) {
      targets = null;
      return;
    }
    targets = { scene: scene, blurA: blurA, blurB: blurB };
  }

  function bindFlower() {
    gl.bindBuffer(gl.ARRAY_BUFFER, flowerBuf);
    const stride = 40;
    const layout = [[0, 3, 0], [1, 3, 12], [2, 1, 24], [3, 1, 28], [4, 1, 32], [5, 1, 36]];
    for (let i = 0; i < layout.length; i++) {
      gl.enableVertexAttribArray(layout[i][0]);
      gl.vertexAttribPointer(layout[i][0], layout[i][1], gl.FLOAT, false, stride, layout[i][2]);
    }
  }

  function bindClip() {
    gl.bindBuffer(gl.ARRAY_BUFFER, clipBuf);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (let i = 1; i <= 5; i++) gl.disableVertexAttribArray(i);
  }

  function perspective(fov, aspect, near, far) {
    const f = 1 / Math.tan(fov / 2);
    const nf = 1 / (near - far);
    const m = new Float32Array(16);
    m[0] = f / aspect;
    m[5] = f;
    m[10] = (far + near) * nf;
    m[11] = -1;
    m[14] = 2 * far * near * nf;
    return m;
  }

  function lookAt(eye, target, up) {
    const z = norm(sub(eye, target));
    const x = norm(cross(up, z));
    const y = cross(z, x);
    const m = new Float32Array(16);
    m[0] = x[0]; m[1] = y[0]; m[2] = z[0];
    m[4] = x[1]; m[5] = y[1]; m[6] = z[1];
    m[8] = x[2]; m[9] = y[2]; m[10] = z[2];
    m[12] = -dot(x, eye); m[13] = -dot(y, eye); m[14] = -dot(z, eye); m[15] = 1;
    return m;
  }

  function multiply(a, b) {
    const m = new Float32Array(16);
    for (let c = 0; c < 4; c++) {
      for (let r = 0; r < 4; r++) {
        m[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
    }
    return m;
  }

  function modelMatrix(yaw, pitch, bob, scale) {
    const cy = Math.cos(yaw);
    const sy = Math.sin(yaw);
    const cx = Math.cos(pitch);
    const sx = Math.sin(pitch);
    const m = new Float32Array(16);
    m[0] = cy * scale;
    m[1] = 0;
    m[2] = -sy * scale;
    m[4] = sy * sx * scale;
    m[5] = cx * scale;
    m[6] = cy * sx * scale;
    m[8] = -sy * cx * scale;
    m[9] = -sx * scale;
    m[10] = cy * cx * scale;
    m[13] = bob;
    m[15] = 1;
    return m;
  }

  function pose() {
    const breath = 0.5 - 0.5 * Math.cos(((clock % BREATH) / BREATH) * Math.PI * 2);
    return {
      yaw: clock * 0.26,
      pitch: 0.16 * Math.sin(clock * 0.33),
      bob: Math.sin(clock * 0.65) * 0.04,
      scale: 0.8 + breath * 0.018,
      light: 0.48 + breath * 0.72,
      bloom: 0.2 + breath * 0.62,
    };
  }

  function drawFlower(mvp, half, light) {
    gl.useProgram(lineProg);
    bindFlower();
    gl.uniformMatrix4fv(lineLoc.uMVP, false, mvp);
    gl.uniform1f(lineLoc.uHalf, half);
    gl.uniform1f(lineLoc.uLight, light);
    gl.drawArrays(gl.TRIANGLES, 0, flowerCount);
  }

  function render() {
    const box = canvas.width;
    const height = canvas.height;
    if (box < 2 || height < 2) return;
    const view = pose();
    const aspect = box / height;
    const proj = perspective((32 * Math.PI) / 180, aspect, 0.1, 20);
    const cam = lookAt([0, 0.22, 3.85], [0, 0, 0], [0, 1, 0]);
    const mvp = multiply(proj, multiply(cam, modelMatrix(view.yaw, view.pitch, view.bob, view.scale)));
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE);
    if (targets) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets.scene.fb);
      gl.viewport(0, 0, targets.scene.w, targets.scene.h);
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      drawFlower(mvp, 0.0056, view.light);
      gl.useProgram(blurProg);
      bindClip();
      gl.uniform1i(blurLoc.uTex, 0);
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets.blurA.fb);
      gl.viewport(0, 0, targets.blurA.w, targets.blurA.h);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, targets.scene.tex);
      gl.uniform2f(blurLoc.uDir, 1.6 / targets.scene.w, 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets.blurB.fb);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bindTexture(gl.TEXTURE_2D, targets.blurA.tex);
      gl.uniform2f(blurLoc.uDir, 0, 1.6 / targets.blurA.h);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, box, height);
      gl.disable(gl.BLEND);
      gl.useProgram(copyProg);
      bindClip();
      gl.uniform1i(copyLoc.uSharp, 0);
      gl.uniform1i(copyLoc.uGlow, 1);
      gl.uniform1f(copyLoc.uBloom, view.bloom);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, targets.scene.tex);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, targets.blurB.tex);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.activeTexture(gl.TEXTURE0);
      return;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, box, height);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    drawFlower(mvp, 0.014, view.light * 0.28);
    drawFlower(mvp, 0.0056, view.light);
  }

  function resize() {
    const css = Math.max(stage.clientWidth || 220, 2);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const size = Math.max(2, Math.round(css * dpr));
    if (canvas.width !== size || canvas.height !== size) {
      canvas.width = size;
      canvas.height = size;
      if (gl) allocTargets();
    }
    if (gl && reduced()) showImage();
    else if (gl) render();
  }

  function frame(now) {
    if (document.hidden || reduced()) {
      raf = null;
      previous = 0;
      if (reduced()) showImage();
      return;
    }
    const dt = previous ? Math.min(0.034, Math.max(0, now - previous) / 1000) : 0.016;
    previous = now;
    clock += dt;
    render();
    raf = window.requestAnimationFrame(frame);
  }

  function boot() {
    if (reduced()) {
      showImage();
      return;
    }
    try {
      gl = canvas.getContext("webgl", {
        alpha: false,
        antialias: false,
        depth: false,
        stencil: false,
        premultipliedAlpha: false,
        preserveDrawingBuffer: true,
        powerPreference: "high-performance",
        failIfMajorPerformanceCaveat: false,
      });
    } catch (error) {
      gl = null;
    }
    if (!gl) {
      showImage();
      return;
    }
    const lineVs = compile(gl.VERTEX_SHADER, LINE_VS);
    const lineFs = compile(gl.FRAGMENT_SHADER, LINE_FS);
    const blurVs = compile(gl.VERTEX_SHADER, BLUR_VS);
    const blurFs = compile(gl.FRAGMENT_SHADER, BLUR_FS);
    const copyFs = compile(gl.FRAGMENT_SHADER, COPY_FS);
    if (!lineVs || !lineFs || !blurVs || !blurFs || !copyFs) {
      showImage();
      return;
    }
    lineProg = link(lineVs, lineFs, ["aCenter", "aSide", "aAcross", "aAlong", "aKind", "aShade"]);
    blurProg = link(blurVs, blurFs, ["aClip"]);
    copyProg = link(blurVs, copyFs, ["aClip"]);
    if (!lineProg || !blurProg || !copyProg) {
      showImage();
      return;
    }
    lineLoc = locations(lineProg, ["uMVP", "uHalf", "uLight"]);
    blurLoc = locations(blurProg, ["uTex", "uDir"]);
    copyLoc = locations(copyProg, ["uSharp", "uGlow", "uBloom"]);
    const flower = buildFlower();
    flowerCount = flower.length / 10;
    flowerBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, flowerBuf);
    gl.bufferData(gl.ARRAY_BUFFER, flower, gl.STATIC_DRAW);
    clipBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, clipBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.disable(gl.DEPTH_TEST);
    canvas.hidden = false;
    stage.classList.add("is-live");
    window.__emblemMode = "webgl";
    resize();
    if (raf === null) raf = window.requestAnimationFrame(frame);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (raf !== null) window.cancelAnimationFrame(raf);
      raf = null;
      previous = 0;
      return;
    }
    if (window.__emblemMode === "webgl" && !reduced() && raf === null) {
      raf = window.requestAnimationFrame(frame);
    }
  });
  window.addEventListener("resize", () => {
    if (window.__emblemMode === "webgl") resize();
  }, { passive: true });
  if (reduceQuery.addEventListener) {
    reduceQuery.addEventListener("change", () => {
      if (reduced()) showImage();
      else if (!gl) boot();
      else {
        canvas.hidden = false;
        stage.classList.add("is-live");
        window.__emblemMode = "webgl";
        if (raf === null) raf = window.requestAnimationFrame(frame);
      }
    });
  }
  if (window.ResizeObserver) {
    const observer = new ResizeObserver(() => {
      if (window.__emblemMode === "webgl") resize();
    });
    observer.observe(stage);
  }
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    showImage();
  });

  boot();
})();
