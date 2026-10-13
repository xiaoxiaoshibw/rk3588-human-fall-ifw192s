"""HF-REAL-03 任务2 机器part：093958 三法失败区域交叠定量分析；
任务1 机器part：核 v3 剔除点与 HF-REAL-01 视觉人区 XY[1.4,2.6]x[1.25,2.2] 的位置关系。

ponytail：只读既有 leveling.json + r03 v3 json，matplotlib Agg 输出一次性图，不造通用工具。
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(r'D:/Code/ldiar')
EV1 = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_01_r1'
EV2 = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_02_r1'
HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
PERSON_REGION = [1.4, 2.6], [1.25, 2.2]  # HF-REAL-01 助手视觉排除区（x范围, y范围）

# ── 任务1机器part：v3剔除点是不是都在人物活动区
v3 = json.loads((OUT / 'cap_20261013_094333_process_v3.json').read_text(encoding='utf8'))
fg = json.loads((EV2 / 'cap_20261013_094333_foreground.json').read_text(encoding='utf8'))
pts = np.memmap(EV2 / 'cap_20261013_094333_foreground.bin', dtype='<f4', mode='r').reshape(-1, 4)
removed_rows = []
for r in v3['rows']:
    if r.get('vision_clean_removed_points'):
        fr = fg['frames'][r['frame']]
        allt = pts[fr['offset']:fr['offset'] + fr['count']]
        i2 = np.asarray(r['source_fg_indices'])
        i3_before = np.asarray((EV2 / 'process_v2.json').exists() and
                              json.loads((EV2 / 'process_v2.json').read_text(encoding='utf8'))['rows'][r['frame']]['source_fg_indices'])
        gone = np.setdiff1d(i3_before, i2)
        removed_rows.append((r['frame'], allt[gone]))
fig, ax = plt.subplots(figsize=(8, 6))
ax.add_patch(plt.Rectangle((PERSON_REGION[0][0], PERSON_REGION[1][0]),
                           PERSON_REGION[0][1] - PERSON_REGION[0][0],
                           PERSON_REGION[1][1] - PERSON_REGION[1][0],
                           fill=False, edgecolor='#c92a2a', lw=2, label='HF-REAL-01 person region'))
for fi, rr in removed_rows:
    ax.scatter(rr[:, 0], rr[:, 1], s=12, label=f'f{fi} removed ({len(rr)})')
ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)')
ax.set_title('v3 removed points vs person region (f10 target unaffected, t=1.0s)')
ax.legend(fontsize=7); ax.grid(alpha=.25)
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / 'REMOVED_VS_PERSON_REGION.png', dpi=140); plt.close(fig)

for fi, rr in removed_rows:
    inside = np.sum((rr[:, 0] >= PERSON_REGION[0][0]) & (rr[:, 0] <= PERSON_REGION[0][1]) &
                    (rr[:, 1] >= PERSON_REGION[1][0]) & (rr[:, 1] <= PERSON_REGION[1][1]))
    print(f'f{fi}: removed={len(rr)}, inside_person_region={inside}')

# ── 任务2机器part：093958 三法区域交叠
lv = json.loads((EV1 / 'cap_20261013_093958_leveling.json').read_text(encoding='utf8'))
print('\n093958 leveling.json keys:', list(lv.keys())[:15])
for method in ('tls', 'svd', 'ransac'):
    block = lv.get(method) or lv.get('methods', {}).get(method)
    if not isinstance(block, dict):
        print(method, '-> missing'); continue
    print(f'\n== {method} ==')
    print(' keys:', list(block.keys()))
    for k in ('gate', 'status', 'fit', 'holdout', 'regions', 'recommended'):
        if k in block: print(f'  {k}: {block[k] if not isinstance(block[k], (list, dict)) else json.dumps(block[k], ensure_ascii=False)[:400]}')
