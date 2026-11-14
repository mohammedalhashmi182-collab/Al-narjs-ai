/* Monochrome 3D voice orb. WebGL point sphere, canvas-2D only if WebGL is missing.
   Idle breathing on load. Microphone permission is never requested here.
   ?orbdemo=1 feeds a silent oscillator into an AnalyserNode. No network, no CDN. */
(() => {
  "use strict";

  const PARTICLE_COUNT = 14000;
  const CAM_Z = 4.05;
  const FOCAL = 1 / Math.tan((40 * Math.PI) / 360);

  const canvas = document.getElementById("orb");
  const card = document.getElementById("p");
  if (!canvas || !canvas.getContext) return;

  const reduceQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  const reduce = () => !!reduceQuery.matches;

  const sphere = buildSphere(PARTICLE_COUNT);
  let gl = null;
  let program = null;
  let uniforms = null;
  let blurProg = null;
  let copyProg = null;
  let blurLoc = null;
  let copyLoc = null;
  let clipBuf = null;
  let bloom = null;
  let pointPos = null;
  let pointSeed = null;
  let ctx2d = null;
  let sprite = null;
  let order = null;
  let depthBuf = null;
  let raf = null;
  let clock = 0;
  let previous = 0;
  let level = 0;
  let ripple = 0;
  let glow = 0.92;
  let demoCtx = null;
  let demoGain = null;
  let demoOsc = null;
  let demoAnalyser = null;
  let timeBuf = new Uint8Array(0);
  let freqBuf = new Uint8Array(0);

  window.__orbMode = "init";
  window.__orbEnergy = 0;

  function hash(n) {
    const x = Math.sin(n * 127.1) * 43758.5453;
    return x - Math.floor(x);
  }

  function buildSphere(count) {
    // Fibonacci sphere, then jitter so the points do not form a visible lattice.
    const pos = new Float32Array(count * 3);
    const seed = new Float32Array(count);
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y0 = 1 - (i / (count - 1)) * 2;
      const ring = Math.sqrt(Math.max(0, 1 - y0 * y0));
      const theta = golden * i + (hash(i + 0.17) - 0.5) * 1.35;
      let x = Math.cos(theta) * ring;
      let y = y0 + (hash(i + 2.4) - 0.5) * 0.09;
      let z = Math.sin(theta) * ring;
      const len = Math.hypot(x, y, z) || 1;
      pos[i * 3] = x / len;
      pos[i * 3 + 1] = y / len;
      pos[i * 3 + 2] = z / len;
      seed[i] = hash(i + 8.6);
    }
    return { pos: pos, seed: seed };
  }

  function compile(glContext, type, source) {
    const shader = glContext.createShader(type);
    glContext.shaderSource(shader, source);
    glContext.compileShader(shader);
    if (!glContext.getShaderParameter(shader, glContext.COMPILE_STATUS)) {
      window.__orbError = glContext.getShaderInfoLog(shader) || "shader";
      glContext.deleteShader(shader);
      return null;
    }
    return shader;
  }

  const VERT = [
    "precision mediump float;",
    "attribute vec3 aBase;",
    "attribute float aSeed;",
    "uniform float uYaw, uPitch, uTime, uEnergy, uBreath, uRipple, uGlow;",
    "uniform float uPointScale, uPassAlpha, uFocal, uAspect, uCamZ, uViewportH;",
    "varying float vBright;",
    "vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}",
    "vec4 mod289v(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}",
    "vec4 permute(vec4 x){return mod289v(((x*34.0)+1.0)*x);}",
    "vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}",
    "float snoise(vec3 v){",
    "  const vec2 C=vec2(1.0/6.0,1.0/3.0);",
    "  const vec4 D=vec4(0.0,0.5,1.0,2.0);",
    "  vec3 i=floor(v+dot(v,C.yyy));",
    "  vec3 x0=v-i+dot(i,C.xxx);",
    "  vec3 g=step(x0.yzx,x0.xyz);",
    "  vec3 l=1.0-g;",
    "  vec3 i1=min(g.xyz,l.zxy);",
    "  vec3 i2=max(g.xyz,l.zxy);",
    "  vec3 x1=x0-i1+C.xxx;",
    "  vec3 x2=x0-i2+C.yyy;",
    "  vec3 x3=x0-D.yyy;",
    "  i=mod289(i);",
    "  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));",
    "  float n_=0.142857142857;",
    "  vec3 ns=n_*D.wyz-D.xzx;",
    "  vec4 j=p-49.0*floor(p*ns.z*ns.z);",
    "  vec4 x_=floor(j*ns.z);",
    "  vec4 y_=floor(j-7.0*x_);",
    "  vec4 x=x_*ns.x+ns.yyyy;",
    "  vec4 y=y_*ns.x+ns.yyyy;",
    "  vec4 h=1.0-abs(x)-abs(y);",
    "  vec4 b0=vec4(x.xy,y.xy);",
    "  vec4 b1=vec4(x.zw,y.zw);",
    "  vec4 s0=floor(b0)*2.0+1.0;",
    "  vec4 s1=floor(b1)*2.0+1.0;",
    "  vec4 sh=-step(h,vec4(0.0));",
    "  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;",
    "  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;",
    "  vec3 p0=vec3(a0.xy,h.x);",
    "  vec3 p1=vec3(a0.zw,h.y);",
    "  vec3 p2=vec3(a1.xy,h.z);",
    "  vec3 p3=vec3(a1.zw,h.w);",
    "  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));",
    "  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;",
    "  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0);",
    "  m=m*m;",
    "  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));",
    "}",
    "vec3 rotY(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(c*p.x+s*p.z,p.y,-s*p.x+c*p.z);}",
    "vec3 rotX(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(p.x,c*p.y-s*p.z,s*p.y+c*p.z);}",
    "void main(){",
    "  vec3 base=normalize(aBase);",
    "  float shell=0.78+fract(aSeed*7.13)*0.22;",
    "  float psize=0.45+fract(aSeed*13.7)*1.15;",
    "  float n1=snoise(base*1.25+vec3(uTime*0.22,uTime*0.05,0.1));",
    "  float n2=snoise(base.yzx*2.15+vec3(-uTime*0.16,0.3,uTime*0.12));",
    "  float n3=snoise(base.zxy*0.9+vec3(0.2,-uTime*0.14,uTime*0.18));",
    "  vec3 curl=vec3(",
    "    snoise(base+vec3(0.0,uTime*0.19,0.13))-snoise(base-vec3(0.0,uTime*0.19,0.13)),",
    "    snoise(base+vec3(uTime*0.15,0.0,0.07))-snoise(base-vec3(uTime*0.15,0.0,0.07)),",
    "    snoise(base+vec3(0.11,0.0,uTime*0.17))-snoise(base-vec3(0.11,0.0,uTime*0.17))",
    "  );",
    "  float amp=0.068+uEnergy*0.045;",
    "  float breath=sin(uTime*0.7+aSeed*6.28318)*0.028*uBreath;",
    "  float rad=shell*(1.0+breath+uEnergy*0.18)+n1*amp*0.5;",
    "  vec3 pos=base*rad+curl*amp+cross(base,vec3(n2,n3,n1))*amp*0.65;",
    "  pos=rotX(rotY(pos,uYaw),uPitch);",
    "  vec3 view=vec3(pos.x,pos.y,pos.z-uCamZ);",
    "  float dist=max(0.4,-view.z);",
    "  gl_Position=vec4((view.x/dist)*uFocal/uAspect,(view.y/dist)*uFocal,0.0,1.0);",
    "  float closeness=clamp((view.z-(-uCamZ-1.15))/2.3,0.0,1.0);",
    "  float shade=0.08+0.92*pow(closeness,1.25);",
    "  float coreBoost=mix(1.28,0.82,shell);",
    "  vBright=shade*coreBoost*uGlow*uPassAlpha;",
    "  gl_PointSize=clamp(uPointScale*psize*(0.28+1.15*closeness)*uFocal/dist*uViewportH,1.0,40.0);",
    "}",
  ].join("\n");

  const FRAG = [
    "precision mediump float;",
    "varying float vBright;",
    "void main(){",
    "  vec2 q=gl_PointCoord*2.0-1.0;",
    "  float r2=dot(q,q);",
    "  if(r2>1.0) discard;",
    "  float core=exp(-r2*3.4);",
    "  float halo=exp(-r2*1.05)*0.45;",
    "  float intensity=(core*0.85+halo)*vBright;",
    "  gl_FragColor=vec4(vec3(0.96,0.97,0.99)*intensity,intensity);",
    "}",
  ].join("\n");

  function bootWebGL() {
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
    if (!gl) return false;
    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return false;
    program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, "aBase");
    gl.bindAttribLocation(program, 1, "aSeed");
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      window.__orbError = gl.getProgramInfoLog(program) || "link";
      return false;
    }
    gl.useProgram(program);
    const names = ["uYaw", "uPitch", "uTime", "uEnergy", "uBreath", "uRipple", "uGlow", "uPointScale", "uPassAlpha", "uFocal", "uAspect", "uCamZ", "uViewportH"];
    uniforms = {};
    for (let i = 0; i < names.length; i++) uniforms[names[i]] = gl.getUniformLocation(program, names[i]);

    pointPos = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, pointPos);
    gl.bufferData(gl.ARRAY_BUFFER, sphere.pos, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);

    pointSeed = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, pointSeed);
    gl.bufferData(gl.ARRAY_BUFFER, sphere.seed, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 1, gl.FLOAT, false, 0, 0);

    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.clearColor(0, 0, 0, 1);
    setupBloom();
    window.__orbMode = "webgl";
    return true;
  }

  function setupBloom() {
    const vs = compile(gl, gl.VERTEX_SHADER, "attribute vec2 aClip;varying vec2 vUv;void main(){vUv=aClip*0.5+0.5;gl_Position=vec4(aClip,0.0,1.0);}");
    const blurFs = compile(gl, gl.FRAGMENT_SHADER, [
      "precision mediump float;varying vec2 vUv;uniform sampler2D uTex;uniform vec2 uDir;",
      "void main(){",
      "  vec3 c=texture2D(uTex,vUv).rgb*0.227;",
      "  c+=texture2D(uTex,vUv+uDir).rgb*0.194;c+=texture2D(uTex,vUv-uDir).rgb*0.194;",
      "  c+=texture2D(uTex,vUv+uDir*2.6).rgb*0.122;c+=texture2D(uTex,vUv-uDir*2.6).rgb*0.122;",
      "  c+=texture2D(uTex,vUv+uDir*4.8).rgb*0.07;c+=texture2D(uTex,vUv-uDir*4.8).rgb*0.07;",
      "  gl_FragColor=vec4(c,1.0);}",
    ].join(""));
    const copyFs = compile(gl, gl.FRAGMENT_SHADER, [
      "precision mediump float;varying vec2 vUv;uniform sampler2D uSharp;uniform sampler2D uGlow;uniform float uBloom;",
      "void main(){vec3 s=texture2D(uSharp,vUv).rgb;vec3 g=texture2D(uGlow,vUv).rgb;gl_FragColor=vec4(s+g*uBloom,1.0);}",
    ].join(""));
    if (!vs || !blurFs || !copyFs) return;
    function link(fs) {
      const p = gl.createProgram();
      gl.attachShader(p, vs);
      gl.attachShader(p, fs);
      gl.bindAttribLocation(p, 0, "aClip");
      gl.linkProgram(p);
      return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
    }
    blurProg = link(blurFs);
    copyProg = link(copyFs);
    if (!blurProg || !copyProg) return;
    blurLoc = { uTex: gl.getUniformLocation(blurProg, "uTex"), uDir: gl.getUniformLocation(blurProg, "uDir") };
    copyLoc = {
      uSharp: gl.getUniformLocation(copyProg, "uSharp"),
      uGlow: gl.getUniformLocation(copyProg, "uGlow"),
      uBloom: gl.getUniformLocation(copyProg, "uBloom"),
    };
    clipBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, clipBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
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

  function allocBloom() {
    if (!blurProg) return;
    if (bloom) {
      ["scene", "a", "b"].forEach((key) => {
        gl.deleteTexture(bloom[key].tex);
        gl.deleteFramebuffer(bloom[key].fb);
      });
      bloom = null;
    }
    const w = Math.max(2, canvas.width);
    const h = Math.max(2, canvas.height);
    const scene = makeTarget(w, h);
    const a = makeTarget(Math.max(2, w >> 1), Math.max(2, h >> 1));
    const b = makeTarget(Math.max(2, w >> 1), Math.max(2, h >> 1));
    if (scene && a && b) bloom = { scene: scene, a: a, b: b };
  }

  function bindPoints() {
    gl.bindBuffer(gl.ARRAY_BUFFER, pointPos);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, pointSeed);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 1, gl.FLOAT, false, 0, 0);
  }

  function bindClip() {
    gl.bindBuffer(gl.ARRAY_BUFFER, clipBuf);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.disableVertexAttribArray(1);
  }

  function boot2D() {
    ctx2d = canvas.getContext("2d", { alpha: false });
    if (!ctx2d) {
      window.__orbMode = "failed";
      return;
    }
    sprite = document.createElement("canvas");
    sprite.width = 32;
    sprite.height = 32;
    const paint = sprite.getContext("2d");
    const dot = paint.createRadialGradient(16, 16, 0, 16, 16, 16);
    dot.addColorStop(0, "rgba(244,245,247,0.95)");
    dot.addColorStop(0.35, "rgba(236,237,240,0.45)");
    dot.addColorStop(1, "rgba(236,237,240,0)");
    paint.fillStyle = dot;
    paint.fillRect(0, 0, 32, 32);
    order = new Array(PARTICLE_COUNT);
    depthBuf = new Float32Array(PARTICLE_COUNT);
    for (let i = 0; i < PARTICLE_COUNT; i++) order[i] = i;
    window.__orbMode = "2d";
  }

  function cssSize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w >= 2 && h >= 2) return [w, h];
    return [520, 520];
  }

  function resize() {
    const box = cssSize();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(2, Math.round(box[0] * dpr));
    const h = Math.max(2, Math.round(box[1] * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
      if (gl && window.__orbMode === "webgl") {
        gl.viewport(0, 0, w, h);
        allocBloom();
      }
    } else if (gl && window.__orbMode === "webgl" && !bloom) {
      allocBloom();
    }
    if (reduce()) render();
  }

  function measure(analyser) {
    if (!analyser || typeof analyser.getByteTimeDomainData !== "function") return null;
    const n = analyser.fftSize || 1024;
    if (timeBuf.length !== n) timeBuf = new Uint8Array(n);
    analyser.getByteTimeDomainData(timeBuf);
    let sum = 0;
    for (let i = 0; i < n; i++) {
      const v = (timeBuf[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / n);
    const bins = analyser.frequencyBinCount || (n >> 1);
    if (freqBuf.length !== bins) freqBuf = new Uint8Array(bins);
    let spec = 0;
    if (typeof analyser.getByteFrequencyData === "function") {
      analyser.getByteFrequencyData(freqBuf);
      const use = Math.min(bins, 72);
      for (let i = 2; i < use; i++) spec += freqBuf[i];
      spec /= Math.max(1, (use - 2) * 255);
    }
    return Math.max(0, Math.min(1, Math.max(rms * 6.2, spec * 1.25)));
  }

  function fnLevel(fn) {
    if (typeof fn !== "function") return 0;
    const raw = Number(fn());
    return Number.isFinite(raw) ? Math.max(0, Math.min(1, raw)) : 0;
  }

  function targetEnergy() {
    const cls = card && card.classList;
    if (cls && cls.contains("speaking")) {
      const live = measure(window.__voiceOutAnalyser);
      return live == null ? fnLevel(window.__outLvl) : live;
    }
    if (cls && cls.contains("listening")) {
      const live = measure(window.__voiceInAnalyser);
      return live == null ? fnLevel(window.__inLvl) : live;
    }
    if (demoAnalyser && !(cls && cls.contains("connecting"))) {
      const live = measure(demoAnalyser);
      return live == null ? 0 : live;
    }
    if (cls && cls.contains("connecting")) return 0.045 + 0.05 * (0.5 + 0.5 * Math.sin(clock * 2.3));
    return 0;
  }

  function statePose() {
    const cls = card && card.classList;
    const speaking = !!(cls && cls.contains("speaking"));
    const listening = !!(cls && cls.contains("listening"));
    const connecting = !!(cls && cls.contains("connecting"));
    if (reduce()) {
      return { yaw: 0.62, pitch: 0.26, breath: 0, glowTarget: 0.9, spinNote: 0 };
    }
    const spin = connecting ? 0.24 : (speaking ? 0.2 : 0.15);
    return {
      yaw: clock * spin,
      pitch: 0.2 + Math.sin(clock * 0.13) * 0.045,
      breath: speaking ? 0.22 : (listening ? 0.4 : (connecting ? 0.55 : 1)),
      glowTarget: 1.08 + level * (speaking ? 0.7 : 0.45),
      spinNote: 1,
    };
  }

  function paintPoints(pose, w, h) {
    gl.useProgram(program);
    bindPoints();
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.uniform1f(uniforms.uYaw, pose.yaw);
    gl.uniform1f(uniforms.uPitch, pose.pitch);
    gl.uniform1f(uniforms.uTime, reduce() ? 0.8 : clock);
    gl.uniform1f(uniforms.uEnergy, reduce() ? 0 : level);
    gl.uniform1f(uniforms.uBreath, pose.breath);
    gl.uniform1f(uniforms.uRipple, reduce() ? 0 : ripple);
    gl.uniform1f(uniforms.uGlow, glow);
    gl.uniform1f(uniforms.uFocal, FOCAL);
    gl.uniform1f(uniforms.uAspect, w / Math.max(1, h));
    gl.uniform1f(uniforms.uCamZ, CAM_Z);
    gl.uniform1f(uniforms.uViewportH, h);
    gl.uniform1f(uniforms.uPointScale, 0.022);
    gl.uniform1f(uniforms.uPassAlpha, 0.2);
    gl.drawArrays(gl.POINTS, 0, PARTICLE_COUNT);
    gl.uniform1f(uniforms.uPointScale, 0.0105);
    gl.uniform1f(uniforms.uPassAlpha, 0.72);
    gl.drawArrays(gl.POINTS, 0, PARTICLE_COUNT);
  }

  function renderWebGL(pose) {
    const w = canvas.width;
    const h = canvas.height;
    if (bloom) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, bloom.scene.fb);
      gl.viewport(0, 0, bloom.scene.w, bloom.scene.h);
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      paintPoints(pose, bloom.scene.w, bloom.scene.h);
      gl.disable(gl.BLEND);
      gl.useProgram(blurProg);
      bindClip();
      gl.uniform1i(blurLoc.uTex, 0);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindFramebuffer(gl.FRAMEBUFFER, bloom.a.fb);
      gl.viewport(0, 0, bloom.a.w, bloom.a.h);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bindTexture(gl.TEXTURE_2D, bloom.scene.tex);
      gl.uniform2f(blurLoc.uDir, 1.8 / bloom.scene.w, 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.bindFramebuffer(gl.FRAMEBUFFER, bloom.b.fb);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bindTexture(gl.TEXTURE_2D, bloom.a.tex);
      gl.uniform2f(blurLoc.uDir, 0, 1.8 / bloom.a.h);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, w, h);
      gl.useProgram(copyProg);
      bindClip();
      gl.uniform1i(copyLoc.uSharp, 0);
      gl.uniform1i(copyLoc.uGlow, 1);
      gl.uniform1f(copyLoc.uBloom, 0.4 + level * 0.75);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, bloom.scene.tex);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, bloom.b.tex);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.activeTexture(gl.TEXTURE0);
      return;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, w, h);
    gl.clear(gl.COLOR_BUFFER_BIT);
    paintPoints(pose, w, h);
  }

  function project2D(pose, energy) {
    const w = canvas.width;
    const h = canvas.height;
    const cx = w * 0.5;
    const cy = h * 0.5;
    const aspect = w / Math.max(1, h);
    const yaw = pose.yaw;
    const pitch = pose.pitch;
    const cyaw = Math.cos(yaw);
    const syaw = Math.sin(yaw);
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);
    const breath = Math.sin((reduce() ? 0.8 : clock) * 0.78) * 0.018 * pose.breath;
    const pos = sphere.pos;
    const seed = sphere.seed;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const x0 = pos[i * 3];
      const y0 = pos[i * 3 + 1];
      const z0 = pos[i * 3 + 2];
      const wobble = Math.sin(x0 * 2.2 + clock * 0.6) * Math.cos(y0 * 1.8 - clock * 0.35) * (0.012 + energy * 0.05);
      const rad = (0.945 + seed[i] * 0.055) * (1 + breath + energy * 0.046) + wobble;
      let x = x0 * rad;
      let y = y0 * rad;
      let z = z0 * rad;
      const xz = cyaw * x + syaw * z;
      z = -syaw * x + cyaw * z;
      x = xz;
      const y2 = cp * y - sp * z;
      z = sp * y + cp * z;
      y = y2;
      const dist = Math.max(0.4, CAM_Z - z);
      const closeness = Math.max(0, Math.min(1, ((z - CAM_Z) - (-CAM_Z - 1.08)) / 2.16));
      depthBuf[i] = dist;
      sphere._x = sphere._x || new Float32Array(PARTICLE_COUNT);
      sphere._y = sphere._y || new Float32Array(PARTICLE_COUNT);
      sphere._c = sphere._c || new Float32Array(PARTICLE_COUNT);
      sphere._x[i] = cx + ((x / dist) * FOCAL / aspect) * cx;
      sphere._y[i] = cy - ((y / dist) * FOCAL) * cy;
      sphere._c[i] = closeness;
    }
  }

  function render2D(pose) {
    const w = canvas.width;
    const h = canvas.height;
    project2D(pose, reduce() ? 0 : level);
    order.sort((a, b) => depthBuf[b] - depthBuf[a]);
    ctx2d.setTransform(1, 0, 0, 1, 0, 0);
    ctx2d.globalCompositeOperation = "source-over";
    ctx2d.fillStyle = "#000";
    ctx2d.fillRect(0, 0, w, h);
    ctx2d.globalCompositeOperation = "lighter";
    const px = sphere._x;
    const py = sphere._y;
    const pc = sphere._c;
    for (let k = 0; k < PARTICLE_COUNT; k++) {
      const i = order[k];
      const closeness = pc[i];
      const shade = 0.08 + 0.92 * Math.pow(closeness, 1.32);
      const size = (2.2 + shade * 5.4) * (0.55 + level * 0.35);
      ctx2d.globalAlpha = Math.max(0.04, Math.min(0.85, shade * glow));
      ctx2d.drawImage(sprite, px[i] - size, py[i] - size, size * 2, size * 2);
    }
    ctx2d.globalAlpha = 1;
    ctx2d.globalCompositeOperation = "source-over";
  }

  function render() {
    const pose = statePose();
    if (window.__orbMode === "webgl" && gl) renderWebGL(pose);
    else if (window.__orbMode === "2d" && ctx2d) render2D(pose);
  }

  function pumpDemo() {
    if (!demoCtx || !demoGain || !demoOsc) return;
    if (demoCtx.state === "suspended") demoCtx.resume();
    const opened = Math.max(0, Math.min(1, (clock - 2.3) / 1.1));
    const pulse = Math.pow(Math.max(0, Math.sin((clock - 2.3) * 1.45)), 1.55);
    const amp = 0.002 + opened * (0.04 + pulse * 0.46);
    demoGain.gain.setTargetAtTime(amp, demoCtx.currentTime, 0.05);
    demoOsc.frequency.setTargetAtTime(100 + opened * pulse * 240, demoCtx.currentTime, 0.07);
  }

  function frame(now) {
    if (document.hidden) {
      raf = null;
      previous = 0;
      return;
    }
    const dt = previous ? Math.min(0.034, Math.max(0, now - previous) / 1000) : 0.016;
    previous = now;
    if (!reduce()) clock += dt;
    pumpDemo();
    const target = targetEnergy();
    const follow = target > level ? 8.5 : 3.8;
    const glide = 1 - Math.exp(-dt * follow);
    level += (target - level) * glide;
    ripple += ((target * 0.85) - ripple) * (1 - Math.exp(-dt * 5));
    const pose = statePose();
    glow += (pose.glowTarget - glow) * (1 - Math.exp(-dt * 4));
    window.__orbEnergy = level;
    render();
    if (reduce()) {
      raf = null;
      return;
    }
    raf = window.requestAnimationFrame(frame);
  }

  function start() {
    if (raf !== null || document.hidden) return;
    previous = 0;
    raf = window.requestAnimationFrame(frame);
  }

  function stop() {
    if (raf !== null) window.cancelAnimationFrame(raf);
    raf = null;
  }

  function startDemo() {
    let flag = "";
    try { flag = new URLSearchParams(window.location.search).get("orbdemo") || ""; }
    catch (error) { return; }
    if (flag !== "1") return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    try {
      demoCtx = new Ctx();
      demoAnalyser = demoCtx.createAnalyser();
      demoAnalyser.fftSize = 1024;
      demoAnalyser.smoothingTimeConstant = 0.55;
      demoOsc = demoCtx.createOscillator();
      demoGain = demoCtx.createGain();
      const mute = demoCtx.createGain();
      demoOsc.type = "triangle";
      demoOsc.frequency.value = 140;
      demoGain.gain.value = 0.02;
      mute.gain.value = 0;
      demoOsc.connect(demoGain);
      demoGain.connect(demoAnalyser);
      demoAnalyser.connect(mute);
      mute.connect(demoCtx.destination);
      demoOsc.start();
      window.__orbDemoCtx = demoCtx;
      demoCtx.resume();
    } catch (error) {
      demoCtx = null;
      demoAnalyser = null;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stop();
      if (demoCtx && demoCtx.state === "running") demoCtx.suspend();
      return;
    }
    if (demoCtx && demoCtx.state === "suspended") demoCtx.resume();
    if (reduce()) render();
    else start();
  });
  window.addEventListener("resize", resize, { passive: true });
  if (reduceQuery.addEventListener) {
    reduceQuery.addEventListener("change", () => {
      stop();
      clock = 0;
      level = 0;
      resize();
      render();
      start();
    });
  }
  if (window.ResizeObserver && canvas.parentElement) {
    const observer = new ResizeObserver(() => resize());
    observer.observe(canvas.parentElement);
  }

  try {
    if (!bootWebGL()) boot2D();
  } catch (error) {
    window.__orbError = String(error && error.message || error);
    try { boot2D(); } catch (fallbackError) { window.__orbMode = "failed"; }
  }
  startDemo();
  resize();
  render();
  start();
})();
