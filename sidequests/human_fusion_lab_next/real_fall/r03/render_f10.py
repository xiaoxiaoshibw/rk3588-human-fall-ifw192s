"""HF-REAL-03：渲染094333 f9/f10/f11前景+追踪目标，为助手视觉划分人体/家具。

复用r02 evidence的foreground.bin / tracking_v2.json / process_v2.json。
每个frame一张side/top对图，带刻度，供AI直接读坐标。
ponytail：只画3帧，不造通用工具。"""
import json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'
EV = Path(r'D:/Code/ldiar/docs/human_fall/evidence/2026-10-13_hf_real_02_r1')
SID = 'cap_20261013_094333'

fg = json.loads((EV / f'{SID}_foreground.json').read_text(encoding='utf8'))
pts = np.memmap(EV / f'{SID}_foreground.bin', dtype='<f4', mode='r').reshape(-1, 4)
proc = json.loads((EV / 'process_v2.json').read_text(encoding='utf8'))
tracking = json.loads((EV / f'{SID}_tracking_v2.json').read_text(encoding='utf8'))

def frame_points(fi):
    f = fg['frames'][fi]
    return pts[f['offset']:f['offset'] + f['count']]

def render(fi):
    q = frame_points(fi)
    prow = proc['rows'][fi]
    trow = tracking['rows'][fi] if fi < len(tracking['rows']) else None
    # 追踪目标在 foregound indices 中：用 process row 的 source_fg_indices
    tgt_idx = prow.get('source_fg_indices') or []
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, (a0, a1, title) in zip(axes, [(0, 1, 'TOP'), (0, 2, 'SIDE')]):
        ax.scatter(q[:, a0], q[:, a1], s=2, color='#9aa7b0', alpha=.5, label='foreground')
        if tgt_idx:
            t = q[tgt_idx]
            ax.scatter(t[:, a0], t[:, a1], s=6, color='#d76131', label=f'target v2 ({len(t)})')
        bb = prow.get('bbox')
        if bb:
            mn, mx = np.array(bb['min']), np.array(bb['max'])
            xs = [mn[a0], mx[a0], mx[a0], mn[a0], mn[a0]]
            ys = [mn[a1], mx[a1], mx[a1], mn[a1], mn[a1]]
            ax.plot(xs, ys, color='#20a592', linewidth=1, label='target bbox')
        c = prow.get('center')
        if c:
            ax.scatter([c[0]], [c[a1]], s=80, facecolor='none', edgecolor='#c92a2a', label='track center')
        ax.set_title(f'f{fi} t={prow["t"]:.2f}s {title}  |  tracks={len(tgt_idx)}pts')
        ax.grid(alpha=.2); ax.legend(loc='upper right', fontsize=8)
    plt.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f'F{fi:03d}_V2.png', dpi=140)
    plt.close(fig)
    print(f'f{fi}: fg={len(q)}, target={len(tgt_idx)}, bbox={prow.get("bbox")}')

for fi in (9, 10, 11):
    render(fi)
print('done')
