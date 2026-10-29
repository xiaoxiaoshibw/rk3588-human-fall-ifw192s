// domain/types.ts — 标注领域的数据类型。全部可 JSON 序列化，字段含义见
// ARCHITECTURE.md「坐标系与单位」。
//
// 坐标系：传感器原始坐标（IFW192S 设备系，x 向前 / y 向左 / z 向上），单位米。
// 帧号：meta.json frames 数组下标（0 起）。源时间：frames[i].stamp_sec（设备秒）。

/** 框来源：人工 / 从上一帧传播 / 显式采用的算法建议（保留来源）。 */
export type BoxOrigin =
  | { kind: "human" }
  | { kind: "propagated"; fromBoxId: string }
  | {
      kind: "adopted";
      fromSuggestionId: string;
      algorithm: string; // "<adapterId>@<version>"
    };

export type Visibility = "visible" | "partial" | "occluded";

/** 俯瞰轴对齐矩形框（世界坐标，米）。x/y 为中心，w/h 为全宽全高。 */
export interface Box {
  boxId: string;
  frameIndex: number;
  personId: string;
  x: number;
  y: number;
  w: number;
  h: number;
  zMin: number;
  zMax: number;
  visibility: Visibility;
  origin: BoxOrigin;
  reviewed: boolean;
  note: string | null;
  updatedAtMs: number;
}

export interface Person {
  personId: string; // 如 "P1"
  label: string | null;
  color: string | null; // CSS 色；null = 按序自动分配
}

export type IntervalKind = "action" | "event";

/** 闭区间 [startFrame, endFrame]（含两端，帧号）。 */
export interface Interval {
  intervalId: string;
  personId: string;
  kind: IntervalKind;
  label: string; // 动作/事件名，如 "walk" / "fall"
  startFrame: number;
  endFrame: number;
  origin: BoxOrigin;
  reviewed: boolean;
  note: string | null;
}

export type SuggestionStatus = "pending" | "accepted" | "rejected";

/** 算法建议（与人工标注分开存储/显示；采用后才进入人工编辑）。 */
export interface Suggestion {
  suggestionId: string;
  algorithm: string; // "<adapterId>@<version>"
  paramsHash: string;
  /** 建议绑定的源帧（区间建议为 startFrame）。 */
  frameIndex: number;
  box: { x: number; y: number; w: number; h: number; zMin: number; zMax: number } | null;
  interval: { kind: IntervalKind; label: string; endFrame: number } | null;
  reason: string | null;
  status: SuggestionStatus;
  /** 采用后生成的人工标注 id（boxId / intervalId）。 */
  adoptedRef: string | null;
  createdAtMs: number;
}

/** 存储格式 gt_annotate/2。不兼容变更时升版本 + 迁移，不改旧字段含义。
 * sampleFrames 为可选新增字段（旧文档缺失时按空表解析，不升版本）。 */
export interface AnnotationDoc {
  format: "gt_annotate";
  formatVersion: 2;
  sessionId: string;
  coordinateFrame: "sensor-IFW192S-raw";
  units: "m";
  frameCount: number;
  annotator: string;
  persons: Person[];
  boxes: Box[];
  intervals: Interval[];
  suggestions: Suggestion[];
  /** 稀疏标注：计划标注的帧清单（人择或按间隔取样）；与 boxes 独立。 */
  sampleFrames: number[];
  savedAtMs: number | null;
}

export function emptyDoc(sessionId: string, frameCount: number, annotator = ""): AnnotationDoc {
  return {
    format: "gt_annotate",
    formatVersion: 2,
    sessionId,
    coordinateFrame: "sensor-IFW192S-raw",
    units: "m",
    frameCount,
    annotator,
    persons: [],
    boxes: [],
    intervals: [],
    suggestions: [],
    sampleFrames: [],
    savedAtMs: null,
  };
}

/** 稀疏取样：从 start 起 every N 帧取一个（含 start，钳制到 frameCount-1）。 */
export function sampleEveryN(frameCount: number, everyN: number, start = 0): number[] {
  const n = Math.max(1, Math.floor(everyN));
  const out: number[] = [];
  for (let f = Math.max(0, Math.floor(start)); f < frameCount; f += n) out.push(f);
  return out;
}

/** 已标注帧集合（有任意框的帧）。 */
export function annotatedFrameSet(doc: AnnotationDoc): Set<number> {
  const s = new Set<number>();
  for (const b of doc.boxes) s.add(b.frameIndex);
  return s;
}

/** 清单覆盖：清单里已标/未标统计。 */
export function sampleCoverage(doc: AnnotationDoc): { total: number; annotated: number; missing: number[] } {
  const has = annotatedFrameSet(doc);
  const missing: number[] = [];
  for (const f of doc.sampleFrames) if (!has.has(f)) missing.push(f);
  return { total: doc.sampleFrames.length, annotated: doc.sampleFrames.length - missing.length, missing };
}

/** 生成短随机 id（浏览器 crypto 可用时无规律；否则退化计数）。 */
const idAlphabet = "abcdefghijklmnopqrstuvwxyz0123456789";
let idCounter = 0;
export function newId(prefix: string): string {
  idCounter += 1;
  let rand = "";
  const g = globalThis.crypto;
  if (g && typeof g.getRandomValues === "function") {
    const buf = new Uint8Array(6);
    g.getRandomValues(buf);
    rand = Array.from(buf, (b) => idAlphabet[b % idAlphabet.length]).join("");
  } else {
    rand = idCounter.toString(36);
  }
  return `${prefix}_${Date.now().toString(36)}_${rand}`;
}
