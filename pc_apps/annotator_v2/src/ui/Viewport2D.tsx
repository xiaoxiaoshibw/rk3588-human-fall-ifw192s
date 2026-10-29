// ui/Viewport2D.tsx — 俯瞰视口：底图（点云）与覆盖层（标注）两张画布叠放。
// 底图只在帧/视图变化时重绘；覆盖层随交互重绘（rAF 合并）。指针事件全部走
// Pointer Events + setPointerCapture；面板/工具栏不在此元素内，不会误触发画布手势。
import React, { useEffect, useRef } from "react";
import type { AnnotationDoc, Suggestion } from "../domain/types.ts";
import type { DecodedFrame, SessionMeta } from "../session/types.ts";
import type { InteractionController, Tool } from "../viewport2d/interaction.ts";
import { evtFromDom } from "../viewport2d/interaction.ts";
import { drawBaseLayer, drawOverlayLayer, defaultStyle } from "../viewport2d/renderer.ts";
import { boxToRectPx } from "../domain/geometry.ts";
import { zoomAt } from "../viewport2d/transform.ts";
import type { ViewTransform } from "../viewport2d/transform.ts";
import { metersPerPx, worldToScreen } from "../viewport2d/transform.ts";

export interface Viewport2DProps {
  controllerRef: React.MutableRefObject<InteractionController | null>;
  transformRef: React.MutableRefObject<ViewTransform>;
  baseRedrawRef: React.MutableRefObject<(() => void) | null>;
  overlayRedrawRef: React.MutableRefObject<(() => void) | null>;
  frameRef: React.MutableRefObject<DecodedFrame | null>;
  frameEpoch: number;
  sessionId: string;
  doc: AnnotationDoc | null;
  frameIndex: number;
  selectedBoxId: string | null;
  tool: Tool;
  suggestions: Suggestion[];
  frameStatus: string;
  meta: SessionMeta;
}

// 性能探针（只累计，不影响行为；浏览器端到端读取验证规范十二）。
export interface PerfStats {
  overlayDraws: number;
  overlayMs: number;
  overlayMaxMs: number;
  baseDraws: number;
  baseMs: number;
  baseMaxMs: number;
  lastMoveToRedrawMs: number | null;
  moveSamples: number;
}
export function perfStats(): PerfStats {
  const g = globalThis as { __annotatorStats?: PerfStats };
  return g.__annotatorStats ?? (g.__annotatorStats = {
    overlayDraws: 0, overlayMs: 0, overlayMaxMs: 0,
    baseDraws: 0, baseMs: 0, baseMaxMs: 0,
    lastMoveToRedrawMs: null, moveSamples: 0,
  });
}
const lastMoveTs = { v: 0 };

