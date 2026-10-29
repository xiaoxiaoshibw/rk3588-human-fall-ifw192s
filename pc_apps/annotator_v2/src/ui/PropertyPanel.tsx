// ui/PropertyPanel.tsx — 属性面板：选中框的属性编辑、框内统计（完整点集）、
// 算法建议（显式采用/拒绝）、区间编辑。
import React, { useState } from "react";
import type { AnnotationDoc, Box, Suggestion, Visibility } from "../domain/types.ts";
import { countPointsInBox } from "../domain/geometry.ts";
import type { Op } from "../annotation/ops.ts";
import type { DecodedFrame, SessionMeta } from "../session/types.ts";

export interface PropertyPanelProps {
  doc: AnnotationDoc | null;
  frame: DecodedFrame | null;
  frameIndex: number;
  meta: SessionMeta | null;
  selectedBox: Box | null;
  onCommit(op: Op): void;
  onCopyNext(box: Box): void;
  onDelete(): void;
  suggestions: Suggestion[];
  onAdopt(s: Suggestion): void;
  onReject(s: Suggestion): void;
  personColorOf(doc: AnnotationDoc | null, personId: string): string;
  onAddInterval(personId: string, kind: "action" | "event", label: string, start: number, end: number): void;
  onRemoveInterval(intervalId: string): void;
  targetPersonId: string | null;
}

export function PropertyPanel(p: PropertyPanelProps) {
  const patchBox = (patch: Partial<Box>) => {
    if (p.selectedBox) p.onCommit({ t: "updateBox", boxId: p.selectedBox.boxId, patch });
  };
  const pointCount = p.selectedBox && p.frame
    ? countPointsInBox(p.frame, p.selectedBox)
    : null;
  const b = p.selectedBox;

  return (
    <>
      <h4>选中框</h4>
      {!b && <div className="status-msg">选择工具下点击框选中；拖柄调整大小，拖框体移动。</div>}
      {b && (
        <>
          <div className="prop-row">
            <label>人物</label>
            <select value={b.personId} onChange={(e) => patchBox({ personId: e.target.value })}>
              {(p.doc?.persons ?? []).map((per) => <option key={per.personId} value={per.personId}>{per.personId}</option>)}
            </select>
          </div>
          <div className="prop-row">
            <label>帧</label>
            <span>{b.frameIndex} / {(p.meta?.frameCount ?? 1) - 1}</span>
          </div>
          <div className="prop-row">
            <label>中心 x,y</label>
            <input type="number" step="0.05" value={Number(b.x.toFixed(3))}
              onChange={(e) => patchBox({ x: Number(e.target.value) })} />
            <input type="number" step="0.05" value={Number(b.y.toFixed(3))}
              onChange={(e) => patchBox({ y: Number(e.target.value) })} />
          </div>
          <div className="prop-row">
            <label>宽×高 m</label>
            <input type="number" step="0.05" min="0.05" value={Number(b.w.toFixed(3))}
              onChange={(e) => patchBox({ w: Math.max(0.05, Number(e.target.value)) })} />
            <input type="number" step="0.05" min="0.05" value={Number(b.h.toFixed(3))}
              onChange={(e) => patchBox({ h: Math.max(0.05, Number(e.target.value)) })} />
          </div>
          <div className="prop-row">
            <label>z 范围 m</label>
            <input type="number" step="0.1" value={Number(b.zMin.toFixed(2))}
              onChange={(e) => patchBox({ zMin: Number(e.target.value) })} />
            <input type="number" step="0.1" value={Number(b.zMax.toFixed(2))}
              onChange={(e) => patchBox({ zMax: Number(e.target.value) })} />
          </div>
          <div className="prop-row">
            <label>可见性</label>
            <select value={b.visibility} onChange={(e) => patchBox({ visibility: e.target.value as Visibility })}>
              <option value="visible">可见</option>
              <option value="partial">部分遮挡</option>
              <option value="occluded">遮挡</option>
            </select>
          </div>
          <div className="prop-row">
            <label>已复核</label>
            <input type="checkbox" checked={b.reviewed} onChange={(e) => patchBox({ reviewed: e.target.checked })} />
            <span className="status-msg">来源：{describeOrigin(b)}</span>
          </div>
          <div className="prop-row">
            <label>备注</label>
            <input type="text" value={b.note ?? ""} onChange={(e) => patchBox({ note: e.target.value || null })} />
          </div>
          <div className="status-msg">框内点数（完整点集，非抽稀）：{pointCount ?? "—"}</div>
          <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
            <button onClick={() => p.onCopyNext(b)} title="复制到下一帧（来源 propagated，未复核）">复制到下一帧</button>
            <button className="danger" onClick={p.onDelete}>删除框</button>
          </div>
        </>
      )}

      <h4>算法建议（本帧）</h4>
      {p.suggestions.length === 0 && <div className="status-msg">无待处理建议。工具栏勾选「算法」后点「当前帧建议」。</div>}
      {p.suggestions.map((s) => (
        <SuggestionItem key={s.suggestionId} s={s} onAdopt={p.onAdopt} onReject={p.onReject} />
      ))}

      <IntervalEditor
        doc={p.doc}
        frameIndex={p.frameIndex}
        targetPersonId={p.targetPersonId}
        onAdd={p.onAddInterval}
        onRemove={p.onRemoveInterval}
        personColorOf={p.personColorOf}
      />
    </>
  );
}

