// ui/FrameChecklist.tsx — 稀疏标注帧清单：只标几帧的工作流。
// 清单持久化在 doc.sampleFrames；已标/未标一目了然；点击跳帧。
import React, { useState } from "react";
import type { AnnotationDoc } from "../domain/types.ts";
import { sampleEveryN, sampleCoverage } from "../domain/types.ts";

export interface FrameChecklistProps {
  doc: AnnotationDoc | null;
  currentFrame: number;
  onSetFrames(frames: number[]): void;
  onSeek(frame: number): void;
}

export function FrameChecklist(p: FrameChecklistProps) {
  const [everyN, setEveryN] = useState(25);
  const doc = p.doc;
  if (!doc) return null;
  const cov = sampleCoverage(doc);
  const annotatedElsewhere = new Set(doc.boxes.map((b) => b.frameIndex));

  const toggleCurrent = () => {
    const cur = p.currentFrame;
    const has = doc.sampleFrames.includes(cur);
    p.onSetFrames(has ? doc.sampleFrames.filter((f) => f !== cur) : [...doc.sampleFrames, cur]);
  };

  return (
    <>
      <h4>标注帧清单（稀疏标注）</h4>
      <div className="status-msg" style={{ marginBottom: 4 }}>
        已标 {cov.annotated}/{cov.total} 帧{cov.total > 0 && cov.annotated < cov.total ? `，未标：${cov.missing.slice(0, 8).join("、")}${cov.missing.length > 8 ? "…" : ""}` : ""}
        {doc.boxes.length > 0 && ` · 另有清单外已标帧 ${[...annotatedElsewhere].filter((f) => !doc.sampleFrames.includes(f)).length}`}
      </div>
      <div style={{ display: "flex", gap: 4, marginBottom: 4, flexWrap: "wrap" }}>
        <button className={doc.sampleFrames.includes(p.currentFrame) ? "active" : ""}
          onClick={toggleCurrent}
          title="把当前帧加入/移出清单">
          {doc.sampleFrames.includes(p.currentFrame) ? "✓ 当前帧在清单" : "＋ 当前帧入清单"}
        </button>
        <span style={{ display: "flex", gap: 2, alignItems: "center" }} title="生成间隔取样清单">
          <input type="number" min="1" value={everyN} style={{ width: 46 }}
            onChange={(e) => setEveryN(Math.max(1, Number(e.target.value) || 1))} />
          <button className="small" onClick={() => p.onSetFrames(sampleEveryN(doc.frameCount, everyN))}>
            每N帧取样
          </button>
        </span>
        {doc.sampleFrames.length > 0 && (
          <button className="small danger" onClick={() => p.onSetFrames([])} title="清空清单（不影响已画的框）">清空</button>
        )}
      </div>
      {doc.sampleFrames.length === 0 && (
        <div className="status-msg">不建清单也可以：直接跳到想标的帧画框保存即可（校验不要求覆盖全 session）。</div>
      )}
      <div style={{ maxHeight: 180, overflow: "auto" }}>
        {doc.sampleFrames.map((f) => {
          const done = annotatedElsewhere.has(f);
          return (
            <div key={f} className="person-item" onClick={() => p.onSeek(f)}
              title="点击跳到该帧" style={{ cursor: "pointer" }}>
              <span className="swatch" style={{ background: done ? "#7fd4a0" : "#5a6675" }} />
              <span className="name">帧 {f}</span>
              <span className="meta">{done ? "已标" : "未标"}</span>
              <button className="small danger" onClick={(e) => { e.stopPropagation(); p.onSetFrames(doc.sampleFrames.filter((x) => x !== f)); }}>×</button>
            </div>
          );
        })}
      </div>
    </>
  );
}
