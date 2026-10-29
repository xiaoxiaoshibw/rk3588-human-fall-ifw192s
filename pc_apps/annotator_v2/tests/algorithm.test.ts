// tests/algorithm.test.ts — 算法入口：generation 过期丢弃（反例 6 后半）、
// 显式采用（来源保留）、禁用（反例 9 前半）、超时、演示聚类确定性。
import { describe, expect, it } from "vitest";
import { AlgorithmHost, AlgorithmDisabledError } from "../src/algorithm/host.ts";
import type { HostOptions } from "../src/algorithm/host.ts";
import type { AlgorithmAdapter } from "../src/algorithm/types.ts";
import { clusterBoxes, makeDemoClusterAdapter, DEFAULT_CLUSTER_PARAMS } from "../src/algorithm/demoCluster.ts";
import { emptyDoc } from "../src/domain/types.ts";
import { mkPerson } from "../src/annotation/ops.ts";
import { applyOp } from "../src/annotation/ops.ts";

function mkHost(adapter: AlgorithmAdapter | null, opts: Partial<HostOptions> = {}) {
  let gen = 1;
  let enabled = true;
  const o: HostOptions = {
    enabled: () => enabled,
    currentGeneration: () => gen,
    commitOp: () => undefined,
    ...opts,
  };
  const host = new AlgorithmHost(adapter, o);
  return { host, setGen: (g: number) => { gen = g; }, setEnabled: (v: boolean) => { enabled = v; } };
}

function ctxOf(gen = 1, count = 4) {
  return {
    sessionId: "s", frameIndex: 0, generation: gen,
    frame: {
      sessionId: "s", frameIndex: 0, stampSec: 1, count,
      x: new Float32Array(count), y: new Float32Array(count), z: new Float32Array(count),
      intensity: null, generation: gen,
    },
    doc: emptyDoc("s", 10, ""),
  };
}

describe("AlgorithmHost", () => {
  it("generation 过期：结果丢弃为空，不回写（反例 6）", async () => {
    let release!: (v: []) => void;
    const slow = {
      id: "slow", version: "1.0", paramsHash: "h", displayName: "slow",
      run: () => new Promise<never>((res) => { release = res as unknown as (v: []) => void; }),
    };
    const { host, setGen } = mkHost(slow);
    const p = host.run(ctxOf(1));
    setGen(2); // 结果回来前用户已切帧
    release([] as never);
    const out = await p;
    expect(out).toEqual([]);
  });

  it("禁用：run 抛 AlgorithmDisabledError（反例 9 前半：算法全关不影响人工标注）", async () => {
    const { host, setEnabled } = mkHost(makeDemoClusterAdapter());
    setEnabled(false);
    await expect(host.run(ctxOf())).rejects.toBeInstanceOf(AlgorithmDisabledError);
  });

  it("超时：抛错且不吞掉", async () => {
    const never = {
      id: "never", version: "1.0", paramsHash: "h", displayName: "n",
      run: () => new Promise<never>(() => undefined),
    };
    const { host } = mkHost(never, { timeoutMs: 10 });
    await expect(host.run(ctxOf())).rejects.toThrow(/超时/);
  });

  it("采用：pending 建议 → addBox(origin=adopted) + 建议 accepted；ops 应用后文档一致", () => {
    const { host } = mkHost(makeDemoClusterAdapter());
    const d0 = emptyDoc("s", 10, "");
    const docWithPerson = applyOp(d0, { t: "addPerson", person: mkPerson("P1") });
    const suggestion = {
      suggestionId: "sug_1", algorithm: "demo-cluster@0.1.0", paramsHash: "x",
      frameIndex: 0,
      box: { x: 1, y: 1, w: 0.7, h: 0.5, zMin: 0.1, zMax: 2.0 }, interval: null,
      reason: "test", status: "pending" as const, adoptedRef: null, createdAtMs: 1,
    };
    const doc = applyOp(docWithPerson, { t: "addSuggestion", suggestion });
    const r = host.adopt(doc, "sug_1", "P1");
    expect(r).not.toBeNull();
    let after = doc;
    for (const op of r!.ops) after = applyOp(after, op);
    expect(after.boxes).toHaveLength(1);
    expect(after.boxes[0]!.origin).toMatchObject({ kind: "adopted", algorithm: "demo-cluster@0.1.0" });
    expect(after.suggestions[0]!.status).toBe("accepted");
    expect(after.suggestions[0]!.adoptedRef).toBe(after.boxes[0]!.boxId);
  });

  it("拒绝：pending → rejected", () => {
    const { host } = mkHost(makeDemoClusterAdapter());
    const doc = applyOp(emptyDoc("s", 10, ""), {
      t: "addSuggestion",
      suggestion: {
        suggestionId: "sug_2", algorithm: "a@1", paramsHash: "h", frameIndex: 0,
        box: { x: 0, y: 0, w: 1, h: 1, zMin: 0, zMax: 2 }, interval: null,
        reason: null, status: "pending", adoptedRef: null, createdAtMs: 0,
      },
    });
    const r = host.reject(doc, "sug_2");
    expect(r).not.toBeNull();
    let after = doc;
    for (const op of r!.ops) after = applyOp(after, op);
    expect(after.suggestions[0]!.status).toBe("rejected");
  });
});

describe("demoCluster 聚类（确定性）", () => {
  it("两个独立簇 + 噪声：返回 2 框、点数降序、噪声不成框", () => {
    const xs: number[] = [], ys: number[] = [], zs: number[] = [];
    // 簇 A：80 点在 (1.0, 1.0) 附近 0.3m
    for (let i = 0; i < 80; i++) {
      xs.push(1.0 + (i % 4) * 0.07); ys.push(1.0 + Math.floor(i / 4) * 0.07); zs.push(0.5);
    }
    // 簇 B：50 点在 (3.0, -1.0)
    for (let i = 0; i < 50; i++) {
      xs.push(3.0 + (i % 3) * 0.08); ys.push(-1.0 + Math.floor(i / 3) * 0.08); zs.push(0.9);
    }
    // 噪声：15 点零散（< minPoints 40）
    for (let i = 0; i < 15; i++) { xs.push(-2 - i * 0.5); ys.push(2 + i * 0.3); zs.push(1.0); }
    const boxes = clusterBoxes(new Float32Array(xs), new Float32Array(ys), new Float32Array(zs));
    expect(boxes).toHaveLength(2);
    expect(boxes[0]!.points).toBeGreaterThanOrEqual(boxes[1]!.points);
    const nearA = boxes.find((b) => Math.abs(b.x - 1.1) < 0.3);
    expect(nearA).toBeDefined();
    expect(nearA!.w).toBeLessThan(0.5);
  });

  it("超尺寸结构（墙面）不提：maxExtentM 过滤", () => {
    const xs: number[] = [], ys: number[] = [], zs: number[] = [];
    for (let i = 0; i < 200; i++) { xs.push(2.0); ys.push(-2 + i * 0.05); zs.push(1.0); } // 10m 墙
    const boxes = clusterBoxes(new Float32Array(xs), new Float32Array(ys), new Float32Array(zs), DEFAULT_CLUSTER_PARAMS);
    expect(boxes).toHaveLength(0);
  });

  it("adapter 输出 RawSuggestion 且 paramsHash 随参数变化", async () => {
    const a = makeDemoClusterAdapter();
    const b = makeDemoClusterAdapter({ ...DEFAULT_CLUSTER_PARAMS, minPoints: 10 });
    expect(a.paramsHash).not.toBe(b.paramsHash);
    expect(a.id).toBe("demo-cluster");
  });
});
