// session/loader.ts — 帧加载：LRU 上限、预取、取消、代次防过期。
// 请求与结果都带 sessionId+frameIndex+generation；换代后旧结果作废丢弃，
// 不覆盖当前帧（规范十二：快速切帧时过期结果不能回写）。
import type { DecodedFrame, FrameMeta, SessionMeta, SessionSummary } from "./types.ts";
import { decodeFrame } from "./decode.ts";

export interface Transport {
  listSessions(signal?: AbortSignal): Promise<SessionSummary[]>;
  getMeta(sessionId: string, signal?: AbortSignal): Promise<unknown>;
  getFrameBytes(sessionId: string, frameIndex: number, signal?: AbortSignal): Promise<ArrayBuffer>;
}

/** LRU（Map 迭代序 = 插入序，命中时重插到末尾）。 */
class Lru<K, V> {
  private map = new Map<K, V>();
  constructor(private capacity: number) {}
  get(key: K): V | undefined {
    const v = this.map.get(key);
    if (v !== undefined) {
      this.map.delete(key);
      this.map.set(key, v);
    }
    return v;
  }
  set(key: K, value: V): void {
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, value);
    while (this.map.size > this.capacity) {
      const oldest = this.map.keys().next();
      if (oldest.done) break;
      this.map.delete(oldest.value);
    }
  }
  has(key: K): boolean { return this.map.has(key); }
  peekSize(): number { return this.map.size; }
  clear(): void { this.map.clear(); }
  keys(): K[] { return [...this.map.keys()]; }
}

export interface LoaderStats {
  cacheFrames: number;
  inFlight: number;
  cacheLimit: number;
  droppedStale: number;
}

export interface DecodeHooks {
  /** 默认主线程解码；浏览器注入 Worker 版本（转移缓冲）。 */
  decode(buf: ArrayBuffer, frame: FrameMeta): Promise<{ x: Float32Array; y: Float32Array; z: Float32Array; intensity: Float32Array | null }>;
}

export const mainThreadDecode: DecodeHooks["decode"] = async (buf, frame) => decodeFrame(buf, frame, true);

export class SessionLoader {
  private meta: SessionMeta | null = null;
  private cache = new Lru<number, DecodedFrame>(24);
  private inFlight = new Map<number, Promise<DecodedFrame>>();
  private reqSeq = 0;
  /** 每次换会话或显式换目标时 +1；旧异步结果按 generation 丢弃。 */
  private generation = 0;
  droppedStale = 0;

  constructor(
    private transport: Transport,
    private decodeHook: DecodeHooks["decode"] = mainThreadDecode,
    cacheFrames = 24,
  ) {
    this.cache = new Lru<number, DecodedFrame>(cacheFrames);
  }

  /** 换会话：清缓存、作废在途请求。 */
  resetForSession(sessionId: string): Promise<SessionMeta> {
    this.generation += 1;
    this.cache.clear();
    for (const p of this.inFlight.values()) p.catch(() => undefined); // 防 unhandledrejection
    this.inFlight.clear();
    this.meta = null;
    return this.loadMeta(sessionId);
  }

  bumpGeneration(): void {
    this.generation += 1;
  }

  getGeneration(): number { return this.generation; }

  private async loadMeta(sessionId: string): Promise<SessionMeta> {
    const generation = this.generation;
    const raw = await this.transport.getMeta(sessionId);
    if (generation !== this.generation) throw new StaleResultError(sessionId, -1, generation);
    const meta = parseSessionMeta(raw, sessionId);
    this.meta = meta;
    return meta;
  }

  getMeta(): SessionMeta | null { return this.meta; }