export function Viewport2D(p: Viewport2DProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const baseRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);

  // 最新渲染输入的 ref（指针高频路径不经过 React）
  const stateRef = useRef({ doc: p.doc, frameIndex: p.frameIndex, selectedBoxId: p.selectedBoxId, tool: p.tool, suggestions: p.suggestions, meta: p.meta, sessionId: p.sessionId });
  stateRef.current = { doc: p.doc, frameIndex: p.frameIndex, selectedBoxId: p.selectedBoxId, tool: p.tool, suggestions: p.suggestions, meta: p.meta, sessionId: p.sessionId };

  // rAF 合并绘制
  const rafRef = useRef<{ base: boolean; overlay: boolean; handle: number | null }>({ base: false, overlay: false, handle: null });
  const schedule = (which: "base" | "overlay") => {
    const r = rafRef.current;
    r[which] = true;
    if (r.handle !== null) return;
    r.handle = requestAnimationFrame(() => {
      r.handle = null;
      const doBase = r.base; const doOverlay = r.overlay;
      r.base = false; r.overlay = false;
      if (doBase) renderBase();
      if (doOverlay) renderOverlay();
    });
  };

  const canvasSize = (): { w: number; h: number } => {
    const el = wrapRef.current;
    return { w: el?.clientWidth ?? 800, h: el?.clientHeight ?? 600 };
  };

  const syncTransformSize = () => {
    const { w, h } = canvasSize();
    const t = p.transformRef.current;
    if (t.canvasW !== w || t.canvasH !== h) {
      p.transformRef.current = { ...t, canvasW: w, canvasH: h };
    }
  };

  const renderBase = () => {
    const cv = baseRef.current;
    if (!cv) return;
    const t0 = performance.now();
    syncTransformSize();
    const t = p.transformRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = Math.max(1, Math.round(t.canvasW * dpr)), H = Math.max(1, Math.round(t.canvasH * dpr));
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawBaseLayer(ctx, t, p.frameRef.current, defaultStyle);
    const s = perfStats();
    const dt = performance.now() - t0;
    s.baseDraws += 1; s.baseMs += dt; s.baseMaxMs = Math.max(s.baseMaxMs, dt);
  };

  const renderOverlay = () => {
    const cv = overlayRef.current;
    if (!cv) return;
    const t0 = performance.now();
    syncTransformSize();
    const t = p.transformRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = Math.max(1, Math.round(t.canvasW * dpr)), H = Math.max(1, Math.round(t.canvasH * dpr));
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const s = stateRef.current;
    const controller = p.controllerRef.current;
    const boxes = s.doc ? s.doc.boxes.filter((b) => b.frameIndex === s.frameIndex) : [];
    const personsMap = new Map((s.doc?.persons ?? []).map((per) => [per.personId, per]));
    drawOverlayLayer(ctx, t, {
      boxes,
      persons: personsMap,
      selection: s.selectedBoxId,
      preview: controller ? controller.getPreview() : null,
      hoverBoxId: null,
      tool: s.tool,
      suggestions: s.suggestions.filter((sg) => sg.box !== null).map((sg) => sg.box!),
    }, defaultStyle);
    // HUD
    const f = p.frameRef.current;
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillStyle = "rgba(255,255,255,0.6)";
    ctx.fillText(
      `帧 ${s.frameIndex}/${s.meta.frameCount - 1}${f ? ` · ${f.count} 点` : " · 加载中"}${p.frameStatus === "error" ? " · 加载失败" : ""}`,
      8, 18,
    );
    const st = perfStats();
    const dt = performance.now() - t0;
    st.overlayDraws += 1; st.overlayMs += dt; st.overlayMaxMs = Math.max(st.overlayMaxMs, dt);
    if (lastMoveTs.v > 0) {
      st.lastMoveToRedrawMs = t0 - lastMoveTs.v;
      st.moveSamples += 1;
      lastMoveTs.v = 0;
    }
  };

  // 对外暴露重绘入口
  p.baseRedrawRef.current = () => schedule("base");
  p.overlayRedrawRef.current = () => schedule("overlay");

  // 帧到达 → 底图 + 覆盖层
  useEffect(() => {
    schedule("base");
    schedule("overlay");
  }, [p.frameEpoch]);

  // 标注/选择/工具变化 → 覆盖层
  useEffect(() => {
    schedule("overlay");
  }, [p.doc, p.frameIndex, p.selectedBoxId, p.tool]);

  // 尺寸变化
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      schedule("base");
      schedule("overlay");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 换会话：按首帧点云自动取景（用 1%–99% 分位，避免少量远点把视野拉得太远）
  const fittedFor = useRef<string>("");
  useEffect(() => {
    if (p.frameEpoch === 0) return;
    const f = p.frameRef.current;
    if (!f || fittedFor.current === p.sessionId) return;
    fittedFor.current = p.sessionId;
    if (f.count === 0) return;
    const stride = Math.max(1, Math.floor(f.count / 20000));
    const xs: number[] = [], ys: number[] = [];
    for (let i = 0; i < f.count; i += stride) {
      if (Number.isFinite(f.x[i]) && Number.isFinite(f.y[i])) { xs.push(f.x[i]!); ys.push(f.y[i]!); }
    }
    if (xs.length === 0) return;
    const q = (a: number[], p: number) => a[Math.max(0, Math.min(a.length - 1, Math.floor(a.length * p)))]!;
    xs.sort((a, b) => a - b); ys.sort((a, b) => a - b);
    const x0 = q(xs, 0.01), x1 = q(xs, 0.99);
    const y0 = q(ys, 0.01), y1 = q(ys, 0.99);
    const { w, h } = canvasSize();
    const spanX = Math.max(2, (x1 - x0) * 1.15);
    const spanY = Math.max(2, (y1 - y0) * 1.15);
    const scale = Math.min(w / spanX, h / spanY);
    p.transformRef.current = {
      cx: (x0 + x1) / 2, cy: (y0 + y1) / 2,
      scalePxPerM: Math.max(2, Math.min(2000, scale)),
      canvasW: w, canvasH: h,
    };
    schedule("base");
    schedule("overlay");
  }, [p.frameEpoch, p.sessionId]);

  // ---------- 指针接线 ----------
  const withCapture = (e: React.PointerEvent<HTMLCanvasElement>, fn: (local: { x: number; y: number }) => void) => {
    const rect = e.currentTarget.getBoundingClientRect();
    fn({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    // 左/中键才走手势；右键弹菜单
    if (e.button === 2) return;
    e.currentTarget.setPointerCapture(e.pointerId); // 画布外松手也能收到 up（反例 2）
    withCapture(e, (local) => p.controllerRef.current?.pointerDown({ ...local, button: e.button, pointerType: e.pointerType }));
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    lastMoveTs.v = performance.now();
    withCapture(e, (local) => p.controllerRef.current?.pointerMove({ ...local, button: e.button, pointerType: e.pointerType }));
  };
  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    withCapture(e, (local) => p.controllerRef.current?.pointerUp({ ...local, button: e.button, pointerType: e.pointerType }));
  };
  const onPointerCancel = () => { p.controllerRef.current?.pointerCancel(); };
  const onLostPointerCapture = () => {
    // 正常路径：up 已结束手势（isBusy=false），这里只会清理异常中断
    if (p.controllerRef.current?.isBusy()) p.controllerRef.current.lostPointerCapture();
  };
  const onPointerLeave = (e: React.PointerEvent<HTMLCanvasElement>) => {
    // 捕获中的 leave 不代表手势结束（可能只是移出画布）；未捕获才取消
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) {
      p.controllerRef.current?.externalCancel();
    }
  };
  // 滚轮缩放：必须用原生非 passive 监听（React 的 onWheel 是 passive，preventDefault 无效；
  // 且滚轮事件落在最上层的 overlay canvas 上，不会冒泡到 base canvas）。
  const wheelHandler = useRef<(e: WheelEvent) => void>(() => {});
  wheelHandler.current = (e: WheelEvent) => {
    e.preventDefault();
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const factor = Math.exp(-e.deltaY * 0.0012);
    p.transformRef.current = zoomAt(p.transformRef.current, e.clientX - rect.left, e.clientY - rect.top, factor);
    schedule("base");
    schedule("overlay");
  };
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheelNative = (e: WheelEvent) => wheelHandler.current(e);
    el.addEventListener("wheel", onWheelNative, { passive: false });
    return () => el.removeEventListener("wheel", onWheelNative);
  }, []);

  return (
    <div className="viewport2d-wrap" ref={wrapRef}>
      <canvas
        ref={baseRef}
        className="base"
      />
      <canvas
        ref={overlayRef}
        className="overlay"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        onLostPointerCapture={onLostPointerCapture}
        onPointerLeave={onPointerLeave}
        onContextMenu={(e) => e.preventDefault()}
      />
    </div>
  );
}

export function currentWorldRect(box: AnnotationDoc["boxes"][number], t: ViewTransform) {
  return boxToRectPx(box, (x, y) => worldToScreen(t, x, y), metersPerPx(t));
}
