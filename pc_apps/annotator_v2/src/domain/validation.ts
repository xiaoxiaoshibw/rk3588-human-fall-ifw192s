// domain/validation.ts — 文档校验（纯函数，脱离 UI 可测）。
import type { AnnotationDoc, Box, Interval } from "./types.ts";

export interface ValidationIssue {
  level: "error" | "warning";
  code: string;
  message: string;
  ref?: string;
}

/** 冻结/导出前的硬校验：errors 非空则拒绝。 */
export function validateDoc(doc: AnnotationDoc): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const push = (level: "error" | "warning", code: string, message: string, ref?: string) =>
    issues.push({ level, code, message, ref });

  const personIds = new Set<string>();
  for (const p of doc.persons) {
    if (!p.personId) push("error", "person.id-empty", "人物 id 为空", p.personId);
    if (personIds.has(p.personId)) push("error", "person.duplicate", `人物 id 重复：${p.personId}`, p.personId);
    personIds.add(p.personId);
  }

  const boxIds = new Set<string>();
  const perPersonFrame = new Set<string>();
  for (const b of doc.boxes) {
    const ref = b.boxId;
    if (boxIds.has(b.boxId)) push("error", "box.duplicate-id", `框 id 重复：${b.boxId}`, ref);
    boxIds.add(b.boxId);
    if (!personIds.has(b.personId)) push("error", "box.unknown-person", `框引用不存在的人物：${b.personId}`, ref);
    if (b.frameIndex < 0 || b.frameIndex >= doc.frameCount)
      push("error", "box.frame-range", `框帧号越界：${b.frameIndex}`, ref);
    if (!(b.w > 0) || !(b.h > 0)) push("error", "box.size", "框宽高必须为正", ref);
    if (b.zMax <= b.zMin) push("error", "box.z-range", "zMax 必须大于 zMin", ref);
    const key = `${b.personId}@${b.frameIndex}`;
    if (perPersonFrame.has(key))
      push("error", "box.person-frame-duplicate", `同一人物同帧存在多个框：${key}`, ref);
    perPersonFrame.add(key);
    const origin = b.origin;
    if (origin.kind === "adopted") {
      if (!doc.suggestions.some((s) => s.suggestionId === origin.fromSuggestionId)) {
        push("warning", "box.origin-missing", `框来源建议不存在：${origin.fromSuggestionId}`, ref);
      }
    }
  }

  const intervalIds = new Set<string>();
  for (const it of doc.intervals) {
    if (intervalIds.has(it.intervalId)) push("error", "interval.duplicate-id", `区间 id 重复：${it.intervalId}`, it.intervalId);
    intervalIds.add(it.intervalId);
    if (!personIds.has(it.personId)) push("error", "interval.unknown-person", `区间引用不存在的人物：${it.personId}`, it.intervalId);
    if (it.startFrame < 0 || it.endFrame >= doc.frameCount || it.startFrame > it.endFrame)
      push("error", "interval.frame-range", `区间帧范围非法：[${it.startFrame},${it.endFrame}]`, it.intervalId);
    if (!it.label) push("error", "interval.label-empty", "区间标签为空", it.intervalId);
  }

  const sugIds = new Set<string>();
  for (const s of doc.suggestions) {
    if (sugIds.has(s.suggestionId)) push("error", "suggestion.duplicate-id", `建议 id 重复：${s.suggestionId}`);
    sugIds.add(s.suggestionId);
    if (s.status === "accepted" && !s.adoptedRef)
      push("warning", "suggestion.accepted-no-ref", `建议已采用但无产物引用：${s.suggestionId}`, s.suggestionId);
    if (s.box === null && s.interval === null)
      push("error", "suggestion.empty", "建议必须携带框或区间之一", s.suggestionId);
  }

  if (doc.formatVersion !== 2) push("error", "doc.version", `不支持的文档版本：${doc.formatVersion}`);
  for (const f of doc.sampleFrames) {
    if (f < 0 || f >= doc.frameCount)
      push("error", "sample.frame-range", `标注帧清单越界：${f}（共 ${doc.frameCount} 帧）`);
  }
  return issues;
}

export function hasErrors(issues: ValidationIssue[]): boolean {
  return issues.some((i) => i.level === "error");
}

/** 框编辑的即时校验（编辑器内使用，非冻结校验）。 */
export function boxWithinFrameCount(box: Box, frameCount: number): boolean {
  return box.frameIndex >= 0 && box.frameIndex < frameCount;
}

export function intervalSanity(it: Interval): boolean {
  return it.startFrame >= 0 && it.endFrame >= it.startFrame && it.label.length > 0;
}