function describeOrigin(b: Box): string {
  switch (b.origin.kind) {
    case "human": return "人工";
    case "propagated": return `传播自 ${b.origin.fromBoxId}`;
    case "adopted": return `采用 ${b.origin.algorithm}`;
  }
}

function SuggestionItem({ s, onAdopt, onReject }: { s: Suggestion; onAdopt(s: Suggestion): void; onReject(s: Suggestion): void }) {
  return (
    <div className={"suggestion-item " + s.status}>
      <div>
        {s.box
          ? `框 @(${s.box.x.toFixed(2)}, ${s.box.y.toFixed(2)}) ${s.box.w.toFixed(2)}×${s.box.h.toFixed(2)}m`
          : `区间 ${s.interval?.label ?? ""}`}
      </div>
      <div className="reason">{s.algorithm} · {s.reason ?? ""}</div>
      {s.status === "pending" && (
        <div className="row">
          <button className="small" onClick={() => onAdopt(s)}>采用（进人工编辑）</button>
          <button className="small danger" onClick={() => onReject(s)}>拒绝</button>
        </div>
      )}
      {s.status === "accepted" && <div className="reason">已采用 → {s.adoptedRef}</div>}
    </div>
  );
}

function IntervalEditor(props: {
  doc: AnnotationDoc | null;
  frameIndex: number;
  targetPersonId: string | null;
  onAdd(personId: string, kind: "action" | "event", label: string, start: number, end: number): void;
  onRemove(intervalId: string): void;
  personColorOf(doc: AnnotationDoc | null, personId: string): string;
}) {
  const { doc, frameIndex, targetPersonId, onAdd, onRemove, personColorOf } = props;
  const [kind, setKind] = useState<"action" | "event">("action");
  const [label, setLabel] = useState("");
  const [start, setStart] = useState(frameIndex);
  const [end, setEnd] = useState(frameIndex);
  const [person, setPerson] = useState(targetPersonId ?? "");
  const persons = doc?.persons ?? [];
  const intervals = doc?.intervals ?? [];
  return (
    <>
      <h4>动作 / 事件区间</h4>
      {intervals.map((it) => (
        <div key={it.intervalId} className="person-item" title={`${it.personId} ${it.kind} ${it.label} [${it.startFrame},${it.endFrame}]`}>
          <span className="swatch" style={{ background: personColorOf(doc, it.personId) }} />
          <span className="name">{it.personId} {it.label}</span>
          <span className="meta">[{it.startFrame},{it.endFrame}]</span>
          <button className="small danger" onClick={() => onRemove(it.intervalId)}>删</button>
        </div>
      ))}
      {persons.length > 0 ? (
        <div>
          <div className="prop-row">
            <label>人物</label>
            <select value={person} onChange={(e) => setPerson(e.target.value)}>
              {persons.map((per) => <option key={per.personId} value={per.personId}>{per.personId}</option>)}
            </select>
          </div>
          <div className="prop-row">
            <label>类型</label>
            <select value={kind} onChange={(e) => setKind(e.target.value as "action" | "event")}>
              <option value="action">动作</option>
              <option value="event">事件</option>
            </select>
          </div>
          <div className="prop-row">
            <label>标签</label>
            <input type="text" value={label} placeholder="如 walk / fall" onChange={(e) => setLabel(e.target.value)} />
          </div>
          <div className="prop-row">
            <label>起止帧</label>
            <input type="number" value={start} min="0" onChange={(e) => setStart(Number(e.target.value))} />
            <input type="number" value={end} min="0" onChange={(e) => setEnd(Number(e.target.value))} />
          </div>
          <button
            className="small"
            disabled={!label || !person}
            onClick={() => { onAdd(person, kind, label, start, end); setLabel(""); }}
          >
            ＋ 区间
          </button>
        </div>
      ) : (
        <div className="status-msg">先添加人物。</div>
      )}
    </>
  );
}
