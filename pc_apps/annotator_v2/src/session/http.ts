// session/http.ts — HTTP 传输（对接 pc_apps/annotator_v2/server.py）与 Worker 解码钩子。
import type { SessionSummary, FrameMeta } from "./types.ts";
import type { Transport, DecodeHooks } from "./loader.ts";

const BASE = ""; // 同源（dev 走 vite 代理，生产由 server.py 直接服务）。

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  return (await res.json()) as T;
}

export class HttpTransport implements Transport {
  async listSessions(signal?: AbortSignal): Promise<SessionSummary[]> {
    const data = await fetchJson<{ sessions: SessionSummary[] }>(`${BASE}/api/sessions`, signal);
    return data.sessions;
  }

  async getMeta(sessionId: string, signal?: AbortSignal): Promise<unknown> {
    return fetchJson<unknown>(`${BASE}/api/session/${encodeURIComponent(sessionId)}/meta`, signal);
  }

  async getFrameBytes(sessionId: string, frameIndex: number, signal?: AbortSignal): Promise<ArrayBuffer> {
    const res = await fetch(
      `${BASE}/api/session/${encodeURIComponent(sessionId)}/frame/${frameIndex}`,
      { signal },
    );
    if (!res.ok) throw new Error(`GET frame ${frameIndex} → ${res.status}`);
    return res.arrayBuffer();
  }
}

/** Worker 解码钩子：一个 Worker 复用；主线程仅排队请求。强度当前视图不用，不解码。 */
export function makeWorkerDecode(): DecodeHooks["decode"] {
  let worker: Worker | null = null;
  let reqSeq = 0;
  const pending = new Map<number, {
    resolve: (v: { x: Float32Array; y: Float32Array; z: Float32Array; intensity: Float32Array | null }) => void;
    reject: (e: Error) => void;
  }>();
  const ensureWorker = (): Worker => {
    if (worker) return worker;
    worker = new Worker(new URL("./decodeWorker.ts", import.meta.url), { type: "module" });
    worker.onmessage = (ev: MessageEvent) => {
      const msg = ev.data as {
        type: "decoded" | "error"; reqId: number;
        x?: Float32Array; y?: Float32Array; z?: Float32Array; intensity?: Float32Array | null;
        count?: number; message?: string;
      };
      const p = pending.get(msg.reqId);
      if (!p) return;
      pending.delete(msg.reqId);
      if (msg.type === "decoded" && msg.x && msg.y && msg.z) {
        p.resolve({ x: msg.x, y: msg.y, z: msg.z, intensity: msg.intensity ?? null });
      } else {
        p.reject(new Error(msg.message ?? "decode worker error"));
      }
    };
    worker.onerror = () => {
      for (const p of pending.values()) p.reject(new Error("decode worker crashed"));
      pending.clear();
    };
    return worker;
  };
  return async (buf: ArrayBuffer, frame: FrameMeta) => {
    const w = ensureWorker();
    const reqId = ++reqSeq;
    const transferred = buf; // 转移所有权
    return new Promise((resolve, reject) => {
      pending.set(reqId, { resolve, reject });
      w.postMessage(
        { type: "decode", reqId, buffer: transferred, frame, withIntensity: false },
        [transferred],
      );
    });
  };
}
