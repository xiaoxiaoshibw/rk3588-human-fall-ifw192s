"""HF-REAL-03：渲染v2 vs v3在f9/f10/f11的对比图，并新增f47/f109/f118骨架查看。"""
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
p2 = json.loads((EV / 'process_v2.json').read_text(encoding='utf8'))
p3 = json.loads((OUT / f'{SID}_process_v3.json').read_text(encoding='utf8'))

def draw(ax, row_v2, row_v3, fi, axes=(0, 1), v3_color='#8e44ad'):
    f = fg['frames'][fi]
    q = pts[f['offset']:f['offset'] + f['count']]
    ax.scatter(q[:, axes[0]], q[:, axes[1]], s=2, color='#aaa', alpha=.4)
    if row_v2:
        i2 = np.asarray(row_v2['source_fg_indices'], dtype=int)
        if len(i2):
            ax.scatter(q[i2, axes[0]], q[i2, axes[1]], s=6, color='#d76131', alpha=.7, label='v2 target')
    if row_v3:
        i3 = np.asarray(row_v3['source_fg_indices'], dtype=int)
        if len(i3):
            ax.scatter(q[i3, axes[0]], q[i3, axes[1]], s=6, color=v3_color, label='v3 (vision-cleaned)')
    c = (row_v3 or row_v2 or {}).get('center')
    if c:
        ax.scatter([c[0]], [c[axes[1]]], s=90, facecolor='none', edgecolor='#c92a2a', label='track center')
    r = row_v3 or row_v2
    sk = r.get('skeleton') if r else None
    if sk and fi in (47, 109, 118):  # ambiguous frames
        nodes = sk.get('nodes', {})
        valid = np.array([n['xyz'] for n in nodes.values() if n.get('valid')]).reshape(-1, 3)
        if len(valid):
            ax.scatter(valid[:, axes[0]], valid[:, axes[1]], s=35, color='#20a592', marker='s', label='skeleton nodes')
    moved = (len(row_v2['source_fg_indices']) - len(row_v3['source_fg_indices'])) if (row_v2 and row_v3) else 0
    ax.set_title(f'f{fi} t={r.get("t",0):.2f}s removed={moved}')
    ax.grid(alpha=.2); ax.legend(fontsize=7)

# f9/f10/f11 对比（v2 vs v3）
for group, frames in [('CLEAN', (9, 10, 11)), ('AMBIG', (47, 109, 118))]:
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for col, fi in enumerate(frames):
        draw(axes[0][col], p2['rows'][fi], p3['rows'][fi], fi, (0, 1))
        draw(axes[1][col], p2['rows'][fi], p3['rows'][fi], fi, (0, 2))
    for a in axes[0]:
        a.set_xlim(1.3, 2.45)
        if group == 'CLEAN': a.set_ylim(1.2, 2.2)
    for a in axes[1]:
        a.set_xlim(1.3, 2.45)
        if group == 'CLEAN': a.set_ylim(0, 1.9)
    plt.suptitle(group)
    plt.tight_layout(); fig.savefig(OUT / f'{group}_COMPARE.png', dpi=140); plt.close(fig)

print('done')
