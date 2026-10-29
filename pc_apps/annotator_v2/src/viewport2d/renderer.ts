// viewport2d/renderer.ts — 绘制函数（Canvas2D）。分两层：
// 底图 = 点云（帧/视图变化才重绘）；覆盖层 = 框/柄/预览（交互帧重绘，轻量）。
// 显示抽稀（displayStride）只发生在这里；统计/命中/保存一律用完整数组。
import type { Box, Person } from "../domain/types.ts";
import { displayStride } from "../domain/geometry.ts";
import type { DecodedFrame } from "../session/types.ts";
import type { Preview, Tool } from "./interaction.ts";
import { worldToScreen, type ViewTransform } from "./transform.ts";

export interface RenderStyle {
  background: string;
  gridMajor: string;
  pointBase: string;
  zTintLow: [number, number, number]; // z 低端 RGB
  zTintHigh: [number, number, number];
  boxStroke: (personColor: string | null, selected: boolean) => string;
  handleFill: string;
  previewStroke: string;
  suggestStroke: string;
  maxDisplayPoints: number;
}

export const defaultStyle: RenderStyle = {
  background: "#101418",
  gridMajor: "rgba(255,255,255,0.08)",
  pointBase: "#7fd4a0",
  zTintLow: [80, 140, 220],
  zTintHigh: [255, 120, 90],
  boxStroke: (c, selected) => (selected ? "#ffffff" : c ?? "#e8b339"),
  handleFill: "#ffffff",
  previewStroke: "#4dd0e1",
  suggestStroke: "#b39ddb",
  maxDisplayPoints: 120000,
};

export function zTintRgb(z: number, zMin: number, zMax: number, style: RenderStyle): [number, number, number] {
  const t = Math.max(0, Math.min(1, zMax === zMin ? 0.5 : (z - zMin) / (zMax - zMin)));
  const a = style.zTintLow, b = style.zTintHigh;
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

export function zTint(z: number, zMin: number, zMax: number, style: RenderStyle): string {
  const [r, g, b] = zTintRgb(z, zMin, zMax, style);
  return `rgb(${r},${g},${b})`;
}

const POINT_LEVELS = 24;
const PALETTE = new Uint32Array(POINT_LEVELS);

function pointPalette(style: RenderStyle): Uint32Array {
  for (let i = 0; i < POINT_LEVELS; i++) {
    const [r, g, b] = zTintRgb((i + 0.5) / POINT_LEVELS, 0, 1, style);
    // Uint32 视图按小端写 RGBA；浏览器平台均为小端。
    PALETTE[i] = (0xff << 24) | (b << 16) | (g << 8) | r;
  }
  return PALETTE;
}

/**
 * 把点云画进一张 CSS 分辨率的 RGBA 像素缓冲。与逐点 fillStyle+fillRect 等价，
 * 但 49k 点只需一次 putImageData（同一台机器实测 ~109ms → ~3ms）。
 * 纯函数：不依赖 DOM，便于在 node 里断言像素。
 */
export function paintPointImage(
  pixels: Uint32Array,
  width: number,
  height: number,
  frame: DecodedFrame,
  t: ViewTransform,
  style: RenderStyle,
): void {
  pixels.fill(0);
  const n = frame.count;
  const stride = displayStride(n, style.maxDisplayPoints);
  const zMin = zArrMin(frame.z, stride);
  const zMax = zArrMax(frame.z, stride);
  const palette = pointPalette(style);
  const size = stride > 1 ? 1 : 2;
  const half = size / 2;
  for (let i = 0; i < n; i += stride) {
    const sx = Math.round(t.canvasW / 2 + (frame.x[i]! - t.cx) * t.scalePxPerM - half);
    const sy = Math.round(t.canvasH / 2 - (frame.y[i]! - t.cy) * t.scalePxPerM - half);
    if (sx + size <= 0 || sy + size <= 0 || sx >= width || sy >= height) continue;
    let level = Math.floor(((frame.z[i]! - zMin) / (zMax - zMin)) * POINT_LEVELS);
    if (!Number.isFinite(level)) level = POINT_LEVELS >> 1;
    level = Math.max(0, Math.min(POINT_LEVELS - 1, level));
    const color = palette[level]!;
    const x0 = Math.max(0, sx), x1 = Math.min(width, sx + size);
    const y0 = Math.max(0, sy), y1 = Math.min(height, sy + size);
    for (let y = y0; y < y1; y++) {
      const row = y * width;
      for (let x = x0; x < x1; x++) pixels[row + x] = color;
    }
  }
}

interface PointSurface {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  image: ImageData;
  pixels: Uint32Array;
  w: number;
  h: number;
}

let surface: PointSurface | null = null;

/** 复用的离屏 2D 画布（点层）。浏览器外/取不到 2D 上下文时返回 null。 */
function pointSurface(w: number, h: number): PointSurface | null {
  if (surface && surface.w === w && surface.h === h) return surface;
  if (typeof document === "undefined" || typeof document.createElement !== "function") return null;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const image = ctx.createImageData(w, h);
    surface = { canvas, ctx, image, pixels: new Uint32Array(image.data.buffer), w, h };
    return surface;
  } catch {
    return null;
  }
}

