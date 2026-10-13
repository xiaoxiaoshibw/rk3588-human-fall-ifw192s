"""任务3 mask PNG 渲染：读 probe_215540.js 的 mask.json (xyz+survived)，画 top/side PNG。"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'
mask = np.array(json.loads((OUT / '215540_mask.json').read_text(encoding='utf8')))
js = json.loads((OUT / '215540_frame_stats.json').read_text(encoding='utf8'))
print('frames:', js['frameStats'][-1]['fi'] + 1, 'points in person region:', len(mask))

surv = mask[mask[:, 3] == 1]; rem = mask[mask[:, 3] == 0]
fig, axes = plt.subplots(1, 2, figsize=(15, 6))
for ax, (a0, a1, label) in zip(axes, [(0, 1, 'TOP'), (0, 2, 'SIDE')]):
    ax.scatter(rem[:, a0], rem[:, a1], s=3, color='#d64541', alpha=.5, label=f'removed ({len(rem)})')
    ax.scatter(surv[:, a0], surv[:, a1], s=5, color='#20a592', alpha=.9, label=f'survived ({len(surv)})')
    ax.set_title(f'215540 all frames {label}')
    ax.set_xlabel('x (m)' if a0 == 0 else 'y')
    ax.set_ylabel('z (m)' if a1 == 2 else 'y (m)')
    ax.grid(alpha=.25); ax.legend(fontsize=9, loc='upper left')
per_band_str = ' / '.join(f"{b}: {d['survived']}/{d['survived']+d['removed']}" for b, d in js['per_band'].items())
plt.suptitle(f'215540 P-arm (online-only static bg) — stationary person eaten\nper-band (survived/total): {per_band_str}')
plt.tight_layout()
fig.savefig(OUT / '215540_P_MASK.png', dpi=140); plt.close(fig)
print('wrote', OUT / '215540_P_MASK.png')
