// session/decode.ts — 解码纯函数。Worker 与（降级时的）主线程共用。
// 只分配输出数组，不修改输入缓冲；输入在 Worker 中以 transferable 传递。
import type { FrameMeta } from "./types.ts";

// meta point_layout：x <f4 @0, y <f4 @4, z <f4 @8, intensity <f4 @12,
// ring <u2 @16 + 2 pad, timestamp <f4 @20 + 4 pad → stride 28。
const F32 = new Float32Array(1);
const U16 = new Uint16Array(1);
const F32_BYTES = 4;

export interface DecodeInput {
  buffer: ArrayBuffer;
  frame: FrameMeta; // 已按 countPoints 截齐的服务端切片
  withIntensity: boolean;
}

export function decodeFrame(buf: ArrayBuffer, frame: FrameMeta, withIntensity: boolean): {
  x: Float32Array; y: Float32Array; z: Float32Array; intensity: Float32Array | null;
} {
  const n = frame.countPoints;
  const dv = new DataView(buf);
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  const z = new Float32Array(n);
  const intensity = withIntensity ? new Float32Array(n) : null;
  const base = 0; // 服务端已按 offsetPoints*stride 切片，切片内第 0 点即帧首点
  for (let i = 0; i < n; i++) {
    const o = base + i * 28;
    x[i] = dv.getFloat32(o, true);
    y[i] = dv.getFloat32(o + 4, true);
    z[i] = dv.getFloat32(o + 8, true);
    if (intensity) intensity[i] = dv.getFloat32(o + 12, true);
  }
  return { x, y, z, intensity };
}

/** 校验切片长度与帧声明一致（防半包/错帧）。 */
export function expectedFrameBytes(frame: FrameMeta, strideBytes: number): number {
  return frame.countPoints * strideBytes;
}

export { F32, U16, F32_BYTES };
