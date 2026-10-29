// tests/decode.test.ts — 28 字节小端结构解码（与 meta point_layout 对齐）。
import { describe, expect, it } from "vitest";
import { decodeFrame, expectedFrameBytes } from "../src/session/decode.ts";
import type { FrameMeta } from "../src/session/types.ts";

function frameOf(count: number): FrameMeta {
  return { frameIndex: 0, offsetPoints: 0, countPoints: count, stampSec: 1, bagTimeSec: null };
}

describe("decodeFrame", () => {
  it("x/y/z/intensity 逐点往返（小端 float32 @ 0/4/8/12）", () => {
    const n = 5;
    const buf = new ArrayBuffer(n * 28);
    const dv = new DataView(buf);
    for (let i = 0; i < n; i++) {
      dv.setFloat32(i * 28 + 0, i * 1.5, true);
      dv.setFloat32(i * 28 + 4, -i * 0.25, true);
      dv.setFloat32(i * 28 + 8, 0.1 * i, true);
      dv.setFloat32(i * 28 + 12, i / 255, true);
    }
    const out = decodeFrame(buf, frameOf(n), true);
    expect(out.x.length).toBe(n);
    expect(out.x[3]!).toBeCloseTo(4.5, 6);
    expect(out.y[3]!).toBeCloseTo(-0.75, 6);
    expect(out.z[4]!).toBeCloseTo(0.4, 6);
    expect(out.intensity![2]!).toBeCloseTo(2 / 255, 6);
  });
  it("withIntensity=false 不分配强度数组", () => {
    const out = decodeFrame(new ArrayBuffer(28), frameOf(1), false);
    expect(out.intensity).toBeNull();
  });
  it("expectedFrameBytes = count × stride", () => {
    expect(expectedFrameBytes(frameOf(49099), 28)).toBe(49099 * 28);
  });
});
