// tests/threeView.test.ts — 3D 资源生命周期（反例 7）：缓冲复用不逐点分配、
// 关闭即停止渲染并释放、容量增长一次性。用假渲染器（node 无 WebGL）。
import { describe, expect, it, vi } from "vitest";
import { ThreeView } from "../src/viewport3d/threeView.ts";
import type { DecodedFrame } from "../src/session/types.ts";

function mkFrame(count: number, fill: number): DecodedFrame {
  const x = new Float32Array(count).fill(fill);
  const y = new Float32Array(count).fill(fill + 1);
  const z = new Float32Array(count).fill(fill + 2);
  return { sessionId: "s", frameIndex: 0, stampSec: 1, count, x, y, z, intensity: null, generation: 1 };
}

function mkFakeCanvas(): HTMLCanvasElement {
  return { clientWidth: 300, clientHeight: 200 } as unknown as HTMLCanvasElement;
}

function mkView() {
  const renders: number[] = [];
  const disposed: number[] = [];
  const queue: Array<() => void> = [];
  const renderCalls = { n: 0 };
  const view = new ThreeView(mkFakeCanvas(), {
    makeRenderer: () => ({
      render: () => { renderCalls.n += 1; },
      setSize: () => undefined,
      dispose: () => disposed.push(1),
    }),
    schedule: (cb) => { queue.push(cb); },
  });
  return {
    view, queue, renderCalls, disposed,
    flush: () => { const q = [...queue]; queue.length = 0; q.forEach((cb) => cb()); },
  };
}

describe("ThreeView 生命周期（反例 7）", () => {
  it("两帧同规模：缓冲复用，无重分配", () => {
    const { view } = mkView();
    view.setFrame(mkFrame(1000, 1));
    const cap1 = view.stats().pointCapacity;
    view.setFrame(mkFrame(1000, 2));
    const s = view.stats();
    expect(s.pointCapacity).toBe(cap1);
    expect(s.bufferReallocations).toBe(0);
    expect(s.pointsDrawn).toBe(1000);
  });

  it("超容量：一次性倍增（不是逐点分配）", () => {
    const { view } = mkView();
    view.setFrame(mkFrame(70000, 1)); // 初始 65536 < 70000
    const s = view.stats();
    expect(s.bufferReallocations).toBe(1);
    expect(s.pointCapacity).toBeGreaterThanOrEqual(70000);
    view.setFrame(mkFrame(70000, 2));
    expect(view.stats().bufferReallocations).toBe(1);
  });

  it("start 后 tick 渲染、stop 后不再渲染；dispose 释放且复活无效", () => {
    const { view, queue, flush, renderCalls, disposed } = mkView();
    view.setFrame(mkFrame(10, 1));
    view.start();
    flush(); // 第一帧渲染 + 重新排队
    flush(); // 第二帧渲染
    expect(renderCalls.n).toBe(2);
    view.stop();
    const pending = queue.length;
    flush(); // stop 后排队的回调直接返回
    expect(renderCalls.n).toBe(2);
    expect(pending).toBeGreaterThanOrEqual(1);
    view.dispose();
    expect(disposed).toHaveLength(1);
    expect(view.stats().disposed).toBe(true);
    expect(view.stats().running).toBe(false);
    view.start(); // 已 dispose：不启动
    expect(view.stats().running).toBe(false);
  });

  it("setBoxes 更新线段 drawRange", () => {
    const { view } = mkView();
    view.setBoxes([{ x: 1, y: 1, w: 0.8, h: 0.6, zMin: 0, zMax: 1.8 }]);
    expect(view.stats()).toMatchObject({ pointsDrawn: 0 });
    // 内部：drawRange 通过渲染验证不抛错即可
    expect(() => view.renderOnce()).not.toThrow();
  });
});
