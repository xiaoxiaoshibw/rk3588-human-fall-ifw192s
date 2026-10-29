// tests/renderer.test.ts — 2D 点层像素路径：只画视野内点、按 z 分色、清除旧像素。
import { afterEach, describe, expect, it, vi } from "vitest";
import { drawBaseLayer, paintPointImage, defaultStyle } from "../src/viewport2d/renderer.ts";
import type { DecodedFrame } from "../src/session/types.ts";
import type { ViewTransform } from "../src/viewport2d/transform.ts";

function frame(xs: number[], ys: number[], zs: number[]): DecodedFrame {
  return {
    sessionId: "s", frameIndex: 0, stampSec: 1, count: xs.length,
    x: Float32Array.from(xs), y: Float32Array.from(ys), z: Float32Array.from(zs),
    intensity: null, generation: 1,
  };
}

const t: ViewTransform = { cx: 0, cy: 0, scalePxPerM: 10, canvasW: 100, canvasH: 100 };

describe("paintPointImage", () => {
  it("视野外的点不画；z 不同颜色不同；每帧先清空", () => {
    const px = new Uint32Array(100 * 100);
    // (0,0) z=0 → 屏幕 (50,50)；(2,2) z=1 → (70,30)；(20,20) 在视野外。
    paintPointImage(px, 100, 100, frame([0, 2, 20], [0, 2, 20], [0, 1, 0.5]), t, defaultStyle);
    expect(px[50 * 100 + 50]).toBeGreaterThan(0);
    expect(px[30 * 100 + 70]).toBeGreaterThan(0);
    expect(px[50 * 100 + 50]).not.toBe(px[30 * 100 + 70]);
    expect(px[0]).toBe(0);
    // 第二帧只含中心点：旧像素必须被清掉。
    paintPointImage(px, 100, 100, frame([0], [0], [0]), t, defaultStyle);
    expect(px[30 * 100 + 70]).toBe(0);
    expect(px[50 * 100 + 50]).toBeGreaterThan(0);
  });

  it("z 全相同时不产生 NaN 颜色", () => {
    const px = new Uint32Array(100 * 100);
    paintPointImage(px, 100, 100, frame([0], [0], [1]), t, defaultStyle);
    expect(px[50 * 100 + 50]).toBeGreaterThan(0);
  });

  it("drawBaseLayer 走离屏像素层而不是逐点 fillStyle", () => {
    const calls = { drawImage: 0, fillStyle: 0 };
    let offscreen: { data: Uint8ClampedArray } | null = null;
    const fakeCanvas = {
      width: 0, height: 0,
      getContext: () => ({
        createImageData: (w: number, h: number) => {
          const data = new Uint8ClampedArray(w * h * 4);
          offscreen = { data };
          return { data, width: w, height: h };
        },
        putImageData: () => undefined,
      }),
    };
    vi.stubGlobal("document", { createElement: () => fakeCanvas });
    const ctx = {
      clearRect: () => undefined, fillRect: () => undefined, beginPath: () => undefined,
      moveTo: () => undefined, lineTo: () => undefined, stroke: () => undefined,
      arc: () => undefined, fill: () => undefined, save: () => undefined,
      restore: () => undefined,
      drawImage: () => { calls.drawImage += 1; },
      set fillStyle(_v: string) { calls.fillStyle += 1; },
      strokeStyle: "", lineWidth: 1, imageSmoothingEnabled: true,
    };
    drawBaseLayer(ctx as unknown as CanvasRenderingContext2D, t, frame([0, 2], [0, 2], [0, 1]), defaultStyle);
    expect(calls.drawImage).toBe(1);
    expect(calls.fillStyle).toBeLessThan(10); // 背景/原点，不是每点一次
    expect(offscreen).not.toBeNull();
  });
});

afterEach(() => vi.unstubAllGlobals());
