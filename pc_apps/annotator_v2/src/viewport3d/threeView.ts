// viewport3d/threeView.ts — 三维视图：与 2D 共享同一份 DecodedFrame（不复制）；
// 几何缓冲预分配复用（drawRange 控制实际点数），关闭即停止渲染并释放资源。
// 渲染器工厂与 raf 驱动可注入——node 环境用假渲染器测资源生命周期。
import * as THREE from "three";
import type { DecodedFrame } from "../session/types.ts";
import type { BodyColorSet } from '../annotation/body.ts';

export interface RendererLike {
  render(scene: THREE.Scene, camera: THREE.Camera): void;
  setSize(w: number, h: number): void;
  dispose(): void;
}

export interface ThreeViewOptions {
  makeRenderer?: (canvas: HTMLCanvasElement) => RendererLike;
  schedule?: (cb: () => void) => void; // 默认 requestAnimationFrame
}

const INITIAL_CAPACITY = 65536;
const MAX_BOXES = 64; // 框线段缓冲容量（24 顶点/框）

export interface ThreeViewStats {
  running: boolean;
  disposed: boolean;
  pointCapacity: number;
  pointsDrawn: number;
  bufferReallocations: number;
  framesRendered: number;
}

export class ThreeView {
  private renderer: RendererLike;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private points: THREE.Points;
  private pointPositions: Float32Array;
  private pointColors: Float32Array;
  private pointCapacity = INITIAL_CAPACITY;
  private pointsDrawn = 0;
  private boxLines: THREE.LineSegments;
  private boxPositions: Float32Array;
  private boxesDrawn = 0;
  private rafHandle: ReturnType<typeof setTimeout> | null = null;
  private running = false;
  private disposedFlag = false;
  private reallocs = 0;
  private framesRendered = 0;
  private frame: DecodedFrame | null = null;
  private partByRow = new Map<number, string>();
  private bodyFocusedFrame: DecodedFrame | null = null;
  private bodyFocusedBounds = new THREE.Box3();
  private schedule: (cb: () => void) => void;

  // 局部视角状态（不进 React）
  private azimuth = Math.PI * 0.75;
  private polar = Math.PI / 3;
  private dist = 8;
  private target = new THREE.Vector3(1.5, 0, 1);

