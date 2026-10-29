// tests/sparse.test.ts — 稀疏标注：取样生成、覆盖统计、清单操作（可撤销）、
// 存储兼容（旧文档无 sampleFrames 字段按空表解析）。
import { describe, expect, it } from "vitest";
import { emptyDoc, sampleEveryN, sampleCoverage, annotatedFrameSet } from "../src/domain/types.ts";
import { applyOp, invertOp, mkBox, mkPerson } from "../src/annotation/ops.ts";
import type { Op } from "../src/annotation/ops.ts";
import { parseV2Doc, serializeDoc } from "../src/storage/gtFormat.ts";
import { validateDoc } from "../src/domain/validation.ts";

describe("sampleEveryN", () => {
  it("含起点、步进钳制", () => {
    expect(sampleEveryN(10, 25)).toEqual([0]); // 126 帧每 25 帧 → 0,25,50...
    expect(sampleEveryN(126, 25)).toEqual([0, 25, 50, 75, 100, 125]);
    expect(sampleEveryN(100, 3, 10)).toEqual([10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 52, 55, 58, 61, 64, 67, 70, 73, 76, 79, 82, 85, 88, 91, 94, 97]);
    expect(sampleEveryN(5, 0)).toEqual([0, 1, 2, 3, 4]); // n 至少 1
    expect(sampleEveryN(5, 2, -3)).toEqual([0, 2, 4]); // 负起点钳到 0
  });
});

describe("sampleCoverage / annotatedFrameSet", () => {
  it("清单内已标/未标、清单外已标分列", () => {
    const d = emptyDoc("s", 100, "");
    d.persons = [mkPerson("P1")];
    d.boxes = [
      mkBox(10, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" }),
      mkBox(50, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" }),
      mkBox(77, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" }), // 清单外
    ];
    d.sampleFrames = [10, 25, 50];
    expect([...annotatedFrameSet(d)].sort((a, b) => a - b)).toEqual([10, 50, 77]);
    const cov = sampleCoverage(d);
    expect(cov).toEqual({ total: 3, annotated: 2, missing: [25] });
  });
});

describe("setSampleFrames 操作", () => {
  it("整表替换 + 排序；撤销恢复旧表", () => {
    const d = emptyDoc("s", 100, "");
    d.sampleFrames = [5, 3];
    const op: Op = { t: "setSampleFrames", frames: [50, 10, 30] };
    const d2 = applyOp(d, op);
    expect(d2.sampleFrames).toEqual([10, 30, 50]);
    const d3 = applyOp(d2, invertOp(d, op));
    expect(d3.sampleFrames).toEqual([3, 5]); // 逆操作同样按序规范化（集合不变）
    expect(validateDoc(d2).filter((i) => i.level === "error")).toHaveLength(0);
  });
  it("越界清单帧为校验 error", () => {
    const d = emptyDoc("s", 10, "");
    d.sampleFrames = [3, 99];
    const codes = validateDoc(d).filter((i) => i.level === "error").map((i) => i.code);
    expect(codes).toContain("sample.frame-range");
  });
});

describe("存储兼容", () => {
  it("旧文档（无 sampleFrames）按空表解析；往返保留；坏值过滤", () => {
    const d = emptyDoc("s", 10, "");
    const back = parseV2Doc(JSON.parse(serializeDoc(d)));
    expect(back.sampleFrames).toEqual([]);
    d.sampleFrames = [1, 2, 3];
    expect(parseV2Doc(JSON.parse(serializeDoc(d))).sampleFrames).toEqual([1, 2, 3]);
    const raw = JSON.parse(serializeDoc(d));
    delete raw.sampleFrames;
    expect(parseV2Doc(raw).sampleFrames).toEqual([]);
    raw.sampleFrames = [2, -1, "x", 5];
    expect(parseV2Doc(raw).sampleFrames).toEqual([2, 5]);
  });
});
