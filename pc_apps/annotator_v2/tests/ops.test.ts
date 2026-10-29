// tests/ops.test.ts — 编辑操作与撤销/重做：一次拖动 = 一条撤销记录；复合逆序；
// 建议操作可撤销；removePerson 级联可恢复。
import { describe, expect, it } from "vitest";
import { applyOp, invertOp, UndoHistory, mkBox, mkPerson, mkInterval } from "../src/annotation/ops.ts";
import type { Op } from "../src/annotation/ops.ts";
import { emptyDoc, newId } from "../src/domain/types.ts";
import { validateDoc, hasErrors } from "../src/domain/validation.ts";

function baseDoc() {
  const d = emptyDoc("s1", 100, "tester");
  d.persons = [mkPerson("P1"), mkPerson("P2")];
  return d;
}

describe("applyOp / invertOp", () => {
  it("addBox → invert → 无框", () => {
    const d = baseDoc();
    const box = mkBox(3, "P1", { x: 1, y: 1, w: 0.8, h: 0.6 }, { kind: "human" });
    const d2 = applyOp(d, { t: "addBox", box });
    expect(d2.boxes).toHaveLength(1);
    const d3 = applyOp(d2, invertOp(d, { t: "addBox", box }));
    expect(d3.boxes).toHaveLength(0);
    // 原对象不被修改
    expect(d.boxes).toHaveLength(0);
  });

  it("updateBox 逆 = 回到旧值", () => {
    const d = baseDoc();
    const box = mkBox(3, "P1", { x: 1, y: 1, w: 0.8, h: 0.6 }, { kind: "human" });
    const d2 = applyOp(d, { t: "addBox", box });
    const d3 = applyOp(d2, { t: "updateBox", boxId: box.boxId, patch: { x: 9, w: 2 } });
    expect(d3.boxes[0]!.x).toBe(9);
    const inv = invertOp(d2, { t: "updateBox", boxId: box.boxId, patch: { x: 9, w: 2 } });
    const d4 = applyOp(d3, inv);
    expect(d4.boxes[0]!.x).toBe(1);
    expect(d4.boxes[0]!.w).toBe(0.8);
  });

  it("removePerson 级联删除且可整体恢复", () => {
    const d = baseDoc();
    const b1 = mkBox(0, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" });
    const b2 = mkBox(1, "P1", { x: 1, y: 1, w: 1, h: 1 }, { kind: "human" });
    const itv = mkInterval("P1", "action", "walk", 0, 9);
    let cur = applyOp(d, { t: "addBox", box: b1 });
    cur = applyOp(cur, { t: "addBox", box: b2 });
    cur = applyOp(cur, { t: "addInterval", interval: itv });
    const op = { t: "removePerson", personId: "P1" } as const;
    const inv = invertOp(cur, op);
    const after = applyOp(cur, op);
    expect(after.persons.map((p) => p.personId)).toEqual(["P2"]);
    expect(after.boxes).toHaveLength(0);
    expect(after.intervals).toHaveLength(0);
    const restored = applyOp(after, inv);
    expect(restored.persons.map((p) => p.personId)).toContain("P1");
    expect(restored.boxes).toHaveLength(2);
    expect(restored.intervals).toHaveLength(1);
  });

  it("addSuggestion 撤销后建议消失", () => {
    const d = baseDoc();
    const sug = {
      suggestionId: newId("sug"), algorithm: "demo@0.1", paramsHash: "h",
      frameIndex: 0,
      box: { x: 0, y: 0, w: 1, h: 1, zMin: 0, zMax: 2 }, interval: null,
      reason: null, status: "pending" as const, adoptedRef: null, createdAtMs: 1,
    };
    const d2 = applyOp(d, { t: "addSuggestion", suggestion: sug });
    expect(d2.suggestions).toHaveLength(1);
    const inv = invertOp(d, { t: "addSuggestion", suggestion: sug });
    expect(applyOp(d2, inv).suggestions).toHaveLength(0);
  });
});

describe("UndoHistory", () => {
  it("拖动提交（单 updateBox）是一条记录：undo 一次回到原位", () => {
    const h = new UndoHistory();
    const d = baseDoc();
    const box = mkBox(0, "P1", { x: 1, y: 1, w: 1, h: 1 }, { kind: "human" });
    const d1 = h.commit(d, { t: "addBox", box }).doc;
    const d2 = h.commit(d1, { t: "updateBox", boxId: box.boxId, patch: { x: 5, y: 5 } }).doc;
    expect(d2.boxes[0]!.x).toBe(5);
    const d3 = h.undo(d2)!;
    expect(d3.boxes[0]!.x).toBe(1);
    const d4 = h.redo(d3)!;
    expect(d4.boxes[0]!.x).toBe(5);
    expect(h.size()).toEqual({ past: 2, future: 0 });
  });

  it("复合（采用建议 = addBox + updateSuggestion）undo 一次全部回退", () => {
    const h = new UndoHistory();
    const d = baseDoc();
    const sug = {
      suggestionId: newId("sug"), algorithm: "demo@0.1", paramsHash: "h",
      frameIndex: 0,
      box: { x: 2, y: 2, w: 0.8, h: 0.8, zMin: 0, zMax: 2 }, interval: null,
      reason: null, status: "pending" as const, adoptedRef: null, createdAtMs: 1,
    };
    const d1 = h.commit(d, { t: "addSuggestion", suggestion: sug }).doc;
    const box = mkBox(0, "P1", sug.box!, { kind: "adopted", fromSuggestionId: sug.suggestionId, algorithm: "demo@0.1" });
    const composite: Op = {
      t: "composite", label: "采用建议",
      ops: [
        { t: "addBox", box },
        { t: "updateSuggestion", suggestionId: sug.suggestionId, patch: { status: "accepted" as const, adoptedRef: box.boxId } },
      ],
    };
    const d2 = h.commit(d1, composite).doc;
    expect(d2.boxes).toHaveLength(1);
    expect(d2.suggestions[0]!.status).toBe("accepted");
    const d3 = h.undo(d2)!;
    expect(d3.boxes).toHaveLength(0);
    expect(d3.suggestions[0]!.status).toBe("pending");
    expect(validateDoc(d2).filter((i) => i.level === "error")).toHaveLength(0);
    expect(hasErrors(validateDoc(d3))).toBe(false);
  });

  it("历史超限丢弃最旧", () => {
    const h = new UndoHistory(3);
    let d = baseDoc();
    for (let i = 0; i < 5; i++) {
      d = h.commit(d, { t: "addPerson", person: mkPerson(`X${i}`) }).doc;
    }
    expect(d.persons).toHaveLength(7); // P1 P2 + 5
    expect(h.size().past).toBe(3);
    for (let i = 0; i < 3; i++) d = h.undo(d)!;
    expect(d.persons.map((p) => p.personId)).toEqual(["P1", "P2", "X0", "X1"]);
  });
});