  constructor(canvas: HTMLCanvasElement, opts: ThreeViewOptions = {}) {
    this.schedule = opts.schedule ?? ((cb) => { requestAnimationFrame(cb); });
    this.renderer = opts.makeRenderer
      ? opts.makeRenderer(canvas)
      : new THREE.WebGLRenderer({ canvas, antialias: true }) as unknown as RendererLike;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0c1016);
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.05, 200);
    this.camera.up.set(0, 0, 1); // z 向上（传感器系）

    this.pointPositions = new Float32Array(INITIAL_CAPACITY * 3);
    this.pointColors = new Float32Array(INITIAL_CAPACITY * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(this.pointPositions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(this.pointColors, 3));
    geo.setDrawRange(0, 0);
    this.points = new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.025, vertexColors: true }));
    this.points.frustumCulled = false;
    this.scene.add(this.points);

    this.boxPositions = new Float32Array(MAX_BOXES * 24 * 3);
    const boxGeo = new THREE.BufferGeometry();
    boxGeo.setAttribute("position", new THREE.BufferAttribute(this.boxPositions, 3));
    boxGeo.setDrawRange(0, 0);
    this.boxLines = new THREE.LineSegments(boxGeo, new THREE.LineBasicMaterial({ color: 0xe8b339 }));
    this.boxLines.frustumCulled = false;
    this.scene.add(this.boxLines);

    this.updateCamera();
    this.renderer.setSize(canvas.clientWidth || 300, canvas.clientHeight || 300);
  }

  /** 共帧：直接从 DecodedFrame 填缓冲；容量不足按 2 倍扩（一次性，不是逐点分配）。 */
  setFrame(frame: DecodedFrame | null): void {
    this.frame = frame;
    this.partByRow.clear();
    if (!frame) {
      this.pointsDrawn = 0;
      this.points.geometry.setDrawRange(0, 0);
      return;
    }
    if (frame.count > this.pointCapacity) {
      this.reallocs += 1;
      while (this.pointCapacity < frame.count) this.pointCapacity *= 2;
      this.points.geometry.dispose(); // release old GPU attributes before capacity growth
      this.pointPositions = new Float32Array(this.pointCapacity * 3);
      this.pointColors = new Float32Array(this.pointCapacity * 3);
      this.points.geometry.setAttribute("position", new THREE.BufferAttribute(this.pointPositions, 3));
      this.points.geometry.setAttribute('color', new THREE.BufferAttribute(this.pointColors, 3));
    }
    const px = frame.x, py = frame.y, pz = frame.z;
    for (let i = 0; i < frame.count; i++) {
      const o = i * 3;
      this.pointPositions[o] = px[i]!;
      this.pointPositions[o + 1] = py[i]!;
      this.pointPositions[o + 2] = pz[i]!;
    }
    this.pointsDrawn = frame.count;
    this.points.geometry.setDrawRange(0, frame.count);
    (this.points.geometry.getAttribute("position") as THREE.BufferAttribute).needsUpdate = true;
    this.setBodyColors([]);
  }

  setBodyColors(groups: BodyColorSet[], focus = false): void {
    this.partByRow.clear();
    if (!this.frame) return;
    const colors = this.pointColors;
    const base = new THREE.Color(groups.length ? '#344455' : '#7fd4a0');
    for (let i = 0; i < this.frame.count; i++) base.toArray(colors, i*3);
    const box = new THREE.Box3();
    for (const group of groups) {
      const color = new THREE.Color(group.color);
      for (const row of group.sourceRows) {
        if (!Number.isInteger(row) || row < 0 || row >= this.frame.count || this.partByRow.has(row)) throw new Error('invalid body source row');
        this.partByRow.set(row, group.part); color.toArray(colors, row*3);
        box.expandByPoint(new THREE.Vector3(this.frame.x[row], this.frame.y[row], this.frame.z[row]));
      }
    }
    (this.points.geometry.getAttribute('color') as THREE.BufferAttribute).needsUpdate = true;
    if (focus && !box.isEmpty() && (this.bodyFocusedFrame !== this.frame || !this.bodyFocusedBounds.containsBox(box))) {
      box.getCenter(this.target);
      this.dist = Math.max(1, box.getSize(new THREE.Vector3()).length()*1.8);
      this.azimuth = Math.atan2(-this.target.y, -this.target.x);
      this.polar = Math.PI/2; // display sensor Z only; no gravity inference
      this.bodyFocusedFrame = this.frame;
      this.bodyFocusedBounds.copy(box);
      this.updateCamera();
    }
  }

  pickPart(x: number, y: number): string | null {
    const ray = new THREE.Raycaster();
    ray.params.Points = { threshold: .035 };
    this.camera.updateMatrixWorld(); this.points.updateMatrixWorld();
    // Vertex buffers are reused, so boundingSphere from the previous frame is stale.
    this.points.geometry.computeBoundingSphere();
    ray.setFromCamera(new THREE.Vector2(x, y), this.camera);
    const hit = ray.intersectObject(this.points)[0];
    return hit?.index === undefined ? null : this.partByRow.get(hit.index) ?? null;
  }

  /** 人物框（当前帧，世界系）：写入预分配线段缓冲。 */
  setBoxes(boxes: Array<{ x: number; y: number; w: number; h: number; zMin: number; zMax: number }>): void {
    const n = Math.min(boxes.length, MAX_BOXES);
    let v = 0;
    const put = (x: number, y: number, z: number) => {
      this.boxPositions[v] = x; this.boxPositions[v + 1] = y; this.boxPositions[v + 2] = z; v += 3;
    };
    for (let bi = 0; bi < n; bi++) {
      const b = boxes[bi]!;
      const x0 = b.x - b.w / 2, x1 = b.x + b.w / 2;
      const y0 = b.y - b.h / 2, y1 = b.y + b.h / 2;
      const z0 = b.zMin, z1 = b.zMax;
      const corners: Array<[number, number, number]> = [
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
      ];
      const edges: Array<[number, number]> = [
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
      ];
      for (const [a, bIdx] of edges) {
        const ca = corners[a]!, cb = corners[bIdx]!;
        put(ca[0], ca[1], ca[2]);
        put(cb[0], cb[1], cb[2]);
      }
    }
    this.boxesDrawn = n;
    this.boxLines.geometry.setDrawRange(0, n * 24);
    (this.boxLines.geometry.getAttribute("position") as THREE.BufferAttribute).needsUpdate = true;
  }

  setView(azimuth: number, polar: number, dist: number): void {
    this.azimuth = azimuth; this.polar = polar; this.dist = dist;
    this.updateCamera();
  }

  private updateCamera(): void {
    const sp = Math.sin(this.polar);
    this.camera.position.set(
      this.target.x + this.dist * sp * Math.cos(this.azimuth),
      this.target.y + this.dist * sp * Math.sin(this.azimuth),
      this.target.z + this.dist * Math.cos(this.polar),
    );
    this.camera.lookAt(this.target);
  }

  resize(w: number, h: number): void {
    this.camera.aspect = w / Math.max(1, h);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  renderOnce(): void {
    this.renderer.render(this.scene, this.camera);
    this.framesRendered += 1;
  }

  start(): void {
    if (this.running || this.disposedFlag) return;
    this.running = true;
    const tick = () => {
      if (!this.running) return;
      this.renderOnce();
      this.schedule(tick);
    };
    this.schedule(tick);
  }

  /** 关闭小窗：立即停止渲染循环（不再耗 GPU/CPU）。 */
  stop(): void {
    this.running = false;
  }

  /** 释放资源（关窗或组件卸载）。释放后对象不可再用。 */
  dispose(): void {
    this.stop();
    this.disposedFlag = true;
    this.points.geometry.dispose();
    (this.points.material as THREE.Material).dispose();
    this.boxLines.geometry.dispose();
    (this.boxLines.material as THREE.Material).dispose();
    this.renderer.dispose();
  }

  stats(): ThreeViewStats {
    return {
      running: this.running,
      disposed: this.disposedFlag,
      pointCapacity: this.pointCapacity,
      pointsDrawn: this.pointsDrawn,
      bufferReallocations: this.reallocs,
      framesRendered: this.framesRendered,
    };
  }
}

export { MAX_BOXES };