  /** 取帧：命中缓存直接回；否则网络+解码。世代不匹配返回 null（调用方放弃）。 */
  async getFrame(frameIndex: number, opts: { signal?: AbortSignal } = {}): Promise<DecodedFrame | null> {
    const meta = this.meta;
    if (!meta) throw new Error("session meta not loaded");
    if (frameIndex < 0 || frameIndex >= meta.frameCount) throw new RangeError(`frame ${frameIndex} out of range`);
    const gen = this.generation;
    const sid = meta.sessionId;
    const cached = this.cache.get(frameIndex);
    if (cached) return cached;
    const existing = this.inFlight.get(frameIndex);
    if (existing) return existing;
    const frame = meta.frames[frameIndex]!;
    const reqId = ++this.reqSeq;
    const p = (async (): Promise<DecodedFrame> => {
      const buf = await this.transport.getFrameBytes(sid, frameIndex, opts.signal);
      // 服务端切片可能按实际读到的字节返回；长度不符则视为坏帧。
      if (buf.byteLength !== frame.countPoints * meta.pointStrideBytes) {
        throw new Error(`frame ${frameIndex} slice size ${buf.byteLength} != ${frame.countPoints * meta.pointStrideBytes}`);
      }
      const decoded = await this.decodeHook(buf, frame);
      if (this.generation !== gen || this.meta?.sessionId !== sid) {
        this.droppedStale += 1;
        throw new StaleResultError(sid, frameIndex, gen);
      }
      const out: DecodedFrame = {
        sessionId: sid, frameIndex, stampSec: frame.stampSec,
        count: frame.countPoints, ...decoded, generation: gen,
      };
      this.cache.set(frameIndex, out);
      return out;
    })();
    this.inFlight.set(frameIndex, p);
    try {
      return await p;
    } finally {
      if (this.inFlight.get(frameIndex) === p) this.inFlight.delete(frameIndex);
      void reqId;
    }
  }

  /** 预取目标帧邻域（播放/步进用）。失败静默（缓存缺失不算错误）。 */
  prefetchAround(center: number, back = 1, forward = 4): void {
    const meta = this.meta;
    if (!meta) return;
    const lo = Math.max(0, center - back);
    const hi = Math.min(meta.frameCount - 1, center + forward);
    for (let i = lo; i <= hi; i++) {
      if (this.cache.has(i) || this.inFlight.has(i)) continue;
      void this.getFrame(i).catch(() => undefined);
    }
  }

  peek(frameIndex: number): DecodedFrame | undefined { return this.cache.get(frameIndex); }

  stats(): LoaderStats {
    return {
      cacheFrames: this.cache.peekSize(),
      inFlight: this.inFlight.size,
      cacheLimit: (this.cache as unknown as { capacity: number }).capacity,
      droppedStale: this.droppedStale,
    };
  }
}

export class StaleResultError extends Error {
  constructor(sessionId: string, frameIndex: number, generation: number) {
    super(`stale result ${sessionId}#${frameIndex} gen=${generation}`);
    this.name = "StaleResultError";
  }
}

/** meta.json 原始 JSON → SessionMeta（边界处校验，出错抛异常）。 */
export function parseSessionMeta(raw: unknown, sessionId: string): SessionMeta {
  if (typeof raw !== "object" || raw === null) throw new Error("meta: not an object");
  const r = raw as Record<string, unknown>;
  const framesRaw = r["frames"];
  if (!Array.isArray(framesRaw)) throw new Error("meta: frames missing");
  const stride = typeof r["point_stride_bytes"] === "number" ? r["point_stride_bytes"] : 28;
  const layout = (r["point_layout"] ?? {}) as Record<string, unknown>;
  const fields = Array.isArray(layout["fields"]) ? (layout["fields"] as string[]) : ["x", "y", "z", "intensity", "ring", "timestamp"];
  const dtypes = Array.isArray(layout["dtypes"]) ? (layout["dtypes"] as string[]) : [];
  const frames: FrameMeta[] = framesRaw.map((f, i) => {
    if (typeof f !== "object" || f === null) throw new Error(`meta: frame ${i} malformed`);
    const fo = f as Record<string, unknown>;
    const count = fo["count_points"];
    const offset = fo["offset_points"];
    const stamp = fo["stamp_sec"];
    if (typeof count !== "number" || typeof offset !== "number" || typeof stamp !== "number")
      throw new Error(`meta: frame ${i} missing count/offset/stamp`);
    // stamp_sec 是整秒，亚秒部分在 stamp_nanosec（丢了会按秒跳帧，破坏 10Hz 逐帧播放）。
    const nano = fo["stamp_nanosec"];
    const bag = fo["bag_time_sec"];
    return {
      frameIndex: i, offsetPoints: offset, countPoints: count,
      stampSec: stamp + (typeof nano === "number" ? nano / 1e9 : 0),
      bagTimeSec: typeof bag === "number" ? bag : null,
    };
  });
  const extraction = (r["extraction"] ?? {}) as Record<string, unknown>;
  const sha = extraction["source_bag_sha256"];
  return {
    sessionId,
    frameCount: frames.length,
    totalPoints: typeof r["total_points"] === "number" ? r["total_points"] : frames.reduce((s, f) => s + f.countPoints, 0),
    pointStrideBytes: stride,
    fields, dtypes, frames,
    sourceBagSha256: typeof sha === "string" ? sha : null,
  };
}
