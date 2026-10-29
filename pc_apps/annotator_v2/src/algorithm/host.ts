// algorithm/host.ts — 适配宿主：运行算法、按 generation 丢弃过期结果、
// 建议落库（pending）、显式采用（adopt → 人工可编辑框，来源保留）。
// 算法禁用/失败/超时不影响人工标注（规范十四）。
import type { AnnotationDoc, Suggestion } from "../domain/types.ts";
import { newId } from "../domain/types.ts";
import type { Op } from "../annotation/ops.ts";
import { mkBox, mkInterval } from "../annotation/ops.ts";
import { applyOp } from "../annotation/ops.ts";
import type { AlgorithmAdapter, AlgorithmContext, RawSuggestion } from "./types.ts";
import { adapterTag } from "./types.ts";

export class AlgorithmDisabledError extends Error {
  constructor() { super("algorithm disabled"); this.name = "AlgorithmDisabledError"; }
}

/** 宿主侧扩展 Op：建议状态更新（仅采用/拒绝路径产生）。 */
export type HostOp = Op | { t: "updateSuggestion"; suggestionId: string; patch: Partial<Suggestion> };

export function applyHostOp(doc: AnnotationDoc, op: HostOp): AnnotationDoc {
  if (op.t === "updateSuggestion") {
    return {
      ...doc,
      suggestions: doc.suggestions.map((s) => (s.suggestionId === op.suggestionId ? { ...s, ...op.patch } : s)),
    };
  }
  return applyOp(doc, op);
}

export interface HostOptions {
  /** 总开关：false 时 run/adopt 都不可用（反例 9：算法全关仍可完整标注）。 */
  enabled(): boolean;
  currentGeneration(): number;
  commitOp(op: HostOp): void;
  timeoutMs?: number;
}

export class AlgorithmHost {
  constructor(private adapter: AlgorithmAdapter | null, private opts: HostOptions) {}

  get adapterId(): string | null { return this.adapter ? adapterTag(this.adapter) : null; }

  /** 运行算法；结果带 generation 校验——过期（换帧/换会话）直接丢弃，不回写。 */
  async run(ctx: AlgorithmContext): Promise<Suggestion[]> {
    if (!this.opts.enabled() || !this.adapter) throw new AlgorithmDisabledError();
    const adapter = this.adapter;
    const tag = adapterTag(adapter);
    const timeout = this.opts.timeoutMs ?? 30000;
    if (!ctx.frame || ctx.frame.sessionId !== ctx.sessionId || ctx.frame.frameIndex !== ctx.frameIndex) {
      throw new Error('当前帧尚未就绪');
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    let raw: RawSuggestion[];
    try {
      raw = await Promise.race([
        adapter.run(ctx),
        new Promise<never>((_, rej) => { timer = setTimeout(() => rej(new Error(`算法超时 ${timeout}ms`)), timeout); }),
      ]);
    } finally { clearTimeout(timer); }
    if (!this.opts.enabled() || this.opts.currentGeneration() !== ctx.generation) return []; // 过期：丢弃
    const now = Date.now();
    return raw.map((r) => this.toSuggestion(tag, adapter, r, ctx.frameIndex, now));
  }

  private toSuggestion(tag: string, adapter: AlgorithmAdapter, r: RawSuggestion, frameIndex: number, now: number): Suggestion {
    return {
      suggestionId: newId("sug"),
      algorithm: tag,
      paramsHash: adapter.paramsHash,
      frameIndex: r.kind === "interval" ? r.startFrame : frameIndex,
      box: r.kind === "box" ? { x: r.x, y: r.y, w: r.w, h: r.h, zMin: r.zMin, zMax: r.zMax } : null,
      interval: r.kind === "interval" ? { kind: r.kindOf, label: r.label, endFrame: r.endFrame } : null,
      reason: r.reason,
      status: "pending",
      adoptedRef: null,
      createdAtMs: now,
    };
  }

  /** 显式采用：建议标记 accepted，同时生成人工可编辑标注（一条复合撤销记录）。 */
  adopt(doc: AnnotationDoc, suggestionId: string, personId: string): { ops: HostOp[]; createdId: string } | null {
    if (!this.opts.enabled() || !doc.persons.some(p => p.personId === personId)) return null;
    const sug = doc.suggestions.find((s) => s.suggestionId === suggestionId);
    if (!sug || sug.status !== "pending") return null;
    if (sug.interval) {
      const interval = mkInterval(personId, sug.interval.kind, sug.interval.label, sug.frameIndex, sug.interval.endFrame);
      interval.origin = { kind: 'adopted', fromSuggestionId: sug.suggestionId, algorithm: sug.algorithm };
      return { ops: [{ t: 'addInterval', interval }, { t: 'updateSuggestion', suggestionId,
        patch: { status: 'accepted', adoptedRef: interval.intervalId } }], createdId: interval.intervalId };
    }
    if (!sug.box || doc.boxes.some(b => b.personId === personId && b.frameIndex === sug.frameIndex)) return null;
    const box = mkBox(sug.frameIndex, personId, sug.box, {
      kind: "adopted", fromSuggestionId: sug.suggestionId, algorithm: sug.algorithm,
    }, { zMin: sug.box.zMin, zMax: sug.box.zMax });
    return {
      ops: [
        { t: "addBox", box },
        { t: "updateSuggestion", suggestionId, patch: { status: "accepted", adoptedRef: box.boxId } },
      ],
      createdId: box.boxId,
    };
  }

  reject(doc: AnnotationDoc, suggestionId: string): { ops: HostOp[] } | null {
    if (!this.opts.enabled()) return null;
    const sug = doc.suggestions.find((s) => s.suggestionId === suggestionId);
    if (!sug || sug.status !== "pending") return null;
    return { ops: [{ t: "updateSuggestion", suggestionId, patch: { status: "rejected" } }] };
  }
}
