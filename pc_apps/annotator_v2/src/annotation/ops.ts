// annotation/ops.ts — 编辑操作（命令模式）：一次拖动 = 预览 + 结束时提交一个 Op，
// 撤销/重做按 Op 为单位（规范十一：拖动期间只更新预览，结束后一次可撤销记录）。
import type { AnnotationDoc, Box, Interval, Person, Suggestion } from "../domain/types.ts";
import { newId } from "../domain/types.ts";

export type Op =
  | { t: "addPerson"; person: Person }
  | { t: "updatePerson"; personId: string; patch: Partial<Person> }
  | { t: "removePerson"; personId: string }
  | { t: "addBox"; box: Box }
  | { t: "updateBox"; boxId: string; patch: Partial<Box> }
  | { t: "removeBox"; boxId: string }
  | { t: "addInterval"; interval: Interval }
  | { t: "updateInterval"; intervalId: string; patch: Partial<Interval> }
  | { t: "removeInterval"; intervalId: string }
  | { t: "addSuggestion"; suggestion: Suggestion }
  | { t: "updateSuggestion"; suggestionId: string; patch: Partial<Suggestion> }
  | { t: "removeSuggestion"; suggestionId: string }
  | { t: "setSampleFrames"; frames: number[] } // 稀疏标注帧清单（整表替换，可撤销）
  | { t: "composite"; label: string; ops: Op[] }; // 拖动提交 = 单条复合记录

export function applyOp(doc: AnnotationDoc, op: Op): AnnotationDoc {
  const d: AnnotationDoc = { ...doc };
  switch (op.t) {
    case "addPerson":
      d.persons = [...d.persons, op.person];
      return d;
    case "updatePerson":
      d.persons = d.persons.map((p) => (p.personId === op.personId ? { ...p, ...op.patch } : p));
      return d;
    case "removePerson":
      d.persons = d.persons.filter((p) => p.personId !== op.personId);
      d.boxes = d.boxes.filter((b) => b.personId !== op.personId);
      d.intervals = d.intervals.filter((i) => i.personId !== op.personId);
      return d;
    case "addBox":
      d.boxes = [...d.boxes, op.box];
      return d;
    case "updateBox":
      d.boxes = d.boxes.map((b) => (b.boxId === op.boxId ? { ...b, ...op.patch, updatedAtMs: Date.now() } : b));
      return d;
    case "removeBox":
      d.boxes = d.boxes.filter((b) => b.boxId !== op.boxId);
      return d;
    case "addInterval":
      d.intervals = [...d.intervals, op.interval];
      return d;
    case "updateInterval":
      d.intervals = d.intervals.map((i) => (i.intervalId === op.intervalId ? { ...i, ...op.patch } : i));
      return d;
    case "removeInterval":
      d.intervals = d.intervals.filter((i) => i.intervalId !== op.intervalId);
      return d;
    case "addSuggestion":
      d.suggestions = [...d.suggestions, op.suggestion];
      return d;
    case "updateSuggestion":
      d.suggestions = d.suggestions.map((s) => (s.suggestionId === op.suggestionId ? { ...s, ...op.patch } : s));
      return d;
    case "removeSuggestion":
      d.suggestions = d.suggestions.filter((s) => s.suggestionId !== op.suggestionId);
      return d;
    case "setSampleFrames":
      d.sampleFrames = [...op.frames].sort((a, b) => a - b);
      return d;
    case "composite": {
      let cur = doc;
      for (const sub of op.ops) cur = applyOp(cur, sub);
      return cur;
    }
    default: {
      const never: never = op;
      void never;
      return d;
    }
  }
}

/** 构造反操作（undo 用）。要求 doc 为应用该 Op 之前的状态。 */
export function invertOp(doc: AnnotationDoc, op: Op): Op {
  switch (op.t) {
    case "addPerson":
      return { t: "removePerson", personId: op.person.personId };
    case "updatePerson": {
      const before = doc.persons.find((p) => p.personId === op.personId);
      if (!before) return { t: "composite", label: "noop", ops: [] };
      return { t: "updatePerson", personId: op.personId, patch: pickChanged(before, op.patch) };
    }
    case "removePerson":
      return { t: "composite", label: "undo-removePerson", ops: [
        { t: "addPerson", person: doc.persons.find((p) => p.personId === op.personId) ?? op0Person(op.personId) },
        ...doc.boxes.filter((b) => b.personId === op.personId).map((b) => ({ t: "addBox", box: b } as Op)),
        ...doc.intervals.filter((i) => i.personId === op.personId).map((i) => ({ t: "addInterval", interval: i } as Op)),
      ] };
    case "addBox":
      return { t: "removeBox", boxId: op.box.boxId };
    case "updateBox": {
      const before = doc.boxes.find((b) => b.boxId === op.boxId);
      if (!before) return { t: "composite", label: "noop", ops: [] };
      return { t: "updateBox", boxId: op.boxId, patch: pickChanged(before, op.patch) };
    }
    case "removeBox":
      return { t: "addBox", box: doc.boxes.find((b) => b.boxId === op.boxId) ?? op0Box(op.boxId) };
    case "addInterval":
      return { t: "removeInterval", intervalId: op.interval.intervalId };
    case "updateInterval": {
      const before = doc.intervals.find((i) => i.intervalId === op.intervalId);
      if (!before) return { t: "composite", label: "noop", ops: [] };
      return { t: "updateInterval", intervalId: op.intervalId, patch: pickChanged(before, op.patch) };
    }
    case "removeInterval":
      return { t: "addInterval", interval: doc.intervals.find((i) => i.intervalId === op.intervalId) ?? op0Interval(op.intervalId) };
    case "addSuggestion":
      return { t: "removeSuggestion", suggestionId: op.suggestion.suggestionId };
    case "removeSuggestion":
      return { t: "addSuggestion", suggestion: doc.suggestions.find((s) => s.suggestionId === op.suggestionId) ?? op0Suggestion(op.suggestionId) };
    case "updateSuggestion": {
      const before = doc.suggestions.find((s) => s.suggestionId === op.suggestionId);
      if (!before) return { t: "composite", label: "noop", ops: [] };
      return { t: "updateSuggestion", suggestionId: op.suggestionId, patch: pickChanged(before, op.patch) };
    }
    case "setSampleFrames":
      return { t: "setSampleFrames", frames: doc.sampleFrames };
    case "composite":
      // 复合的逆 = 子逆倒序
      return { t: "composite", label: `undo-${op.label}`, ops: invertSeq(doc, op.ops) };
  }
}

