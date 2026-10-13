"""HF-REAL-03 任务2 v3：按28B格式重读093958，看早期/中期/晚期点云。
ponytail: 复用 HF-REAL-01 prepare 推断的 28B layout（7列 f32）；
meta.frame_rows 包含 offset_points/count_points 与 28B 源 stride。"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r'D:/Code/ldiar')
SID = 'cap_20261013_093958'
OUT = Path(__file__).resolve().parent / 'out'
OUT.mkdir(parents=True, exist_ok=True)

meta = json.loads((ROOT / 'captures/remote' / SID / 'meta.json').read_text(encoding='utf8'))
blob = (ROOT / 'captures/remote' / SID / 'points.bin').read_bytes()
print('bytes:', len(blob), 'bytes/frame0 from meta:', meta['frames'][0]['count_points'] * 28)

# 28B: 7 f32 per row (likely xyz + intensity + 3 others) — 与 HF-REAL-01 prepare.py 对齐
if len(blob) % 28 == 0:
    arr = np.frombuffer(blob, dtype='<f4').reshape(-1, 7)
    print('rows:', len(arr), 'cols:', 7)
    frames = meta['frames'] if 'frames' in meta else meta['frame_rows']
    fr = frames[0]
    sample = arr[fr['offset_points']:fr['offset_points'] + fr['count_points']]
    print('first-frame sample (first 3 rows):', sample[:3])
    # 检查前3列是否近似合理 xyz
    xyz = sample[:, :3]
    print('xyz ranges:', xyz.min(axis=0), xyz.max(axis=0), 'mean:', xyz.mean(axis=0))
else:
    print('bytes not divisible by 28 — layout unknown, stop')
    raise SystemExit(1)

# 3帧视觉图（滤零占位点）
fig, axes = plt.subplots(2, 3, figsize=(17, 10))
for col, fi in enumerate((5, 60, 115)):
    fr = meta['frames'][fi] if 'frames' in meta else meta['frame_rows'][fi]
    o, c = fr['offset_points'], fr['count_points']
    q = arr[o:o + c][:, :3]
    valid = (np.abs(q).sum(axis=1) > 1e-3) & np.isfinite(q).all(axis=1) & (np.linalg.norm(q, axis=1) < 15)
    q = q[valid]
    for r_, (a0, a1, label) in enumerate(((0, 2, 'SIDE'), (0, 1, 'TOP'))):
        ax = axes[r_][col]
        ax.scatter(q[:, a0], q[:, a1], s=2, color='#748ea0', alpha=.5)
        ax.set_title(f'f{fi} {label} n={len(q)}')
        ax.set_xlabel('x (m)' if a0 == 0 else 'y'); ax.set_ylabel('z (m)' if a1 == 2 else 'y (m)')
        ax.grid(alpha=.25)
plt.suptitle(f'{SID} raw 28B (zero/non-finite filtered) — leveling FAIL, pairwise PASS')
plt.tight_layout(); fig.savefig(OUT / '093958_SNAPSHOTS.png', dpi=140); plt.close(fig)
print('\nwrote', OUT / '093958_SNAPSHOTS.png')
