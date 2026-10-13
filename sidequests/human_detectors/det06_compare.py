"""DET-06 comparison figure: base (first32, tau .20) vs z_rank32 (tau .35) final pedestrian boxes. Offline, no model."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon, Rectangle

from det06_metrics import final_boxes, trace_path

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ROOT = Path(__file__).resolve().parent
DET = ROOT / 'artifacts/det06_r1'
EVAL = DET / 'eval'
OUT = DET / 'compare'
NEW_PRE = ROOT / 'artifacts/det06_prepared_r1'
OLD_PRE = ROOT / 'artifacts/det02_prepared_r1'
TAU = {'base': .20, 'zrank': .35}
MATCH_M = .55
XLIM, YLIM = (0.0, 5.0), (-2.5, 2.0)


def read_pre(root, sid, index):
    m = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    s = next(x for x in m['sessions'] if x['sid'] == sid)
    rec = next(f for f in s['frames'] if f['index'] == index)
    return np.fromfile(root / sid / rec['file'], dtype='<f4').reshape(-1, 4)


def rect_corners(box):
    x, y, w, l, yaw = box[0], box[1], box[3], box[4], box[6]
    c, s = np.cos(yaw), np.sin(yaw)
    local = np.array([[-w / 2, -l / 2], [w / 2, -l / 2], [w / 2, l / 2], [-w / 2, l / 2]])
    return local @ np.array([[c, -s], [s, c]]) + [x, y]


def draw(ax, pts, boxes, gt, title, xy):
    ax.scatter(pts[:, 0], pts[:, 1], s=1, c='#BBBBBB', alpha=.5, linewidths=0, rasterized=True)
    if gt is not None:
        mn, mx = gt['aabb_min'], gt['aabb_max']
        ax.add_patch(Rectangle((mn[0], mn[1]), mx[0] - mn[0], mx[1] - mn[1], fill=False, ec='#009E73', lw=2.2))
        ax.plot(xy[0], xy[1], 'x', c='#009E73', ms=8)
    tp = fp = 0
    for b in boxes:
        hit = gt is not None and np.hypot(b[0] - xy[0], b[1] - xy[1]) <= MATCH_M
        tp += hit
        fp += (not hit)
        col = '#D55E00' if hit else '#0072B2'
        ax.add_patch(Polygon(rect_corners(b), closed=True, fill=False, ec=col, lw=1.6))
        ax.text(b[0], b[1], '%.2f' % b[7], fontsize=8, color=col)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_aspect('equal')
    ax.grid(alpha=.15)
    ax.set_title('%s  |  %s' % (title, ('命中 %d / 误报 %d' % (tp, fp)) if gt is not None else '误报 %d' % fp),
                 fontsize=9)
    ax.set_xlabel('x (m)', fontsize=8)
    ax.set_ylabel('y (m)', fontsize=8)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gt = json.loads((DET / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    rows = {(r['sid'], r['index'], r['arm']): r for r in
            (json.loads(l) for l in (EVAL / 'rows.jsonl').read_text(encoding='utf-8').splitlines())}
    cases = []
    for f in gt['test_frames']:
        if f['index'] == sorted(x['index'] for x in gt['test_frames'] if x['sid'] == f['sid'])[3]:
            cases.append(dict(sid=f['sid'], index=f['index'], gt=f['box'], xy=f['box']['centroid_xy'],
                              pre=NEW_PRE, label='人框帧 %s #%d' % (f['sid'][-6:], f['index'])))
    cases.append(dict(sid='cap_20261008_114819', index=122, gt=None, xy=None, pre=NEW_PRE,
                      label='空场 114819 #122（人形固定物处）'))
    cases.append(dict(sid='cap_20261007_233658', index=35, gt=None, xy=None, pre=OLD_PRE,
                      label='空场 233658 #35（旧空场）'))
    fig, axes = plt.subplots(len(cases), 2, figsize=(10, 3.2 * len(cases)), layout='constrained')
    summary = []
    for i, c in enumerate(cases):
        pts = read_pre(c['pre'], c['sid'], c['index'])
        for j, arm in enumerate(('base', 'zrank')):
            row = rows[(c['sid'], c['index'], arm)]
            tr = dict(np.load(trace_path(row)))
            boxes = final_boxes(tr, TAU[arm])
            name = '原版 first32（τ=%.2f）' % TAU[arm] if arm == 'base' else '覆盖 z_rank32（τ=%.2f）' % TAU[arm]
            xy = c['xy'] if c['xy'] is not None else [3.68, -0.48]
            draw(axes[i, j], pts, boxes, c['gt'], '%s\n%s' % (c['label'], name), xy)
            summary.append(dict(frame=c['label'], arm=arm, tau=TAU[arm], boxes=len(boxes),
                                scores=[round(float(b[7]), 3) for b in boxes]))
    fig.savefig(OUT / 'compare_grid.png', dpi=110)
    plt.close(fig)
    (OUT / 'compare_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('wrote', OUT / 'compare_grid.png', 'cases', len(cases))


if __name__ == '__main__':
    main()
