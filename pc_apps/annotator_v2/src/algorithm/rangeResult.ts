import type { AlgorithmAdapter, AlgorithmContext, RawSuggestion } from './types.ts';

export interface RangeResult {
  manifest: { sessionId: string; coordinateFrame: string; units: string; confirmedEnabled: boolean;
    contentSha256: string; sourceFrameCount: number; algorithm: { id: string; version: string; configSha256: string } };
  frame: { frameIndex: number; stampSec: number; state: string; reasons: string[]; trackId: string | null;
    generation: number; measured: boolean; sourceRows: number[]; heightMedianM: number | null;
    rawSha256?: string;
    groundAlert?: { variant: 'ground_alert_v1'; state: string; active: boolean; durationSec: number;
      triggerFrame: number | null; semantic: 'UNKNOWN'; confirmedEnabled: false };
    posture?: { state: string; reason: string; durationSec: number; humanSemantic: 'UNKNOWN'; fallEvent: false };
    depth?: { version: number; width: number; height: number; validPixels: number; targetPixels: number; overflowPixels: number };
    box: { x: number; y: number; w: number; h: number; zMin: number; zMax: number } | null };
  intervals: { startFrame: number; endFrame: number; label: string }[];
  allIntervals?: { startFrame: number; endFrame: number; label: string; triggerFrame?: number | null }[];
}

export async function fetchRangeResult(sessionId: string, frameIndex: number, signal?: AbortSignal): Promise<RangeResult> {
  const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/analysis?frame=${frameIndex}`, { cache: 'no-store', signal });
  if (!response.ok) throw new Error(`识别结果不可用 HTTP ${response.status}：${await response.text()}`);
  const packet = await response.json() as RangeResult;
  if (packet.manifest.sessionId !== sessionId || packet.frame.frameIndex !== frameIndex
      || packet.manifest.coordinateFrame !== 'sensor-IFW192S-raw' || packet.manifest.units !== 'm'
      || packet.manifest.confirmedEnabled !== false || packet.frame.state === 'confirmed'
      || !/^[a-f0-9]{64}$/.test(packet.manifest.algorithm.configSha256)) {
    throw new Error('识别结果来源或坐标契约不匹配');
  }
  return packet;
}

export function makeRangeAdapter(packet: RangeResult): AlgorithmAdapter {
  const { manifest, frame, intervals } = packet;
  return {
    id: manifest.algorithm.id, version: manifest.algorithm.version,
    paramsHash: manifest.algorithm.configSha256, displayName: '距离图跟踪与跌倒规则',
    async run(ctx: AlgorithmContext): Promise<RawSuggestion[]> {
      if (ctx.sessionId !== manifest.sessionId || ctx.frameIndex !== frame.frameIndex
          || ctx.doc.frameCount !== manifest.sourceFrameCount || ctx.frame?.stampSec !== frame.stampSec) {
        throw new Error('识别结果与当前源帧不匹配');
      }
      const result: RawSuggestion[] = [];
      const b = frame.box;
      if (frame.measured && b) {
        if (![b.x,b.y,b.w,b.h,b.zMin,b.zMax].every(Number.isFinite) || b.w <= 0 || b.h <= 0 || b.zMax <= b.zMin) {
          throw new Error('当前目标几何不足以形成标注框');
        }
        if (!ctx.frame || new Set(frame.sourceRows).size !== frame.sourceRows.length
            || frame.sourceRows.some(i => !Number.isInteger(i) || i < 0 || i >= ctx.frame!.count)) {
          throw new Error('目标来源行越界');
        }
        result.push({ kind: 'box', ...b,
          reason: `${frame.state}；目标 ${frame.trackId ?? 'UNKNOWN'}；人体语义 UNKNOWN；结果 ${manifest.contentSha256}` });
      }
      for (const interval of intervals) {
        if (!['suspected_fall','sustained_low_posture'].includes(interval.label) || interval.startFrame < 0 || interval.endFrame >= ctx.doc.frameCount
            || interval.startFrame > frame.frameIndex || interval.endFrame < frame.frameIndex) {
          throw new Error('疑似区间绑定错误');
        }
        result.push({ kind: 'interval', kindOf: interval.label === 'sustained_low_posture' ? 'action' : 'event', ...interval,
          reason: `${interval.label === 'sustained_low_posture' ? '持续低姿态；蹲坐地也触发，不是跌倒事件' : '几何疑似，未经人体真值验证'}；结果 ${manifest.contentSha256}` });
      }
      return result;
    },
  };
}
