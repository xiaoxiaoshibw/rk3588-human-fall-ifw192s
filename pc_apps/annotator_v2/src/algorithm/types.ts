// algorithm/types.ts — 算法适配入口（规范十四）。
// 算法接收显式绑定的帧与上下文，输出候选框/区间建议；建议与人工标注分开
// 存储/显示，只有用户显式采用后才进入人工编辑流程并保留来源。
import type { DecodedFrame } from "../session/types.ts";
import type { AnnotationDoc, BoxOrigin, IntervalKind } from "../domain/types.ts";

export interface AlgorithmContext {
  sessionId: string;
  frameIndex: number;
  generation: number; // 会话/帧世代：异步返回时必须核对
  frame: DecodedFrame | null;
  doc: AnnotationDoc; // 只读：算法可参考已有人工标注，但不得修改
}

export interface RawBoxSuggestion {
  kind: "box";
  x: number; y: number; w: number; h: number;
  zMin: number; zMax: number;
  reason: string;
}

export interface RawIntervalSuggestion {
  kind: "interval";
  kindOf: IntervalKind;
  label: string;
  startFrame: number;
  endFrame: number;
  reason: string;
}

export type RawSuggestion = RawBoxSuggestion | RawIntervalSuggestion;

export interface AlgorithmAdapter {
  id: string;
  version: string; // 语义化版本；结果携带 "<id>@<version>"
  paramsHash: string; // 参数绑定摘要（改动参数 → 新 hash）
  displayName: string;
  /** 同步或异步计算；必须尊重 ctx.generation。 */
  run(ctx: AlgorithmContext): Promise<RawSuggestion[]>;
}

export function adapterTag(a: AlgorithmAdapter): string {
  return `${a.id}@${a.version}`;
}

export type AdoptedOrigin = Extract<BoxOrigin, { kind: "adopted" }>;
