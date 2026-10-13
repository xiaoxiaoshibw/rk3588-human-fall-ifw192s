"""Actual source points only; no inferred skeleton or GT. Existing matplotlib dependency."""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
bundle = json.loads((OUT / 'review_bundle.json').read_text(encoding='utf8'))
colors = {'HUMAN_EVIDENCE': '#218568', 'OBJECT_EVIDENCE': '#788795', 'UNKNOWN': '#684fa7'}
fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
for ax, suffix in zip(axes.flat, ['114205', '114254', '114340', '114422']):
    case = next(r for r in bundle['cases'] if r['sid'].endswith(suffix) and r['ordinal'] in [122, 135, 140, 97])
    descriptions = []
    for c in case['clusters']:
        pts = [p['xyz'] for p in c['points'] if not p['raw_invalid']]
        if not pts:
            continue
        ax.scatter([p[0] for p in pts], [p[2] for p in pts], s=1, color=colors[c['semantic']], rasterized=True)
        descriptions.append('c%d %s (%d)' % (c['ci'], c['semantic'].replace('_EVIDENCE', ''), len(pts)))
    removed = [p['xyz'] for p in case['deleted']]
    if removed:
        ax.scatter([p[0] for p in removed], [p[2] for p in removed], s=5, c='#db382e', marker='x')
    ax.set(title=suffix + ' f' + str(case['ordinal']) + ' ' + case['mode'], xlabel='X (m)', ylabel='Z (m)')
    ax.text(.02, .98, '\n'.join(descriptions), transform=ax.transAxes, va='top', fontsize=8)
    ax.grid(alpha=.15)
    if 'zoom' in sys.argv:
        ax.set_xlim(1, 3.5)
        ax.set_ylim(0, 2.5)
fig.suptitle('Frozen S-A+ on full cleanup clusters; red = deletion clues; no human GT', fontsize=12)
for ext in ['png', 'svg']:
    target = OUT / (('full_cluster_cases_zoom.' if 'zoom' in sys.argv else 'full_cluster_cases.') + ext)
    if target.exists():
        raise FileExistsError(target)
    fig.savefig(target, dpi=160, facecolor='white')
plt.close(fig)
print('matplotlib', matplotlib.__version__, 'four actual middle-frame full-cluster views')