function invertSeq(doc: AnnotationDoc, ops: Op[]): Op[] {
  // 倒序逐个在“应用前”状态上求逆：子 op i 的前置状态是应用 ops[0..i) 后的 doc。
  let cur = doc;
  const out: Op[] = [];
  for (let i = ops.length - 1; i >= 0; i--) {
    const sub = ops[i]!;
    out.push(invertOp(cur, sub));
    cur = applyOp(cur, sub);
  }
  return out;
}

function pickChanged<T extends object>(before: T, patch: Partial<T>): Partial<T> {
  const back: Record<string, unknown> = {};
  for (const k of Object.keys(patch) as Array<keyof T>) {
    back[k as string] = before[k];
  }
  return back as Partial<T>;
}

function op0Person(id: string): Person { return { personId: id, label: null, color: null }; }
function op0Box(id: string): Box { return { boxId: id, frameIndex: 0, personId: "", x: 0, y: 0, w: 1, h: 1, zMin: 0, zMax: 2, visibility: "visible", origin: { kind: "human" }, reviewed: false, note: null, updatedAtMs: 0 }; }
function op0Interval(id: string): Interval { return { intervalId: id, personId: "", kind: "action", label: "", startFrame: 0, endFrame: 0, origin: { kind: "human" }, reviewed: false, note: null }; }
function op0Suggestion(id: string): Suggestion { return { suggestionId: id, algorithm: "?", paramsHash: "?", frameIndex: 0, box: { x: 0, y: 0, w: 1, h: 1, zMin: 0, zMax: 2 }, interval: null, reason: null, status: "pending", adoptedRef: null, createdAtMs: 0 }; }

/** 撤销栈。doc 由外部持有；栈只存 Op 与逆 Op。 */
export class UndoHistory {
  private past: Array<{ op: Op; inv: Op }> = [];
  private future: Array<{ op: Op; inv: Op }> = [];
  constructor(private limit = 200) {}

  commit(docBefore: AnnotationDoc, op: Op): { doc: AnnotationDoc; undoable: boolean } {
    const doc = applyOp(docBefore, op);
    const inv = invertOp(docBefore, op);
    this.past.push({ op, inv });
    if (this.past.length > this.limit) this.past.shift();
    this.future = [];
    return { doc, undoable: op.t !== "composite" || op.ops.length > 0 };
  }

  canUndo(): boolean { return this.past.length > 0; }
  canRedo(): boolean { return this.future.length > 0; }

  undo(doc: AnnotationDoc): AnnotationDoc | null {
    const e = this.past.pop();
    if (!e) return null;
    const next = applyOp(doc, e.inv);
    this.future.push(e);
    return next;
  }

  redo(doc: AnnotationDoc): AnnotationDoc | null {
    const e = this.future.pop();
    if (!e) return null;
    const next = applyOp(doc, e.op);
    this.past.push(e);
    return next;
  }

  size(): { past: number; future: number } { return { past: this.past.length, future: this.future.length }; }
}

// ---------- 常用构造器 ----------

export function mkBox(
  frameIndex: number, personId: string,
  geom: { x: number; y: number; w: number; h: number },
  origin: Box["origin"],
  zRange: { zMin: number; zMax: number } = { zMin: 0, zMax: 2.5 },
): Box {
  return {
    boxId: newId("box"), frameIndex, personId,
    x: geom.x, y: geom.y, w: geom.w, h: geom.h,
    zMin: zRange.zMin, zMax: zRange.zMax,
    visibility: "visible", origin, reviewed: false, note: null, updatedAtMs: Date.now(),
  };
}

export function mkPerson(personId: string, label: string | null = null): Person {
  return { personId, label, color: null };
}

export function mkInterval(
  personId: string, kind: Interval["kind"], label: string, startFrame: number, endFrame: number,
): Interval {
  return { intervalId: newId("itv"), personId, kind, label, startFrame, endFrame, origin: { kind: "human" }, reviewed: false, note: null };
}
