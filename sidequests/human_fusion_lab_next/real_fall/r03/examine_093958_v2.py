"""HF-REAL-03 任务2：093958 leveling.json 全字段判读 + 逐帧视觉图。
ponytail：一次run输出 JSON摘要 + 3张图 (early/mid/late)，不修代码不回归。"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r'D:/Code/ldiar')
EV1 = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_01_r1'
LV = json.loads((EV1 / 'cap_20261013_093958_leveling.json').read_text(encoding='utf8'))
OUT = Path(__file__).resolve().parent / 'out'
OUT.mkdir(parents=True, exist_ok=True)
SID = LV['sid']

print('=== 093958 leveling top-level ===')
for k in ('frames', 'duration_s', 'recommended', 'numeric_check_ok', 'physical_verified', 'runtime_eligible'):
    print(f' {k}: {LV.get(k)}')

print('\n=== pairwise ===')
print(json.dumps(LV.get('pairwise'), ensure_ascii=False, indent=1)[:1200])

print('\n=== estimators keys ===')
est = LV.get('estimators', {})
for m, block in est.items():
    print(f'\n -- {m} --')
    if isinstance(block, dict):
        for kk in ('status', 'gate_pass', 'n_inliers', 'pitch_deg', 'roll_deg', 'tz_m', 'normal', 'reason'):
            if kk in block: print(f'   {kk}: {block[kk]}')

print('\n=== domain_geometry ===')
print(json.dumps(LV.get('domain_geometry'), ensure_ascii=False, indent=1)[:1000])

# 3帧视觉图 early/mid/late
fg = json.loads((ROOT / 'captures/remote' / SID / 'meta.json').read_text(encoding='utf8'))
pts = np.memmap(ROOT / 'captures/remote' / SID / 'points.bin', dtype='<f4', mode='r').reshape(-1, 4)
fig, axes = plt.subplots(2, 3, figsize=(17, 10))
for col, fi in enumerate((5, 60, 120)):
    fr = fg['frames'][fi]
    q = pts[fr['offset_points']:fr['offset_points'] + fr['count_points']]
    for r_, (a0, a1, label) in enumerate(((0, 2, 'SIDE'), (0, 1, 'TOP'))):
        ax = axes[r_][col]
        ax.scatter(q[:, a0], q[:, a1], s=2, color='#748ea0', alpha=.5)
        ax.set_title(f'f{fi} {label}')
        ax.set_xlabel('x (m)' if a0 == 0 else 'y'); ax.set_ylabel('z (m)' if a1 == 2 else 'y (m)')
        ax.grid(alpha=.25)
plt.suptitle(f'{SID} leveling failed; sanity snapshots')
plt.tight_layout(); fig.savefig(OUT / '093958_SNAPSHOTS.png', dpi=140); plt.close(fig)
print('\nwrote', OUT / '093958_SNAPSHOTS.png')