/** 底图：点云 + 网格。只在帧/视图变化时调用（由组件的 rAF 合并器控制）。 */
export function drawBaseLayer(
  ctx: CanvasRenderingContext2D,
  t: ViewTransform,
  frame: DecodedFrame | null,
  style: RenderStyle,
): void {
  ctx.clearRect(0, 0, t.canvasW, t.canvasH);
  ctx.fillStyle = style.background;
  ctx.fillRect(0, 0, t.canvasW, t.canvasH);
  // 网格：每 1m
  ctx.strokeStyle = style.gridMajor;
  ctx.lineWidth = 1;
  const w0 = t.cx - t.canvasW / 2 / t.scalePxPerM;
  const w1 = t.cx + t.canvasW / 2 / t.scalePxPerM;
  const h0 = t.cy - t.canvasH / 2 / t.scalePxPerM;
  const h1 = t.cy + t.canvasH / 2 / t.scalePxPerM;
  ctx.beginPath();
  for (let gx = Math.floor(w0); gx <= Math.ceil(w1); gx++) {
    const s = worldToScreen(t, gx, 0);
    ctx.moveTo(s.sx, 0); ctx.lineTo(s.sx, t.canvasH);
  }
  for (let gy = Math.floor(h0); gy <= Math.ceil(h1); gy++) {
    const s = worldToScreen(t, 0, gy);
    ctx.moveTo(0, s.sy); ctx.lineTo(t.canvasW, s.sy);
  }
  ctx.stroke();
  if (!frame) return;
  // 原点标记（设备位置）
  const o = worldToScreen(t, 0, 0);
  ctx.fillStyle = "rgba(255,255,255,0.35)";
  ctx.beginPath(); ctx.arc(o.sx, o.sy, 4, 0, Math.PI * 2); ctx.fill();

  const w = Math.max(1, Math.ceil(t.canvasW));
  const h = Math.max(1, Math.ceil(t.canvasH));
  const surf = pointSurface(w, h);
  if (surf) {
    paintPointImage(surf.pixels, surf.w, surf.h, frame, t, style);
    surf.ctx.putImageData(surf.image, 0, 0);
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(surf.canvas, 0, 0, t.canvasW, t.canvasH);
    ctx.restore();
    return;
  }

  // 兜底（无 DOM）：逐点绘制，行为与旧版一致。
  const n = frame.count;
  const stride = displayStride(n, style.maxDisplayPoints);
  const zMin = zArrMin(frame.z, stride);
  const zMax = zArrMax(frame.z, stride);
  const size = stride > 1 ? 1 : 2;
  for (let i = 0; i < n; i += stride) {
    const sx = t.canvasW / 2 + (frame.x[i]! - t.cx) * t.scalePxPerM;
    const sy = t.canvasH / 2 - (frame.y[i]! - t.cy) * t.scalePxPerM;
    if (sx < -8 || sy < -8 || sx > t.canvasW + 8 || sy > t.canvasH + 8) continue;
    ctx.fillStyle = zTint(frame.z[i]!, zMin, zMax, style);
    ctx.fillRect(sx - size / 2, sy - size / 2, size, size);
  }
}

