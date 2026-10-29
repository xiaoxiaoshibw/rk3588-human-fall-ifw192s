// domain/geometry.ts — 纯几何函数（世界坐标，米；屏幕坐标，CSS 像素）。
import type { Box } from "./types.ts";

/** 8 个控制柄方位。 */
export type HandleKind =
  | "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

export interface RectPx { x: number; y: number; w: number; h: number } // 屏幕像素，左上角原点

export function boxToRectPx(box: Box, toScreen: (x: number, y: number) => { sx: number; sy: number }, mPerPx: number): RectPx {
  const c = toScreen(box.x, box.y);
  const wPx = box.w / mPerPx;
  const hPx = box.h / mPerPx;
  return { x: c.sx - wPx / 2, y: c.sy - hPx / 2, w: wPx, h: hPx };
}

/** 把拖动两点（屏幕像素）规范成最小宽高的正矩形（世界坐标，米）。 */
export function dragToBox(
  p0: { x: number; y: number }, p1: { x: number; y: number },
  toWorld: (sx: number, sy: number) => { x: number; y: number },
  minWm = 0.1, minHm = 0.1,
): { x: number; y: number; w: number; h: number } | null {
  const a = toWorld(p0.x, p0.y);
  const b = toWorld(p1.x, p1.y);
  const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
  const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
  const w = x1 - x0, h = y1 - y0;
  if (w < minWm || h < minHm) return null; // 过小视为无效框（单击/微动）
  return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, w, h };
}

export function pointInRectPx(px: number, py: number, r: RectPx): boolean {
  return px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h;
}

/** 命中控制柄：返回方位；handlePx 为命中半径（像素，已含触控余量）。 */
export function hitHandle(px: number, py: number, r: RectPx, handlePx: number): HandleKind | null {
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
  const nearL = Math.abs(px - r.x) <= handlePx;
  const nearR = Math.abs(px - (r.x + r.w)) <= handlePx;
  const nearT = Math.abs(py - r.y) <= handlePx;
  const nearB = Math.abs(py - (r.y + r.h)) <= handlePx;
  if (nearL && nearT) return "nw";
  if (nearR && nearT) return "ne";
  if (nearL && nearB) return "sw";
  if (nearR && nearB) return "se";
  if (nearT && Math.abs(px - cx) <= handlePx) return "n";
  if (nearB && Math.abs(px - cx) <= handlePx) return "s";
  if (nearL && Math.abs(py - cy) <= handlePx) return "w";
  if (nearR && Math.abs(py - cy) <= handlePx) return "e";
  return null;
}

/** 命中优先级：控制柄 > 框体 > 背景。返回从上层到下层的第一个命中。 */
export function hitBox(
  px: number, py: number,
  boxes: Array<{ box: Box; rect: RectPx }>,
  handlePx: number,
): { boxId: string; handle: HandleKind | null } | null {
  // 后画的在上层：倒序遍历，先测柄再测体。
  for (let i = boxes.length - 1; i >= 0; i--) {
    const { box, rect } = boxes[i]!;
    const h = hitHandle(px, py, rect, handlePx);
    if (h) return { boxId: box.boxId, handle: h };
  }
  for (let i = boxes.length - 1; i >= 0; i--) {
    const { box, rect } = boxes[i]!;
    if (pointInRectPx(px, py, rect)) return { boxId: box.boxId, handle: null };
  }
  return null;
}

/** 调整大小：给定原框、柄方位与当前指针（世界坐标），返回新框（面积非负、保中心对侧固定）。 */
export function resizeBox(
  box: Box, handle: HandleKind, worldPt: { x: number; y: number },
  minWm = 0.1, minHm = 0.1,
): { x: number; y: number; w: number; h: number } {
  let x0 = box.x - box.w / 2, x1 = box.x + box.w / 2;
  let y0 = box.y - box.h / 2, y1 = box.y + box.h / 2;
  if (handle.includes("w")) x0 = Math.min(worldPt.x, x1 - minWm);
  if (handle.includes("e")) x1 = Math.max(worldPt.x, x0 + minWm);
  if (handle.includes("n")) y1 = Math.max(worldPt.y, y0 + minHm); // n = y 大侧（俯瞰北向上）
  if (handle.includes("s")) y0 = Math.min(worldPt.y, y1 - minHm);
  return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0 };
}

export function moveBox(box: Box, dx: number, dy: number): { x: number; y: number } {
  return { x: box.x + dx, y: box.y + dy };
}

/** 统计：框内点数与 z 范围内点数（用完整解码数组，不用显示抽稀结果）。 */
export function countPointsInBox(
  pts: { x: Float32Array; y: Float32Array; z: Float32Array },
  box: Pick<Box, "x" | "y" | "w" | "h" | "zMin" | "zMax">,
): number {
  const x0 = box.x - box.w / 2, x1 = box.x + box.w / 2;
  const y0 = box.y - box.h / 2, y1 = box.y + box.h / 2;
  let n = 0;
  for (let i = 0; i < pts.x.length; i++) {
    const px = pts.x[i]!, py = pts.y[i]!, pz = pts.z[i]!;
    if (px >= x0 && px <= x1 && py >= y0 && py <= y1 && pz >= box.zMin && pz <= box.zMax) n++;
  }
  return n;
}

/**
 * 显示抽稀步长：count > maxPoints 时按 stride 抽（i % stride === 0）。
 * 只影响绘制；统计、命中与保存一律用完整数组。
 */
export function displayStride(count: number, maxPoints: number): number {
  if (count <= maxPoints) return 1;
  return Math.ceil(count / maxPoints);
}
