import React, { useState } from 'react';
import type { RangeResult } from '../algorithm/rangeResult.ts';

export function DepthView({ packet, overlay }: { packet: RangeResult | null; overlay?: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [mask, setMask] = useState(false);
  if (!packet?.frame.depth) return <div>此帧未生成 LiDAR 距离图</div>;
  const { manifest, frame } = packet;
  const depth = packet.frame.depth;
  const base = `/api/session/${encodeURIComponent(manifest.sessionId)}/depth/${frame.frameIndex}/`;
  return <section aria-label="LiDAR 距离图">
    <h4>LiDAR 径向距离 · {depth.width} × {depth.height}</h4>
    <div style={{ position: 'relative', width: '100%', aspectRatio: '4 / 3', background: '#050b14' }}>
      {!failed && <img alt={`距离图 帧 ${frame.frameIndex}`} src={base+(mask ? 'mask' : 'preview')}
        onLoad={() => setReady(true)} onError={() => { setFailed(true); setReady(false); }}
        style={{ width: '100%', height: '100%', objectFit: 'contain', imageRendering: 'pixelated', visibility: ready ? 'visible' : 'hidden',
          transform: depth.version === 1 ? 'rotate(180deg)' : undefined }} />}
      {!ready && <span style={{ position: 'absolute', top: 12, left: 12 }}>{failed ? '距离图校验或加载失败' : '加载同帧距离图…'}</span>}
      {ready && !failed && overlay}
    </div>
    <button onClick={() => { setReady(false); setFailed(false); setMask(!mask); }}>{mask ? '查看距离图' : '查看目标像素'}</button>
    <div>红近 → 蓝远，0.1–8 m 截色；黑色无回波。上下、左右已转正，无补洞。</div>
    {depth.version === 1 && <div>旧版 v1：显示已转正，下载保留原生行列；新版 v2 导出与显示同向。</div>}
    <div>有效 {depth.validPixels} · 目标 {depth.targetPixels} · 溢出 {depth.overflowPixels}</div>
    <div>导出毫米 PNG16：0=无回波，65535=超量程；并非相机 Z 深度。</div>
    <p>{(['metric','preview','mask','metadata'] as const).map(kind =>
      <React.Fragment key={kind}><a href={base+kind} download={`${manifest.sessionId}_${frame.frameIndex}_${kind}.${kind === 'metadata' ? 'json' : 'png'}`}>
        {{metric:'距离 PNG16',preview:'预览',mask:'目标 mask',metadata:'元数据'}[kind]}</a>{' '}</React.Fragment>)}</p>
  </section>;
}
