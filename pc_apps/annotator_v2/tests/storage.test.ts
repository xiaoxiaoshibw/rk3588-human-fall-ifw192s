// tests/storage.test.ts — v2 序列化往返、坏版本拒绝、v1 迁移导入、保存冲突 409。
import { describe, expect, it, vi, afterEach } from "vitest";
import { parseV2Doc, serializeDoc, parseDraftEnvelope, importV1Doc, FormatError } from "../src/storage/gtFormat.ts";
import { GtClient, SaveConflictError } from "../src/storage/client.ts";
import { emptyDoc, newId } from "../src/domain/types.ts";
import { mkBox, mkPerson, mkInterval } from "../src/annotation/ops.ts";

describe("v2 序列化", () => {
  it("往返保持语义", () => {
    const d = emptyDoc("cap_x", 50, "ann");
    d.persons = [mkPerson("P1")];
    d.boxes = [mkBox(3, "P1", { x: 1, y: 2, w: 0.8, h: 0.6 }, { kind: "human" })];
    d.intervals = [mkInterval("P1", "event", "fall", 3, 8)];
    const back = parseV2Doc(JSON.parse(serializeDoc(d)));
    expect(back.boxes).toHaveLength(1);
    expect(back.boxes[0]!.personId).toBe("P1");
    expect(back.intervals[0]!.label).toBe("fall");
    expect(back.coordinateFrame).toBe("sensor-IFW192S-raw");
  });
  it("版本不符 / 结构坏 → FormatError", () => {
    const d = emptyDoc("cap_x", 10, "");
    expect(() => parseV2Doc({ ...JSON.parse(serializeDoc(d)), formatVersion: 3 })).toThrow(FormatError);
    expect(() => parseV2Doc({ format: "other", formatVersion: 2 })).toThrow(FormatError);
    // 校验失败（未知人物）也拒绝
    const bad = JSON.parse(serializeDoc(d));
    bad.boxes = [mkBox(0, "GHOST", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" })];
    expect(() => parseV2Doc(bad)).toThrow(FormatError);
    expect(()=>parseV2Doc({...d,coordinateFrame:'leveled'})).toThrow(FormatError);
    expect(()=>parseV2Doc({...d,units:'cm'})).toThrow(FormatError);
  });
  it("信封解析：无草稿 / 有草稿", () => {
    expect(parseDraftEnvelope({ version: 0, doc: null })).toEqual({ version: 0, doc: null });
    const d = emptyDoc("cap_x", 10, "");
    const env = { version: 3, saved_at: "2026-10-24", doc: JSON.parse(serializeDoc(d)) };
    const out = parseDraftEnvelope(env);
    expect(out.version).toBe(3);
    expect(out.doc?.sessionId).toBe("cap_x");
  });
});

describe("v1 (gt_workbench/1) 迁移", () => {
  const v1 = {
    schema_version: "gt_workbench/1",
    session_id: "cap_20261010_175227",
    annotator: "old",
    objects: {
      obj_f0_n1: {
        class_name: "FURNITURE", frame_idx: 0,
        polygon_xy: [[1, 2], [2, 2], [2, 1], [1, 1]],
      },
      obj_f1_p1: {
        class_name: "PERSON", frame_idx: 1, track_id: "P1", source: "human", reviewed: true,
        polygon_xy: [[0, 0], [1, 0], [1, 1], [0.5, 1.2], [0, 1]],
      },
      obj_f2_p1: {
        class_name: "PERSON", frame_idx: 2, track_id: "P1", source: "propagated",
        polygon_xy: [[0.1, 0.1], [1.1, 0.1], [1.1, 1.1], [0.1, 1.1]],
      },
      obj_f3_noTrack: {
        class_name: "PERSON", frame_idx: 3,
        polygon_xy: [[0, 0], [1, 0], [1, 1], [0, 1]],
      },
    },
  };

  it("PERSON+track → 人物+外接框；非 PERSON / 无 track 跳过并报告", () => {
    const { doc, report } = importV1Doc(v1, 100);
    expect(report.persons).toBe(1);
    expect(report.boxes).toBe(2);
    expect(report.skippedNonPerson).toBe(1);
    expect(report.skippedNoTrack).toBe(1);
    expect(doc.persons[0]!.personId).toBe("P1");
    const b2 = doc.boxes.find((b) => b.frameIndex === 2)!;
    expect(b2.x).toBeCloseTo(0.6, 5);
    expect(b2.w).toBeCloseTo(1.0, 5);
    expect(b2.origin.kind).toBe("propagated");
    expect(report.warnings.join()).toContain("leveled");
  });
  it("非 v1 schema 拒绝", () => {
    expect(() => importV1Doc({ schema_version: "other" }, 10)).toThrow(FormatError);
  });
});

describe("GtClient 保存（fetch 桩）", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("409 → SaveConflictError 携带服务器版本", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ error: "version conflict", currentVersion: 5 }), { status: 409 })));
    const client = new GtClient();
    const d = emptyDoc("s", 5, "a");
    await expect(client.save(d)).rejects.toMatchObject({ name: "SaveConflictError", currentVersion: 5 });
    expect(new SaveConflictError(5).currentVersion).toBe(5);
  });

  it("成功保存递增版本号", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      calls += 1;
      if (calls === 1) return new Response(JSON.stringify({ version: 2, doc: null }), { status: 200 });
      expect(init?.method).toBe("PUT");
      return new Response(JSON.stringify({ version: 3 }), { status: 200 });
    }));
    const client = new GtClient();
    await client.load("s");
    const d = emptyDoc("s", 5, "a");
    expect(await client.save(d)).toBe(3);
  });
});
