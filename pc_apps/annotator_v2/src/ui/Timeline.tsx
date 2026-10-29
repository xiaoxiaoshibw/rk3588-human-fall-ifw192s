// ui/Timeline.tsx — 时间轴：播放控制、拖动寻址（Pointer Events + 捕获）、
// 动作/事件区间条、播放头。暂停/逐帧精确对应源帧（PlaybackClock 保证）。
import React, { useEffect, useRef, useState } from "react";
import type { AnnotationDoc } from "../domain/types.ts";
import type { SessionMeta } from "../session/types.ts";
import type { PlaybackClock } from "../timeline/clock.ts";
import { frameToX, xToFrame, formatStamp } from "../timeline/clock.ts";
import type { LoaderStats } from "../session/loader.ts";

export interface TimelineProps {
  meta: SessionMeta | null;
  frameIndex: number;
  playing: boolean;
  clock: PlaybackClock | null;
  onTogglePlay(): void;
  onSeek(frame: number): void;
  onStep(delta: number): void;
  doc: AnnotationDoc | null;
  personColorOf(doc: AnnotationDoc | null, personId: string): string;
  frameStatus: string;
  cacheStats?: LoaderStats;
  /** 有框的帧（稀疏标注标记）。 */
  annotatedFrames: number[];
  algorithmIntervals?: { startFrame: number; endFrame: number; label: string; triggerFrame?: number | null }[];
}

export function Timeline(p: TimelineProps) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const [trackW, setTrackW] = useState(600);
  const [rate, setRate] = useState(1);
  const [jumpTo, setJumpTo] = useState("");

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setTrackW(el.clientWidth));
    ro.observe(el);
    setTrackW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    p.clock?.setRate(rate);
  }, [p.clock, rate]);

  if (!p.meta) {
    return <div className="timeline"><div className="controls"><span className="frameinfo">未打开会话</span></div></div>;
  }
  const layout = { widthPx: Math.max(1, trackW - 2), frameCount: p.meta.frameCount };
  const stamp = p.meta.frames[p.frameIndex]?.stampSec ?? 0;

  const frameFromEvent = (e: React.PointerEvent<HTMLDivElement>): number => {
    const rect = e.currentTarget.getBoundingClientRect();
    return xToFrame(layout, e.clientX - rect.left);
  };
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    p.onSeek(frameFromEvent(e));
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
    p.onSeek(frameFromEvent(e));
  };

  return (
    <div className="timeline">
      <div className="controls">
        <button onClick={p.onTogglePlay} title="播放/暂停（按源帧时间推进）">{p.playing ? "暂停" : "播放"}</button>
        <button onClick={() => p.onStep(-1)} title="上一帧">◀ 帧</button>
        <button onClick={() => p.onStep(1)} title="下一帧">帧 ▶</button>
        <select value={rate} onChange={(e) => setRate(Number(e.target.value))} title="倍速">
          <option value={0.25}>0.25×</option>
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
          <option value={4}>4×</option>
        </select>
        <span className="frameinfo">
          帧 {p.frameIndex}/{p.meta.frameCount - 1} · {formatStamp(stamp)}
          {p.frameStatus === "loading" ? " · 帧加载中…" : ""}
          {p.frameStatus === "error" ? " · 帧加载失败" : ""}
        </span>
        <span style={{ display: "flex", gap: 2, alignItems: "center" }} title="跳到指定帧号">
          <input type="number" min="0" max={p.meta.frameCount - 1} value={jumpTo}
            placeholder="帧号" style={{ width: 52 }}
            onChange={(e) => setJumpTo(e.target.value)} />
          <button className="small" onClick={() => {
            const f = Number(jumpTo);
            if (Number.isFinite(f) && jumpTo !== "") { p.onSeek(f); setJumpTo(""); }
          }}>跳转</button>
        </span>
        {p.cacheStats && (
          <span className="frameinfo" title="帧缓存（带上限）/ 在途请求 / 过期丢弃">
            缓存 {p.cacheStats.cacheFrames}/{p.cacheStats.cacheLimit} · 在途 {p.cacheStats.inFlight} · 弃旧 {p.cacheStats.droppedStale}
          </span>
        )}
      </div>
      <div
        className="track"
        ref={trackRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
      >
        {(p.algorithmIntervals ?? []).map((it, i) => <div key={`algorithm-${i}`} className="interval event"
          style={{left:frameToX(layout,it.startFrame),width:Math.max(3,frameToX(layout,it.endFrame)-frameToX(layout,it.startFrame)),top:31,background:'#be7f35'}}
          title={`${it.label === 'sustained_low_posture' ? '持续低姿态（非跌倒事件）' : '几何疑似'} [${it.startFrame},${it.endFrame}] · 触发 ${it.triggerFrame ?? it.startFrame}`}
          onPointerDown={e=>{e.stopPropagation();p.onSeek(it.triggerFrame ?? it.startFrame)}} />)}
        {(p.doc?.intervals ?? []).map((it) => {
          const x0 = frameToX(layout, it.startFrame);
          const x1 = frameToX(layout, it.endFrame);
          return (
            <div
              key={it.intervalId}
              className={"interval " + it.kind}
              style={{ left: x0, width: Math.max(3, x1 - x0), top: it.kind === "event" ? 18 : 3 }}
              title={`${it.personId} ${it.kind} ${it.label} [${it.startFrame},${it.endFrame}]`}
            />
          );
        })}
        {/* 稀疏标注标记：清单帧（空心）/ 已标帧（实心），点附近即跳 */}
        {(p.doc?.sampleFrames ?? []).map((f) => (
          <div key={"s" + f} className="mark sample" style={{ left: frameToX(layout, f) - 2 }} title={`帧 ${f}（清单）`} />
        ))}
        {p.annotatedFrames.map((f) => (
          <div key={"a" + f} className="mark annotated" style={{ left: frameToX(layout, f) - 1 }} title={`帧 ${f}（已标注）`} />
        ))}
        <div className="playhead" style={{ left: frameToX(layout, p.frameIndex) }} />
      </div>
    </div>
  );
}
