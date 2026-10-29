// ui/Viewport3D.tsx — 3D 小窗：与 2D 共享同一份解码帧引用；打开创建 ThreeView，
// 关闭即 stop + dispose（不残留渲染循环）；自带视角拖拽（局部状态，不进 React）。
import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import type { AnnotationDoc, Box } from "../domain/types.ts";
import type { DecodedFrame } from "../session/types.ts";
import { ThreeView } from "../viewport3d/threeView.ts";
import type { BodyColorSet } from '../annotation/body.ts';

export interface Viewport3DProps {
  frameRef: React.MutableRefObject<DecodedFrame | null>;
  frameEpoch: number;
  boxes: Box[];
  doc: AnnotationDoc | null;
  onClose(): void;
  personColorOf(doc: AnnotationDoc | null, personId: string): string;
  bodyColors?: BodyColorSet[];
  onPickPart?(part: string): void;
  focusBody?: boolean;
}

export function Viewport3D(p: Viewport3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<ThreeView | null>(null);
  const boxesRef = useRef(p.boxes);
  boxesRef.current = p.boxes;

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const view = new ThreeView(cv);
    viewRef.current = view;
    view.setFrame(p.frameRef.current);
    view.setBoxes(boxesRef.current);
    view.start();
    const ro = new ResizeObserver(() => {
      const w = wrapRef.current?.clientWidth ?? 300;
      const h = wrapRef.current?.clientHeight ?? 300;
      view.resize(w, h);
    });
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => {
      ro.disconnect();
      view.dispose(); // 关窗：停止渲染 + 释放 GPU 资源（反例 7）
      viewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    viewRef.current?.setFrame(p.frameRef.current);
    viewRef.current?.setBoxes(p.boxes);
    viewRef.current?.setBodyColors(p.bodyColors ?? [], p.focusBody);
  }, [p.frameEpoch, p.boxes, p.bodyColors, p.focusBody]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || !p.onPickPart) return;
    const click = (e: MouseEvent) => {
      const rect = cv.getBoundingClientRect();
      const part = viewRef.current?.pickPart((e.clientX-rect.left)/rect.width*2-1, 1-(e.clientY-rect.top)/rect.height*2);
      if (part) p.onPickPart?.(part);
    };
    cv.addEventListener('click', click);
    return () => cv.removeEventListener('click', click);
  }, [p.onPickPart]);

  // 视角控制：左键拖旋转 / 滚轮缩放 / 中键平移（局部，无 React 状态）
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    let az = Math.PI * 0.75, polar = Math.PI / 3, dist = 8;
    let mode: "none" | "orbit" | "panmove" = "none";
    let lastX = 0, lastY = 0;
    const apply = () => viewRef.current?.setView(az, polar, dist);
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 && e.button !== 1) return;
      cv.setPointerCapture(e.pointerId);
      mode = e.button === 1 ? "panmove" : "orbit";
      lastX = e.clientX; lastY = e.clientY;
    };
    const onMove = (e: PointerEvent) => {
      if (mode === "none") return;
      const dx = e.clientX - lastX, dy = e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      if (mode === "orbit") {
        az -= dx * 0.006;
        polar = Math.max(0.15, Math.min(Math.PI - 0.15, polar - dy * 0.006));
      } else {
        az += dx * 0.006; // 简化：中键也转（平移可后续加）
      }
      apply();
    };
    const onUp = (e: PointerEvent) => {
      mode = "none";
      if (cv.hasPointerCapture(e.pointerId)) cv.releasePointerCapture(e.pointerId);
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      dist = Math.max(1.5, Math.min(40, dist * Math.exp(e.deltaY * 0.0012)));
      apply();
    };
    cv.addEventListener("pointerdown", onDown);
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerup", onUp);
    cv.addEventListener("pointercancel", onUp);
    cv.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      cv.removeEventListener("pointerdown", onDown);
      cv.removeEventListener("pointermove", onMove);
      cv.removeEventListener("pointerup", onUp);
      cv.removeEventListener("pointercancel", onUp);
      cv.removeEventListener("wheel", onWheel);
    };
  }, []);

  return (
    <div className="viewport3d-wrap" ref={wrapRef}>
      {!p.focusBody && <button className="close3d small" onClick={p.onClose} title="关闭 3D（停止渲染并释放资源）">✕</button>}
      <canvas ref={canvasRef} />
    </div>
  );
}

export { THREE };
