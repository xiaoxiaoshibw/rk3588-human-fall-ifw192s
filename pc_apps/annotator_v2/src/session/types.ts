// session/types.ts — 会话与帧的数据类型（解析自 meta.json，见
// docs/human_capture/README.md §2：points.bin 为小端紧凑结构体数组，
// 字段 x,y,z,intensity,ring,timestamp，stride 28 字节）。

export interface FrameMeta {
  frameIndex: number;
  offsetPoints: number;
  countPoints: number;
  stampSec: number; // 设备秒（time_domain: device_stamp_s_unanchored）
  bagTimeSec: number | null;
}

export interface SessionMeta {
  sessionId: string;
  frameCount: number;
  totalPoints: number;
  pointStrideBytes: number; // 28
  fields: string[]; // ["x","y","z","intensity","ring","timestamp"]
  dtypes: string[]; // ["<f4",...]
  frames: FrameMeta[];
  sourceBagSha256: string | null;
}

export interface DecodedFrame {
  sessionId: string;
  frameIndex: number;
  stampSec: number;
  count: number;
  /** 顶点 xyz；与 3D 视口共享同一份引用（只读，不复制）。 */
  x: Float32Array;
  y: Float32Array;
  z: Float32Array;
  intensity: Float32Array | null;
  /** 解码代次：用于丢弃过期异步结果。 */
  generation: number;
}

export interface SessionSummary {
  sessionId: string;
  frameCount: number;
  durationSec: number | null;
  totalPoints: number;
  createdAtIso: string | null;
}
