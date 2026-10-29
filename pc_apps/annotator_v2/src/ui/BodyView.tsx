import React, { useEffect, useRef, useState } from 'react';
import type { RangeResult } from '../algorithm/rangeResult.ts';
import type { AnnotationDoc, Box } from '../domain/types.ts';
import type { DecodedFrame } from '../session/types.ts';
import { PART_LABELS, PART_COLORS, bodyColors, checkBodyBinding, displayRect, mergeBodySuggestions } from '../annotation/body.ts';
import type { BodyContext, BodyDoc, BodyPart } from '../annotation/body.ts';
import { DepthView } from './DepthView.tsx';
import { Viewport3D } from './Viewport3D.tsx';

interface Props {
  packet: RangeResult; person: string; box: Box | null; doc: AnnotationDoc | null;
  frameRef: React.MutableRefObject<DecodedFrame | null>; frameEpoch: number; pause(): void;
}

export function BodyView(p: Props) {
  const [context, setContext] = useState<BodyContext | null>(null);
  const [body, setBody] = useState<BodyDoc | null>(null);
  const [version, setVersion] = useState(0);
  const [selected, setSelected] = useState('head');
  const [draw, setDraw] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [fitImage, setFitImage] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState('加载同源索引…');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const past = useRef<BodyDoc[]>([]), future = useRef<BodyDoc[]>([]);
  const alive = useRef(true), request = useRef(0);
  const drag = useRef<number[] | null>(null);
  const [rubber, setRubber] = useState<number[] | null>(null);
  const sid = p.packet.manifest.sessionId, frame = p.packet.frame.frameIndex;
  const url = `/api/body/${encodeURIComponent(sid)}/${frame}?person=${encodeURIComponent(p.person)}`;
  const scope = () => p.box ? { kind: 'person_box', boxId: p.box.boxId,
    box: { x: p.box.x, y: p.box.y, w: p.box.w, h: p.box.h, zMin: p.box.zMin, zMax: p.box.zMax } }
    : { kind: 'automatic_target', trackId: context?.trackId, generation: context?.generation };
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    setContext(null); setBody(null); past.current = []; future.current = []; setDirty(false);
    fetch(url, { signal: controller.signal, cache: 'no-store' }).then(async r => {
      if (!r.ok) throw new Error(await r.text());
      return r.json() as Promise<{ context: BodyContext; doc: BodyDoc | null; version: number }>;
    }).then(env => {
      if (!alive.current || controller.signal.aborted) return;
      checkBodyBinding(env.context, sid, frame, p.person, p.packet.frame.rawSha256);
      const legacy = env.doc?.parts.some(part => part.origin.kind === 'automatic'
        && ['image_extent_bands_v1', 'range_topology_branches_v1'].includes(part.origin.method));
      setContext(env.context); setBody(env.doc); setVersion(env.version);
      setMessage(legacy ? '已加载旧版自动结果；请点“自动部位候选”重算，手工区域会保留'
        : env.doc ? (env.version === 0 ? '已加载同帧预计算自动候选（未写入标注）' : '已加载独立部位标注') : '可直接画区域，或生成自动假设');
    }).catch(e => { if (!controller.signal.aborted) setMessage(String(e)); });
    return () => { alive.current = false; controller.abort(); request.current++; };
  }, [url, revision, sid, frame, p.person, p.packet.frame.rawSha256]);

  const run = async (action: 'map' | 'suggest' | 'save', next?: BodyDoc) => {
    if (!context || busy) return;
    p.pause();
    const token = ++request.current;
    setBusy(true);
    try {
      const response = await fetch(url, { method: action === 'save' ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'suggest' ? { action: 'suggest' } : { doc: next ?? body, baseVersion: version }) });
      if (!response.ok) throw new Error(await response.text());
      const value = await response.json();
      if (!alive.current || token !== request.current) return;
      let mapped: BodyDoc = action === 'save' ? value.doc : value;
      if (action === 'suggest' && body) {
        const merged = mergeBodySuggestions(body, mapped);
        const checked = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ doc: merged }) });
        if (!checked.ok) throw new Error(await checked.text());
        mapped = await checked.json() as BodyDoc;
        if (!alive.current || token !== request.current) return;
      }
      checkBodyBinding({ ...context, binding: mapped.binding }, sid, frame, p.person, p.packet.frame.rawSha256);
      if (action === 'save') { setVersion(value.version); setDirty(false); setMessage('部位保存成功（独立存储）'); }
      else {
        past.current.push(body ?? { format: 'body_parts_v1', binding: context.binding, scope: scope(), parts: [] });
        future.current = []; setDirty(true); setMessage(action === 'suggest'
          ? (mapped.parts.some(part => part.mapping?.sourceRows.length)
            ? '已计算部位拓扑候选；仅给有支撑的点集，未解析部位留空。手工/传播区域保留，人体语义 UNKNOWN。'
            : '目标缺失、拓扑不清或形态条件不足：部位候选全部留空，原因见各部位')
          : '映射完成：仅当前可见代表回波');
      }
      setBody(mapped);
    } catch (e) { if (alive.current && token === request.current) setMessage(String(e)); }
    finally { if (alive.current && token === request.current) setBusy(false); }
  };
  const replace = (part: BodyPart | null) => {
    if (!context) return;
    const current = body ?? { format: 'body_parts_v1', binding: context.binding, scope: scope(), parts: [] };
    void run('map', { ...current, parts: [...current.parts.filter(v => v.part !== selected), ...(part ? [part] : [])] });
  };
  const humanPart = (state: BodyPart['state'], rect: number[] | null): BodyPart => ({ part: selected, state, rect,
    ...(rect === null && (state === 'visible' || state === 'occluded') && body?.parts.find(part => part.part === selected)?.pixels
      ? { pixels: body.parts.find(part => part.part === selected)!.pixels } : {}),
    origin: { kind: 'human', method: 'range_rectangle_editor_v1', derivedFrom: body?.parts.find(part => part.part === selected)?.origin ?? null,
      uncertainty: ['manual_semantic_assignment_not_algorithm_success', 'visible_surface_only', 'background_purity_unverified'] } });
  const point = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return [(e.clientX-r.left)/r.width*(context?.width ?? 256), (e.clientY-r.top)/r.height*(context?.height ?? 192)];
  };
  const undo = (redo: boolean) => {
    const from = redo ? future.current : past.current, to = redo ? past.current : future.current;
    const next = from.pop();
    if (next && body) { to.push(body); setBody(next); setDirty(true); }
  };
  const selectedPart = body?.parts.find(v => v.part === selected);
  const colors = bodyColors(body, selected);
  const overlay = context && <svg aria-label="距离图部位区域编辑" viewBox={`0 0 ${context.width} ${context.height}`}
    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', touchAction: 'none', cursor: draw ? 'crosshair' : 'pointer' }}
    onPointerDown={e => { if (draw && !busy) { p.pause(); drag.current = point(e); setRubber(null); e.currentTarget.setPointerCapture(e.pointerId); } }}
    onPointerMove={e => { if (drag.current) setRubber(displayRect(drag.current, point(e), context.width, context.height)); }}
    onPointerCancel={() => { drag.current = null; setRubber(null); }}
    onPointerUp={e => {
      if (!drag.current) return;
      const rect = displayRect(drag.current, point(e), context.width, context.height);
      drag.current = null; setRubber(null); setDraw(false); replace(humanPart('visible', rect));
    }}>
    {body?.parts.map(part => <g key={part.part} onClick={() => { if (!draw) setSelected(part.part); }}>
      {part.mapping?.imagePixels.map(([x, y], i) => <rect key={i} x={x} y={y} width="1" height="1"
        fill={part.part === selected ? '#ffffff' : PART_COLORS[part.part]} fillOpacity=".8" />)}
      {part.rect && <><rect x={part.rect[0]} y={part.rect[1]} width={part.rect[2]!-part.rect[0]!} height={part.rect[3]!-part.rect[1]!}
        fill="none" stroke={PART_COLORS[part.part]} strokeWidth={part.part === selected ? .8 : .35} />
        <text x={part.rect[0]} y={Math.max(5, part.rect[1]!-1)} fill={PART_COLORS[part.part]} fontSize="4">{PART_LABELS[part.part]}{part.origin.kind === 'automatic' ? '候选?' : part.origin.kind === 'propagated' ? '传播' : '区域'}</text></>}
    </g>)}
    {rubber && <rect x={rubber[0]} y={rubber[1]} width={rubber[2]!-rubber[0]!} height={rubber[3]!-rubber[1]!} stroke="white" strokeWidth=".5" fill="white" fillOpacity=".1" />}
  </svg>;
  return <div className="body-workspace">
    <div className="body-range">
      <h3>2D LiDAR 距离图 → 同源 3D 部位点集</h3>
      <div>会话 {sid} · 源帧 {frame} · 人物 {p.person} · {p.box ? `整人框 ${p.box.boxId}` : `自动目标 ${p.packet.frame.trackId ?? '缺失'}（人物对应未验证）`}</div>
      <div className="body-controls">
        <select aria-label="身体部位" value={selected} onChange={e => { setSelected(e.target.value); setDraw(false); }}>{Object.entries(PART_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <button disabled={!context || busy} className={draw ? 'active' : ''} onClick={() => { p.pause(); setDraw(!draw); }}>画 / 重画区域</button>
        <button disabled={!context || busy} onClick={() => void run('suggest')}>自动部位候选（含四肢/脚）</button>
        {p.box && <button disabled={!body || busy} onClick={() => body && void run('map', { ...body, scope: scope() })}>按当前整人框重新过滤</button>}
        <button className={fitImage ? 'active' : ''} onClick={() => { setFitImage(v => !v); setZoom(1); }}>完整图适配</button>
        <button onClick={() => { setFitImage(false); setZoom(z => z === 1 ? 2 : 1); }}>{zoom === 1 ? '放大 2×' : '还原'}</button>
      </div>
      <div className="body-image-scroll"><div style={{ width: fitImage ? 'min(100%, max(160px, calc(133.333vh - 440px)))' : `${zoom*100}%` }}><DepthView packet={p.packet} overlay={overlay} /></div></div>
      <div className="body-controls">
        <select aria-label="部位可见性" value={selectedPart?.state ?? 'uncertain'} disabled={!context || busy} onChange={e => {
          const state = e.target.value as BodyPart['state'];
          replace(humanPart(state, state === 'invisible' || state === 'uncertain' ? null : selectedPart?.rect ?? null));
        }}><option value="visible">可见（只标实测区域）</option><option value="occluded">遮挡（可保留可见部分）</option><option value="invisible">不可见（无点集）</option><option value="uncertain">无法判断（无点集）</option></select>
        <button disabled={!selectedPart || busy} onClick={() => replace(null)}>删除当前部位</button>
        <button disabled={!past.current.length || busy} onClick={() => undo(false)}>部位撤销</button>
        <button disabled={!future.current.length || busy} onClick={() => undo(true)}>部位重做</button>
        <button disabled={!body || busy} onClick={() => void run('save')}>保存部位{dirty ? ' *' : ''}</button>
        <button disabled={busy} onClick={() => setRevision(v => v+1)}>重载部位</button>
        <button disabled={!body} onClick={() => {
          const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
          a.download = `${sid}_${frame}_${p.person}_body.json`; a.click(); URL.revokeObjectURL(a.href);
        }}>导出映射 JSON</button>
      </div>
      <div role="status">{busy ? '同源验证中…' : message}</div>
      {body && <div>映射范围快照：{body.scope.kind === 'person_box' ? `整人框 ${String(body.scope.boxId)}` : '自动目标源点'}；整人框调整后可重新过滤，范围内背景纯度仍 UNKNOWN。</div>}
      <div className="body-controls">{body?.parts.map(part => <button key={part.part} style={{ borderColor: PART_COLORS[part.part] }}
        className={selected === part.part ? 'active' : ''} onClick={() => setSelected(part.part)}>{PART_LABELS[part.part]} · {part.mapping?.sourceRows.length ? `${part.mapping.sourceRows.length}点` : 'UNKNOWN / 无点集'} · {part.origin.kind}</button>)}</div>
      {body && context && body.scope.kind === 'automatic_target' && <div>目标实测源点 {context.targetRows.length} · 已分配区域 {new Set(body.parts.flatMap(part => part.mapping?.sourceRows ?? [])).size}；其余保留未解析，不强行补齐。</div>}
      {selectedPart && <div>当前 {PART_LABELS[selected]}：{selectedPart.origin.kind} / {selectedPart.origin.method} · {selectedPart.state}
        {' · '}无效像素 {selectedPart.mapping?.invalidPixels ?? 0} · 范围外排除 {selectedPart.mapping?.excludedOutsideScope ?? 0}<br />
        不确定原因：{selectedPart.origin.uncertainty.join(' / ')}</div>}
      {selectedPart?.origin.evidence && <div>候选依据：{selectedPart.origin.evidence.reason ?? '观测分支'}
        {selectedPart.origin.evidence.arcLengthM !== undefined && ` · 可分离路径 ${selectedPart.origin.evidence.arcLengthM.toFixed(3)} m`}
        {selectedPart.origin.evidence.terminalTurnDeg !== undefined && ` · 末端实测转向 ${selectedPart.origin.evidence.terminalTurnDeg.toFixed(1)}°`}
        {selectedPart.origin.evidence.segmentBoundary && ' · 上下段按实测路径弧长分段，边界不是肘/膝关节'}
      </div>}
      <div>区域中心仅为部位代表点；分支 1/2 不表示解剖左右。点击彩色像素、部位按钮或 3D 点同步选中（白色）。</div>
      <div>部位草稿使用本区保存/撤销按钮；切帧或换人物前请保存。整人框仍用原工具栏保存。3D 的 Z 仅为传感器坐标显示方向。</div>
      {body?.geometry && <div className="body-features"><strong>身体相对几何旁路（未接告警）</strong><br />
        头—躯干距离：{body.geometry.headTorso ? `${body.geometry.headTorso.distanceM.toFixed(3)} m；传感器系差向量 [${body.geometry.headTorso.deltaSensorM.map(x => x.toFixed(3)).join(', ')}] m` : 'UNKNOWN（缺支撑）'}<br />
        躯干主轴：{body.geometry.parts.torso?.principalAxis?.map(x => x.toFixed(3)).join(', ') ?? body.geometry.parts.torso?.reason ?? 'UNKNOWN'}<br />
        段主轴夹角：{Object.entries(body.geometry.segmentAxisAnglesDeg).map(([key, value]) => `${key}=${value.toFixed(1)}°`).join('；') || 'UNKNOWN（缺少可辨主轴）'}<br />
        部位旁路的站立 / 躺倒 / 离地高度 / 跌倒事件：UNKNOWN；本旁路未使用重力与地面，传感器 Z 不作为重力。整体高度 / 低位提示见同帧识别结果；人体部位与姿态准确性 UNKNOWN。</div>}
    </div>
    <Viewport3D frameRef={p.frameRef} frameEpoch={p.frameEpoch} boxes={p.box ? [p.box] : []} doc={p.doc}
      onClose={() => {}} personColorOf={() => '#e8b339'} bodyColors={colors} onPickPart={setSelected} focusBody />
  </div>;
}
