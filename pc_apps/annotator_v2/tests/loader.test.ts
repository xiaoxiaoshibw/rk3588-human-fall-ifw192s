// tests/loader.test.ts — 帧加载：LRU 上限、在途去重、代次丢弃（反例 6 前半：
// 快速切帧时旧帧不回写）、切片长度校验。
import { describe, expect, it, vi } from "vitest";
import { SessionLoader, StaleResultError, parseSessionMeta } from "../src/session/loader.ts";
import type { Transport } from "../src/session/loader.ts";
import type { SessionSummary } from "../src/session/types.ts";
import { decodeFrame } from "../src/session/decode.ts";

/** 原始 meta.json 形状（snake_case，与 data/sessions 一致）。 */
function mkRawMeta(nFrames: number) {
  return {
    session_id: "s1",
    format: "human_capture_session",
    point_stride_bytes: 28,
    point_layout: {
      fields: ["x", "y", "z", "intensity", "ring", "timestamp"],
      dtypes: ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
      stride_bytes: 28,
    },
    frames: Array.from({ length: nFrames }, (_, i) => ({
      count_points: 10, offset_points: i * 10, stamp_sec: 100 + i * 0.1,
    })),
  };
}

/** 受控传输：按帧返回Deferred，可手动放行。 */
function mkTransport(nFrames: number) {
  const meta = mkRawMeta(nFrames);
  const pending = new Map<number, Array<(b: ArrayBuffer) => void>>();
  const calls: number[] = [];
  const transport: Transport = {
    async listSessions(): Promise<SessionSummary[]> { return []; },
    async getMeta(): Promise<unknown> { return meta; },
    async getFrameBytes(_sid: string, frameIndex: number): Promise<ArrayBuffer> {
      calls.push(frameIndex);
      return new Promise((resolve) => {
        const list = pending.get(frameIndex) ?? [];
        list.push(resolve);
        pending.set(frameIndex, list);
      });
    },
  };
  return {
    transport, calls,
    resolve(frameIndex: number) {
      const buf = new ArrayBuffer(10 * 28);
      (pending.get(frameIndex) ?? []).forEach((r) => r(buf));
      pending.delete(frameIndex);
    },
  };
}

const instantDecode = async (buf: ArrayBuffer, frame: { countPoints: number }) => decodeFrame(buf, frame as never, false);

describe("SessionLoader", () => {
  it('late metadata from an old session cannot replace the new session',async()=>{
    let release!:(value:unknown)=>void;
    const transport:Transport={listSessions:async()=>[],getFrameBytes:async()=>new ArrayBuffer(0),
      getMeta:async sid=>sid==='old'?new Promise(r=>{release=r}):{...mkRawMeta(2),session_id:sid}};
    const loader=new SessionLoader(transport);
    const old=loader.resetForSession('old');
    await loader.resetForSession('new');
    release({...mkRawMeta(2),session_id:'old'});
    await expect(old).rejects.toBeInstanceOf(StaleResultError);
    expect(loader.getMeta()?.sessionId).toBe('new');
  });
  it("getFrame 缓存命中不重复请求；在途去重（同帧并发只打一次网络）", async () => {
    const t = mkTransport(5);
    const loader = new SessionLoader(t.transport, instantDecode, 8);
    await loader.resetForSession("s1");
    const p1 = loader.getFrame(1);
    const p2 = loader.getFrame(1); // 在途并发
    t.resolve(1);
    const [f1, f2] = await Promise.all([p1, p2]);
    expect(f1?.frameIndex).toBe(1);
    expect(f2).toBe(f1); // 同一结果对象
    await loader.getFrame(1); // 缓存命中
    expect(t.calls.filter((c) => c === 1)).toHaveLength(1);
  });

  it("LRU 有上限：预取/加载超过容量后缓存帧数不超上限（反例 7 内存约束的一部分）", async () => {
    const t = mkTransport(40);
    const loader = new SessionLoader(t.transport, instantDecode, 4);
    await loader.resetForSession("s1");
    for (let i = 0; i < 10; i++) {
      const p = loader.getFrame(i);
      t.resolve(i);
      await p;
    }
    expect(loader.stats().cacheFrames).toBeLessThanOrEqual(4);
    expect(loader.stats().cacheLimit).toBe(4);
  });

  it("换代后过期结果被丢弃：快速切帧旧帧不回写、不占缓存（反例 6）", async () => {
    const t = mkTransport(5);
    const loader = new SessionLoader(t.transport, instantDecode, 8);
    await loader.resetForSession("s1");
    const pOld = loader.getFrame(0);
    loader.bumpGeneration(); // 用户已切走（换会话/显式换代）
    const pNew = loader.getFrame(1);
    t.resolve(0);
    t.resolve(1);
    await expect(pOld).rejects.toBeInstanceOf(StaleResultError);
    const f = await pNew;
    expect(f?.frameIndex).toBe(1);
    expect(loader.peek(0)).toBeUndefined(); // 旧帧没进缓存
    expect(loader.droppedStale).toBe(1);
  });

  it("切片长度不符 → 抛错不污染缓存", async () => {
    const t = mkTransport(5);
    const origResolve = t.resolve.bind(t);
    void origResolve;
    // 直接构造一个短包 transport
    const shortTransport: Transport = {
      async listSessions() { return []; },
      async getMeta() { return mkRawMeta(5); },
      async getFrameBytes() { return new ArrayBuffer(10); }, // 10B ≠ 280B
    };
    const loader = new SessionLoader(shortTransport, instantDecode, 8);
    await loader.resetForSession("s1");
    await expect(loader.getFrame(0)).rejects.toThrow(/slice size/);
    expect(loader.peek(0)).toBeUndefined();
  });

  it("prefetchAround 只发邻域且静默失败", async () => {
    const t = mkTransport(20);
    const loader = new SessionLoader(t.transport, instantDecode, 32);
    await loader.resetForSession("s1");
    loader.prefetchAround(5, 1, 3); // 4..8
    expect(t.calls.sort((a, b) => a - b)).toEqual([4, 5, 6, 7, 8]);
  });
});

describe("parseSessionMeta（边界校验）", () => {
  it("解析真实 meta 结构（含 stamp_nanosec 亚秒）", () => {
    const raw = {
      session_id: "cap_x", total_points: 30, point_stride_bytes: 28,
      point_layout: { fields: ["x", "y", "z"], dtypes: ["<f4"], stride_bytes: 28 },
      frames: [
        { count_points: 10, offset_points: 0, stamp_sec: 1.0, stamp_nanosec: 477752000, bag_time_sec: 2 },
        { count_points: 20, offset_points: 10, stamp_sec: 1.1 },
        { count_points: 5, offset_points: 30, stamp_sec: 1, stamp_nanosec: 577752000 },
      ],
    };
    const m = parseSessionMeta(raw, "cap_x");
    expect(m.frameCount).toBe(3);
    expect(m.frames[0]!.stampSec).toBeCloseTo(1.477752, 6);
    expect(m.frames[1]!.stampSec).toBeCloseTo(1.1, 6);
    expect(m.frames[2]!.stampSec).toBeCloseTo(1.577752, 6);
    expect(m.frames[0]!.bagTimeSec).toBe(2);
    expect(m.frames[1]!.bagTimeSec).toBeNull();
  });
  it("坏结构抛错", () => {
    expect(() => parseSessionMeta({ frames: "x" }, "s")).toThrow();
    expect(() => parseSessionMeta({ frames: [{ count_points: 1 }] }, "s")).toThrow();
  });
});