function zArrMin(z: Float32Array, stride: number): number {
  let m = Infinity;
  for (let i = 0; i < z.length; i += stride) { const v = z[i]!; if (v < m) m = v; }
  return Number.isFinite(m) ? m : 0;
}
function zArrMax(z: Float32Array, stride: number): number {
  let m = -Infinity;
  for (let i = 0; i < z.length; i += stride) { const v = z[i]!; if (v > m) m = v; }
  return Number.isFinite(m) ? m : 1;
}

export interface OverlayInput {
  boxes: Box[]; // 当前帧的框
  persons: Map<string, Person>;
  selection: string | null;
  preview: Preview;
  hoverBoxId: string | null;
  tool: Tool;
  suggestions: Array<{ x: number; y: number; w: number; h: number }>; // 世界系
}

/** 覆盖层：框 / 柄 / 预览 / 建议。每交互帧重绘（不碰点云）。 */
export function drawOverlayLayer(
  ctx: CanvasRenderingContext2D,
  t: ViewTransform,
  input: OverlayInput,
  style: RenderStyle,
): void {
  ctx.clearRect(0, 0, t.canvasW, t.canvasH);
  const px = (w: number) => w / metersPerPxScale(t);
  // 算法建议（虚线，仅显示）
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = style.suggestStroke;
  ctx.lineWidth = 1.5;
  for (const s of input.suggestions) {
    const c = worldToScreen(t, s.x, s.y);
    ctx.strokeRect(c.sx - px(s.w) / 2, c.sy - px(s.h) / 2, px(s.w), px(s.h));
  }
  ctx.setLineDash([]);
  // 框
  for (const b of input.boxes) {
    const isSel = b.boxId === input.selection;
    const color = style.boxStroke(input.persons.get(b.personId)?.color ?? null, isSel);
    const preview = input.preview && "boxId" in input.preview && input.preview.boxId === b.boxId ? input.preview : null;
    let geom = { x: b.x, y: b.y, w: b.w, h: b.h };
    if (preview && preview.kind === "moveBox") geom = { ...geom, x: preview.geom.x, y: preview.geom.y };
    if (preview && preview.kind === "resizeBox") geom = preview.geom;
    const c = worldToScreen(t, geom.x, geom.y);
    const rw = px(geom.w), rh = px(geom.h);
    ctx.strokeStyle = color;
    ctx.lineWidth = isSel ? 2.5 : 1.5;
    ctx.strokeRect(c.sx - rw / 2, c.sy - rh / 2, rw, rh);
    // 人物 id 标签
    const label = b.personId + (b.reviewed ? " ✓" : "");
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillStyle = color;
    ctx.fillText(label, c.sx - rw / 2, c.sy - rh / 2 - 4);
    // 选中框画柄
    if (isSel) {
      ctx.fillStyle = style.handleFill;
      for (const hx of [c.sx - rw / 2, c.sx, c.sx + rw / 2]) {
        for (const hy of [c.sy - rh / 2, c.sy, c.sy + rh / 2]) {
          if (hx === c.sx && hy === c.sy) continue; // 中心不放柄
          ctx.fillRect(hx - 3, hy - 3, 6, 6);
        }
      }
    }
  }
  // 画框预览（世界系矩形）
  if (input.preview && input.preview.kind === "drawRect") {
    const r = input.preview.rectPx;
    const c0 = worldToScreen(t, r.x, r.y + r.h); // 世界左下 → 屏幕左上
    const c1 = worldToScreen(t, r.x + r.w, r.y); // 世界右上 → 屏幕右下
    ctx.strokeStyle = style.previewStroke;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(Math.min(c0.sx, c1.sx), Math.min(c0.sy, c1.sy), Math.abs(c1.sx - c0.sx), Math.abs(c1.sy - c0.sy));
    ctx.setLineDash([]);
  }
  // 工具提示角标
  ctx.font = "12px ui-monospace, monospace";
  ctx.fillStyle = "rgba(255,255,255,0.55)";
  const toolName = input.tool === "draw" ? "画框" : input.tool === "pan" ? "平移" : "选择";
  ctx.fillText(`工具：${toolName}`, 8, t.canvasH - 8);
}

function metersPerPxScale(t: ViewTransform): number { return 1 / t.scalePxPerM; }
