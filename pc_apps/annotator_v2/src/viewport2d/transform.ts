// viewport2d/transform.ts — 世界（米，传感器原始系）↔ 屏幕（CSS 像素）。
// 俯瞰视图：北向上（y+ 朝上 → 屏幕向上），x+ 朝右。
export interface ViewTransform {
  cx: number; // 视野中心（世界米）
  cy: number;
  scalePxPerM: number;
  canvasW: number; // CSS 像素
  canvasH: number;
}

export function makeTransform(cx = 2, cy = 0, scalePxPerM = 60, canvasW = 800, canvasH = 600): ViewTransform {
  return { cx, cy, scalePxPerM, canvasW, canvasH };
}

export function worldToScreen(t: ViewTransform, x: number, y: number): { sx: number; sy: number } {
  return {
    sx: t.canvasW / 2 + (x - t.cx) * t.scalePxPerM,
    sy: t.canvasH / 2 - (y - t.cy) * t.scalePxPerM, // y 翻转：北向上
  };
}

export function screenToWorld(t: ViewTransform, sx: number, sy: number): { x: number; y: number } {
  return {
    x: t.cx + (sx - t.canvasW / 2) / t.scalePxPerM,
    y: t.cy - (sy - t.canvasH / 2) / t.scalePxPerM,
  };
}

export function metersPerPx(t: ViewTransform): number {
  return 1 / t.scalePxPerM;
}

/** 以 (sx, sy) 为锚点缩放（滚轮/捏合）：保持锚点世界坐标不动。 */
export function zoomAt(t: ViewTransform, sx: number, sy: number, factor: number, minScale = 2, maxScale = 2000): ViewTransform {
  const before = screenToWorld(t, sx, sy);
  const next = Math.min(maxScale, Math.max(minScale, t.scalePxPerM * factor));
  const nt: ViewTransform = { ...t, scalePxPerM: next };
  const after = screenToWorld(nt, sx, sy);
  nt.cx = t.cx + (before.x - after.x);
  nt.cy = t.cy + (before.y - after.y);
  return nt;
}

export function panByPx(t: ViewTransform, dxPx: number, dyPx: number): ViewTransform {
  return { ...t, cx: t.cx - dxPx / t.scalePxPerM, cy: t.cy + dyPx / t.scalePxPerM };
}
