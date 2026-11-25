/**
 * Three.js r128 3D 点云主视图：
 * - 自定义点精灵 ShaderMaterial（柔光圆点 + 景深尺寸/淡出 + 5 种着色）
 * - 地面网格 & 配平显示平面（不修改原始判据）
 * - 目标 3D 包围盒、几何骨架（非人体关节）、轨迹尾迹、微型坐标轴指示器
 * - 5 种视角预设 + 平滑 cubic 补间 + 跟随目标
 */

import {
  computeLevelMatrixColMajor,
  computePresetPose,
  easeOutCubic,
  lerpVec3,
  rawPointToWorld,
  translateFallState,
} from "./studio_lib.js";

const MAX_POINTS = 65536;
const MAX_TRAIL_FRAMES = 50;

const VERT_SHADER = `
  attribute float aIntensity;
  attribute float aFlag;
  uniform mat4 uLevelMatrix;
  uniform float uBaseSize;
  uniform int uColorMode;
  varying vec3 vColor;
  varying float vAlpha;

  vec3 heightRamp(float h) {
    float t = clamp(h / 2.1, 0.0, 1.0);
    if (t < 0.35) return mix(vec3(0.16, 0.48, 0.88), vec3(0.22, 0.85, 0.66), t / 0.35);
    if (t < 0.72) return mix(vec3(0.22, 0.85, 0.66), vec3(0.96, 0.78, 0.28), (t - 0.35) / 0.37);
    return mix(vec3(0.96, 0.78, 0.28), vec3(1.0, 0.36, 0.42), (t - 0.72) / 0.28);
  }

  vec3 rangeRamp(float d) {
    float t = clamp((d - 0.1) / 7.9, 0.0, 1.0);
    return vec3(1.0 - t, 1.0 - abs(2.0 * t - 1.0), t);
  }

  vec3 intensityRamp(float inten) {
    float t = clamp(inten / 1000.0, 0.0, 1.0);
    if (t < 0.5) return mix(vec3(0.18, 0.32, 0.58), vec3(0.24, 0.80, 0.88), t / 0.5);
    return mix(vec3(0.24, 0.80, 0.88), vec3(1.0, 0.92, 0.58), (t - 0.5) / 0.5);
  }

  void main() {
    vec4 worldPos = uLevelMatrix * vec4(position, 1.0);
    vec4 mvPos = modelViewMatrix * worldPos;
    gl_Position = projectionMatrix * mvPos;

    int fl = int(aFlag + 0.5);
    bool isTarget = (fl == 1 || fl == 3 || fl == 5 || fl == 7 || fl == 9 || fl == 11 || fl == 13 || fl == 15);
    // 用浮点取模兼容 WebGL1 无位运算限制
    float f = floor(aFlag + 0.5);
    bool bTarget = mod(f, 2.0) >= 0.5;
    bool bRec = mod(floor(f / 2.0), 2.0) >= 0.5;
    bool bOther = mod(floor(f / 4.0), 2.0) >= 0.5;
    bool bFg = mod(floor(f / 8.0), 2.0) >= 0.5;

    float depth = max(0.8, -mvPos.z);
    float boost = (bTarget || bRec) ? 1.42 : (bOther ? 1.18 : 1.0);
    gl_PointSize = clamp(uBaseSize * boost * (5.2 / depth), 2.0, 18.0);

    float distFade = 1.0 - smoothstep(6.5, 13.5, length(position));
    vAlpha = (bTarget || bRec || bOther) ? 0.98 : mix(0.28, 0.78, distFade);

    if (uColorMode == 0) {
      vColor = heightRamp(worldPos.y);
      if (bTarget) vColor = mix(vColor, vec3(0.32, 1.0, 0.76), 0.35);
      else if (bRec) vColor = vec3(1.0, 0.76, 0.24);
    } else if (uColorMode == 1) {
      vColor = rangeRamp(length(position));
    } else if (uColorMode == 2) {
      vColor = intensityRamp(aIntensity);
    } else if (uColorMode == 3) {
      if (bTarget) vColor = vec3(0.22, 0.96, 0.70);
      else if (bRec) vColor = vec3(1.0, 0.76, 0.24);
      else if (bOther) vColor = vec3(0.36, 0.72, 1.0);
      else if (bFg) vColor = vec3(0.38, 0.62, 0.72);
      else {
        vColor = vec3(0.27, 0.37, 0.50);
        vAlpha *= 0.55;
      }
    } else {
      // 模式 4：突出局部回收新增点
      if (bRec) vColor = vec3(1.0, 0.82, 0.25);
      else if (bTarget) vColor = vec3(0.22, 0.86, 0.92);
      else {
        vColor = vec3(0.22, 0.29, 0.38);
        vAlpha *= 0.42;
      }
    }
  }
`;

