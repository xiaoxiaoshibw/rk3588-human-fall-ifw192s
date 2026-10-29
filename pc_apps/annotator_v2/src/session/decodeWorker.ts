// session/decodeWorker.ts — 解码 Worker。协议：
// 主线程 → worker: {type:"decode", reqId, buffer(转移), frame, withIntensity}
// worker → 主线程: {type:"decoded", reqId, x,y,z,intensity(转移), count}
//              | {type:"error", reqId, message}
import { decodeFrame } from "./decode.ts";

interface DecodeRequest {
  type: "decode";
  reqId: number;
  buffer: ArrayBuffer;
  frame: { frameIndex: number; offsetPoints: number; countPoints: number; stampSec: number; bagTimeSec: number | null };
  withIntensity: boolean;
}

self.onmessage = (ev: MessageEvent<DecodeRequest>) => {
  const msg = ev.data;
  if (msg.type !== "decode") return;
  try {
    const out = decodeFrame(msg.buffer, msg.frame, msg.withIntensity);
    const transfer: Transferable[] = [out.x.buffer, out.y.buffer, out.z.buffer];
    if (out.intensity) transfer.push(out.intensity.buffer);
    (self as unknown as Worker).postMessage(
      { type: "decoded", reqId: msg.reqId, count: msg.frame.countPoints, ...out },
      transfer,
    );
  } catch (err) {
    (self as unknown as Worker).postMessage({
      type: "error", reqId: msg.reqId,
      message: err instanceof Error ? err.message : String(err),
    });
  }
};