const FRAG_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    vec2 uv = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(uv, uv);
    if (r2 > 1.0) discard;
    float halo = 1.0 - smoothstep(0.25, 1.0, r2);
    float core = exp(-r2 * 4.2);
    vec3 col = vColor * (0.72 + 0.55 * core);
    gl_FragColor = vec4(col, halo * vAlpha);
  }
`;

const COLOR_MODE_INDEX = {
  height: 0,
  range: 1,
  intensity: 2,
  target: 3,
  recovery: 4,
};

const COLOR_LEGEND_META = {
  height: {
    title: "高度着色",
    range: "0.0 – 2.1 m",
    bg: "linear-gradient(90deg, #297ae0 0%, #38d9a9 35%, #f5c747 72%, #ff5c6c 100%)",
  },
  range: {
    title: "径向距离着色",
    range: "0.1 – 8.0 m",
    bg: "linear-gradient(90deg, #ff3b30 0%, #4ade80 50%, #3b82f6 100%)",
  },
  intensity: {
    title: "反射强度着色",
    range: "0 – 1000（无单位）",
    bg: "linear-gradient(90deg, #2e5294 0%, #3dcce0 50%, #ffeb94 100%)",
  },
  target: {
    title: "目标高亮着色",
    range: "绿=核心 · 金=回收 · 蓝=他轨",
    bg: "linear-gradient(90deg, #455e80 0%, #5cb8ff 45%, #ffbe3b 72%, #38f5b8 100%)",
  },
  recovery: {
    title: "局部回收新增",
    range: "金=新增肢体点 · 青=核心",
    bg: "linear-gradient(90deg, #384a61 0%, #38dce8 55%, #ffd147 100%)",
  },
};

export class View3D {
  constructor(mountEl, axisCanvas) {
    this.mountEl = mountEl;
    this.axisCanvas = axisCanvas;
    this.axisCtx = axisCanvas ? axisCanvas.getContext("2d") : null;
    this.THREE = window.THREE;
    this.supported = false;

    this.colorMode = "height";
    this.useLeveling = true;
    this.followTarget = false;
    this.showSkeleton = true;
    this.showBbox = true;
    this.showTrail = true;

    this.displayPlane = null;
    this.lastFrame = null;
    this.timeline = [];
    this.liveTrail = [];
    this.liveTrailKey = null;
    this.currentFrameIdx = 0;

    this.tween = null;
    this.activePreset = "free";
    this.lastTargetWorld = [2.5, 0.9, 0.0];
    this._hasAutoFramed = false;

    this._fpsFrames = 0;
    this._fpsLast = performance.now();
    this.currentFps = 0;

    this._initScene();
  }

  _initScene() {
    const THREE = this.THREE;
    if (!THREE) {
      this._showFallback("Three.js 脚本未加载");
      return;
    }

    try {
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      });
    } catch (err) {
      this._showFallback(`WebGL 初始化失败: ${err.message}`);
      return;
    }

    this.supported = true;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x060a10, 1);
    this.mountEl.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(48, 16 / 9, 0.05, 80);
    this.camera.position.set(5.4, 2.7, -3.4);

    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(2.4, 0.85, 0);
    this.controls.maxDistance = 30;
    this.controls.minDistance = 0.4;
    this.controls.addEventListener("start", () => {
      this.tween = null;
    });

    // 地面网格与距离圆环
    this.gridGroup = new THREE.Group();
    const grid = new THREE.GridHelper(16, 32, 0x26445e, 0x122030);
    grid.position.set(2.5, 0, 0);
    this.gridGroup.add(grid);

    const planeGeo = new THREE.PlaneGeometry(16, 16);
    planeGeo.rotateX(-Math.PI / 2);
    const planeMat = new THREE.MeshBasicMaterial({
      color: 0x0e2a40,
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    this.groundDisc = new THREE.Mesh(planeGeo, planeMat);
    this.groundDisc.position.set(2.5, -0.002, 0);
    this.gridGroup.add(this.groundDisc);

    // 2/4/6/8 m 同心圆环
    for (const r of [2, 4, 6, 8]) {
      const segs = 64;
      const pts = [];
      for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * r, 0.004, Math.sin(a) * r));
      }
      const rg = new THREE.BufferGeometry().setFromPoints(pts);
      const rm = new THREE.LineBasicMaterial({ color: 0x1e3a52, transparent: true, opacity: 0.5 });
      this.gridGroup.add(new THREE.Line(rg, rm));
    }
    this.scene.add(this.gridGroup);

    // 传感器原点锥体
    const sensorGeo = new THREE.ConeGeometry(0.11, 0.24, 4);
    sensorGeo.rotateZ(-Math.PI / 2);
    this.sensorMarker = new THREE.Mesh(
      sensorGeo,
      new THREE.MeshBasicMaterial({ color: 0x58b4ff, wireframe: true })
    );
    this.scene.add(this.sensorMarker);

    // 点云预分配缓冲
    this.posArr = new Float32Array(MAX_POINTS * 3);
    this.intenArr = new Float32Array(MAX_POINTS);
    this.flagArr = new Float32Array(MAX_POINTS);

    this.cloudGeo = new THREE.BufferGeometry();
    this.posAttr = new THREE.BufferAttribute(this.posArr, 3);
    this.intenAttr = new THREE.BufferAttribute(this.intenArr, 1);
    this.flagAttr = new THREE.BufferAttribute(this.flagArr, 1);
    this.cloudGeo.setAttribute("position", this.posAttr);
    this.cloudGeo.setAttribute("aIntensity", this.intenAttr);
    this.cloudGeo.setAttribute("aFlag", this.flagAttr);
    this.cloudGeo.setDrawRange(0, 0);

    this.levelMat4 = new THREE.Matrix4();
    this.cloudMat = new THREE.ShaderMaterial({
      vertexShader: VERT_SHADER,
      fragmentShader: FRAG_SHADER,
      transparent: true,
      depthWrite: true,
      uniforms: {
        uLevelMatrix: { value: this.levelMat4 },
        uBaseSize: { value: 6.5 },
        uColorMode: { value: 0 },
      },
    });
    this.cloudPoints = new THREE.Points(this.cloudGeo, this.cloudMat);
    this.cloudPoints.frustumCulled = false;
    this.scene.add(this.cloudPoints);

    // 目标 3D 包围盒（12 条边 = 24 个顶点）
    this.bboxVerts = new Float32Array(24 * 3);
    this.bboxGeo = new THREE.BufferGeometry();
    this.bboxAttr = new THREE.BufferAttribute(this.bboxVerts, 3);
    this.bboxGeo.setAttribute("position", this.bboxAttr);
    this.bboxMat = new THREE.LineBasicMaterial({ color: 0x38d9a9 });
    this.bboxLines = new THREE.LineSegments(this.bboxGeo, this.bboxMat);
    this.bboxLines.visible = false;
    this.bboxLines.frustumCulled = false;
    this.scene.add(this.bboxLines);

    // 几何骨架组（节点球池 + 连线）
    this.skelGroup = new THREE.Group();
    this.skelNodes = {};
    this.skelSphereGeo = new THREE.SphereGeometry(0.036, 12, 12);
    this.skelCoreMat = new THREE.MeshBasicMaterial({ color: 0x4ef2c8 });
    this.skelBranchMat = new THREE.MeshBasicMaterial({ color: 0x58b4ff });
    this.skelLineVerts = new Float32Array(32 * 2 * 3);
    this.skelLineGeo = new THREE.BufferGeometry();
    this.skelLineAttr = new THREE.BufferAttribute(this.skelLineVerts, 3);
    this.skelLineGeo.setAttribute("position", this.skelLineAttr);
    this.skelLines = new THREE.LineSegments(
      this.skelLineGeo,
      new THREE.LineBasicMaterial({ color: 0x7ef7db })
    );
    this.skelLines.frustumCulled = false;
    this.skelGroup.add(this.skelLines);
    this.scene.add(this.skelGroup);

    // 轨迹尾迹
    this.trailVerts = new Float32Array(MAX_TRAIL_FRAMES * 3);
    this.trailColors = new Float32Array(MAX_TRAIL_FRAMES * 3);
    this.trailGeo = new THREE.BufferGeometry();
    this.trailPosAttr = new THREE.BufferAttribute(this.trailVerts, 3);
    this.trailColAttr = new THREE.BufferAttribute(this.trailColors, 3);
    this.trailGeo.setAttribute("position", this.trailPosAttr);
    this.trailGeo.setAttribute("color", this.trailColAttr);
    this.trailLine = new THREE.Line(
      this.trailGeo,
      new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 })
    );
    this.trailLine.frustumCulled = false;
    this.scene.add(this.trailLine);

    this.resize();
    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(this.mountEl);

    this._animate = this._animate.bind(this);
    requestAnimationFrame(this._animate);
  }

  _showFallback(msg) {
    this.mountEl.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#9cb0c9;font-size:13px">${msg}</div>`;
  }

  resize() {
    if (!this.supported) return;
    const w = Math.max(1, this.mountEl.clientWidth);
    const h = Math.max(1, this.mountEl.clientHeight);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  setColorMode(mode) {
    this.colorMode = mode;
    if (this.supported) {
      this.cloudMat.uniforms.uColorMode.value = COLOR_MODE_INDEX[mode] ?? 0;
    }
    return COLOR_LEGEND_META[mode] || COLOR_LEGEND_META.height;
  }

  setLeveling(enabled) {
    this.useLeveling = Boolean(enabled);
    this._refreshGeometryOverlays();
  }

  setFollowTarget(enabled) {
    this.followTarget = Boolean(enabled);
  }

  setShowSkeleton(enabled) {
    this.showSkeleton = Boolean(enabled);
    if (this.skelGroup) this.skelGroup.visible = this.showSkeleton;
  }

  setShowBbox(enabled) {
    this.showBbox = Boolean(enabled);
    if (this.bboxLines) this.bboxLines.visible = this.showBbox && this._hasBbox;
  }

  setShowTrail(enabled) {
    this.showTrail = Boolean(enabled);
    if (this.trailLine) this.trailLine.visible = this.showTrail;
  }

  setTimeline(timeline) {
    this.timeline = Array.isArray(timeline) ? timeline : [];
    this._hasAutoFramed = false;
  }

  setPreset(preset) {
    if (!this.supported) return;
    this.activePreset = preset;
    const sensorW = rawPointToWorld(0, 0, 0, this.displayPlane, this.useLeveling);
    const pose = computePresetPose(preset, this.lastTargetWorld, sensorW, 4.4);
    this.tween = {
      startTime: performance.now(),
      duration: 340,
      fromPos: [this.camera.position.x, this.camera.position.y, this.camera.position.z],
      toPos: pose.position,
      fromTarget: [this.controls.target.x, this.controls.target.y, this.controls.target.z],
      toTarget: pose.target,
    };
  }

  updateFrame(decoded) {
    this.lastFrame = decoded;
    if (!this.supported) return;

    const st = decoded.state || {};
    const lr = st.local_range || {};
    this.displayPlane = (lr.ground && lr.ground.displayPlane) || null;
    this.currentFrameIdx = Number(st.frame_index || 0);

    if (st.mode === "live") {
      const key = `${st.session_id || ""}:${st.time_epoch ?? 0}:${st.track_id || ""}`;
      if (!st.track_id || key !== this.liveTrailKey) {
        this.liveTrail = [];
        this.liveTrailKey = st.track_id ? key : null;
      }
      if (st.track_id && lr.bbox) {
        this.liveTrail.push({
          center_raw: lr.bbox.raw?.center || null,
          center_leveled: lr.bbox.leveled?.center || null,
        });
        if (this.liveTrail.length > MAX_TRAIL_FRAMES) {
          this.liveTrail.shift();
        }
      }
    } else if (this.liveTrail.length) {
      this.liveTrail = [];
      this.liveTrailKey = null;
    }

    const n = Math.min(decoded.pointCount, MAX_POINTS);
    this.posArr.set(decoded.xyz.subarray(0, n * 3), 0);
    if (decoded.intensity) {
      this.intenArr.set(decoded.intensity.subarray(0, n), 0);
    } else {
      this.intenArr.fill(400, 0, n);
    }
    for (let i = 0; i < n; i++) {
      this.flagArr[i] = decoded.pointFlags[i];
    }
    this.posAttr.needsUpdate = true;
    this.intenAttr.needsUpdate = true;
    this.flagAttr.needsUpdate = true;
    this.cloudGeo.setDrawRange(0, n);

    this._refreshGeometryOverlays();
  }

  _refreshGeometryOverlays() {
    if (!this.supported || !this.lastFrame) return;
    const st = this.lastFrame.state || {};
    const lr = st.local_range || {};
    const plane = this.displayPlane;
    const leveled = this.useLeveling && Boolean(plane);

    this.levelMat4.fromArray(computeLevelMatrixColMajor(plane, leveled));
    this.gridGroup.visible = true;
    this.groundDisc.visible = leveled;

    const sw = rawPointToWorld(0, 0, 0, plane, leveled);
    this.sensorMarker.position.set(sw[0], sw[1], sw[2]);

    // 更新目标包围盒（直接使用 raw 8 角点逐个经 rawPointToWorld 变换，保证配平/原始一致）
    const bboxRaw = lr.bbox && lr.bbox.raw;
    const bboxLev = lr.bbox && lr.bbox.leveled;
    const activeBox = leveled && bboxLev ? bboxLev : bboxRaw;
    this._hasBbox = Boolean(activeBox);
    if (activeBox) {
      let lo, hi;
      if (leveled && bboxLev) {
        // bboxLev 为地面系 (x_fwd, y_left, z_up) -> Three.js (x_fwd, z_up, -y_left)
        lo = [bboxLev.min[0], bboxLev.min[2], -bboxLev.max[1]];
        hi = [bboxLev.max[0], bboxLev.max[2], -bboxLev.min[1]];
      } else {
        lo = [bboxRaw.min[0], bboxRaw.min[2], -bboxRaw.max[1]];
        hi = [bboxRaw.max[0], bboxRaw.max[2], -bboxRaw.min[1]];
      }
      const corners = [
        [lo[0], lo[1], lo[2]],
        [hi[0], lo[1], lo[2]],
        [hi[0], hi[1], lo[2]],
        [lo[0], hi[1], lo[2]],
        [lo[0], lo[1], hi[2]],
        [hi[0], lo[1], hi[2]],
        [hi[0], hi[1], hi[2]],
        [lo[0], hi[1], hi[2]],
      ];
      const edges = [
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
      ];
      let k = 0;
      for (const [a, b] of edges) {
        this.bboxVerts[k++] = corners[a][0];
        this.bboxVerts[k++] = corners[a][1];
        this.bboxVerts[k++] = corners[a][2];
        this.bboxVerts[k++] = corners[b][0];
        this.bboxVerts[k++] = corners[b][1];
        this.bboxVerts[k++] = corners[b][2];
      }
      this.bboxAttr.needsUpdate = true;
      const fallColor = translateFallState(st.fall_status).color || "#38d9a9";
      this.bboxMat.color.set(fallColor);
      this.bboxLines.visible = this.showBbox;

      const nextCenter = [
        (lo[0] + hi[0]) * 0.5,
        (lo[1] + hi[1]) * 0.5,
        (lo[2] + hi[2]) * 0.5,
      ];
      if (this.followTarget && !this.tween) {
        const dx = nextCenter[0] - this.controls.target.x;
        const dy = nextCenter[1] - this.controls.target.y;
        const dz = nextCenter[2] - this.controls.target.z;
        this.controls.target.x += dx * 0.22;
        this.controls.target.y += dy * 0.22;
        this.controls.target.z += dz * 0.22;
        this.camera.position.x += dx * 0.22;
        this.camera.position.y += dy * 0.22;
        this.camera.position.z += dz * 0.22;
      }
      this.lastTargetWorld = nextCenter;
      if (!this._hasAutoFramed) {
        this._hasAutoFramed = true;
        const sensorW = rawPointToWorld(0, 0, 0, plane, leveled);
        const pose = computePresetPose(this.activePreset, nextCenter, sensorW, 4.4);
        this.camera.position.set(pose.position[0], pose.position[1], pose.position[2]);
        this.controls.target.set(pose.target[0], pose.target[1], pose.target[2]);
        this.controls.update();
      }
    } else {
      this.bboxLines.visible = false;
    }

    // 更新几何骨架
    const skel = lr.skeleton || {};
    const nodes = skel.nodes || {};
    const edges = skel.edges || [];
    for (const mesh of Object.values(this.skelNodes)) {
      mesh.visible = false;
    }
    const worldNodes = {};
    for (const [name, node] of Object.entries(nodes)) {
      if (!node || !Array.isArray(node.xyz)) continue;
      const wp = rawPointToWorld(node.xyz[0], node.xyz[1], node.xyz[2], plane, leveled);
      worldNodes[name] = wp;
      let mesh = this.skelNodes[name];
      if (!mesh) {
        const isSpine = name === "TOP" || name === "UPPER" || name === "CENTER" || name === "BASE";
        mesh = new THREE.Mesh(this.skelSphereGeo, isSpine ? this.skelCoreMat : this.skelBranchMat);
        this.skelNodes[name] = mesh;
        this.skelGroup.add(mesh);
      }
      mesh.position.set(wp[0], wp[1], wp[2]);
      mesh.visible = true;
    }
    let eIdx = 0;
    for (const [a, b] of edges) {
      const pa = worldNodes[a];
      const pb = worldNodes[b];
      if (!pa || !pb || eIdx + 6 > this.skelLineVerts.length) continue;
      this.skelLineVerts[eIdx++] = pa[0];
      this.skelLineVerts[eIdx++] = pa[1];
      this.skelLineVerts[eIdx++] = pa[2];
      this.skelLineVerts[eIdx++] = pb[0];
      this.skelLineVerts[eIdx++] = pb[1];
      this.skelLineVerts[eIdx++] = pb[2];
    }
    this.skelLineAttr.needsUpdate = true;
    this.skelLineGeo.setDrawRange(0, eIdx / 3);
    this.skelGroup.visible = this.showSkeleton;

    // 更新轨迹尾迹（回放读 timeline，实时读 liveTrail）
    const trailSrc = st.mode === "live" ? this.liveTrail : this.timeline;
    if (this.showTrail && trailSrc.length > 0) {
      const end = st.mode === "live" ? trailSrc.length - 1 : Math.min(trailSrc.length - 1, this.currentFrameIdx);
      const start = Math.max(0, end - MAX_TRAIL_FRAMES + 1);
      let count = 0;
      for (let i = start; i <= end; i++) {
        const row = trailSrc[i];
        const c = leveled && row.center_leveled ? row.center_leveled : row.center_raw;
        if (!c) continue;
        let wx, wy, wz;
        if (leveled && row.center_leveled) {
          wx = c[0];
          wy = c[2];
          wz = -c[1];
        } else {
          const wp = rawPointToWorld(c[0], c[1], c[2], null, false);
          wx = wp[0];
          wy = wp[1];
          wz = wp[2];
        }
        const frac = (i - start + 1) / Math.max(1, end - start + 1);
        this.trailVerts[count * 3] = wx;
        this.trailVerts[count * 3 + 1] = wy;
        this.trailVerts[count * 3 + 2] = wz;
        this.trailColors[count * 3] = 0.2 * frac;
        this.trailColors[count * 3 + 1] = 0.85 * frac;
        this.trailColors[count * 3 + 2] = 0.72 * frac;
        count++;
      }
      this.trailPosAttr.needsUpdate = true;
      this.trailColAttr.needsUpdate = true;
      this.trailGeo.setDrawRange(0, count);
      this.trailLine.visible = count >= 2;
    } else {
      this.trailLine.visible = false;
    }
  }

  _drawAxisHud() {
    if (!this.axisCtx || !this.supported) return;
    const ctx = this.axisCtx;
    const w = this.axisCanvas.width;
    const h = this.axisCanvas.height;
    ctx.clearRect(0, 0, w, h);

    const invQuat = this.camera.quaternion.clone().invert();
    const axes = [
      { label: "X 前", vec: new this.THREE.Vector3(1, 0, 0), color: "#ff6b7a" },
      { label: "Y 左", vec: new this.THREE.Vector3(0, 0, -1), color: "#38d9a9" },
      { label: "Z 上", vec: new this.THREE.Vector3(0, 1, 0), color: "#58b4ff" },
    ];
    const cx = w * 0.5;
    const cy = h * 0.54;
    const scale = 34;

    const projected = axes.map((ax) => {
      const v = ax.vec.clone().applyQuaternion(invQuat);
      return { ...ax, px: cx + v.x * scale, py: cy - v.y * scale, depth: v.z };
    });
    projected.sort((a, b) => a.depth - b.depth);

    ctx.lineWidth = 2;
    ctx.font = "bold 11px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const ax of projected) {
      ctx.strokeStyle = ax.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(ax.px, ax.py);
      ctx.stroke();

      ctx.fillStyle = ax.color;
      ctx.beginPath();
      ctx.arc(ax.px, ax.py, 2.5, 0, Math.PI * 2);
      ctx.fill();

      const lx = cx + (ax.px - cx) * 1.28;
      const ly = cy + (ax.py - cy) * 1.28;
      ctx.fillText(ax.label, lx, ly);
    }
  }

  _animate(now) {
    if (!this.supported) return;
    if (this.tween) {
      const rawT = (now - this.tween.startTime) / this.tween.duration;
      const k = easeOutCubic(rawT);
      const pos = lerpVec3(this.tween.fromPos, this.tween.toPos, k);
      const tgt = lerpVec3(this.tween.fromTarget, this.tween.toTarget, k);
      this.camera.position.set(pos[0], pos[1], pos[2]);
      this.controls.target.set(tgt[0], tgt[1], tgt[2]);
      if (rawT >= 1) this.tween = null;
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this._drawAxisHud();

    this._fpsFrames++;
    if (now - this._fpsLast >= 500) {
      this.currentFps = (this._fpsFrames * 1000) / (now - this._fpsLast);
      this._fpsFrames = 0;
      this._fpsLast = now;
    }
    requestAnimationFrame(this._animate);
  }
}
