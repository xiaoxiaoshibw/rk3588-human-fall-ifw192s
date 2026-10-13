"""GT v2 proposal (NOT frozen, needs user confirmation): person-box z_min without the empty-template
mask effect, plus a connectivity re-check of the frozen hard-negative structures. Offline, 0 forwards."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from det06_annotate import components, read_prepared
from det06_eval import load_b

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ROOT = Path(__file__).resolve().parent
DET06 = ROOT / 'artifacts/det06_r1'
NEW_FG = ROOT / 'artifacts/det06_foreground_r1'
NEW_PRE = ROOT / 'artifacts/det06_prepared_r1'


def person_zmin(frame):
    pts, _ = load_b(frame['sid'], frame['index'], NEW_FG, NEW_PRE)
    mn, mx = np.asarray(frame['box']['aabb_min']), np.asarray(frame['box']['aabb_max'])
    m = ((pts[:, 0] >= mn[0] - .02) & (pts[:, 0] <= mx[0] + .02) &
         (pts[:, 1] >= mn[1] - .02) & (pts[:, 1] <= mx[1] + .02))
    z = pts[m, 2]
    return dict(old=float(mn[2]), v2=float(z.min()), z_top=float(max(mx[2], z.max())),
                n_in_footprint=int(m.sum()), n_below_old=int((z < mn[2]).sum()))


def fixture_check(gt):
    man = json.loads((NEW_PRE / 'manifest.json').read_text(encoding='utf-8'))
    hf = gt['hardneg_frame']
    rec = next(f for s in man['sessions'] if s['sid'] == hf['sid'] for f in s['frames'] if f['index'] == hf['index'])
    pts, _ = read_prepared(hf['sid'], rec)
    tall = pts[pts[:, 2] >= .15]
    ids, members = components(tall[:, :3], 0.08)
    inv = {}
    for i, cid in enumerate(ids.tolist()):
        inv.setdefault(cid, []).append(i)
    out = []
    for s in gt['hard_negative_structures']:
        c = np.asarray(s['centroid'])
        best = None
        for cid, mem in inv.items():
            m = np.asarray(mem)
            d = np.hypot(tall[m, 0] - c[0], tall[m, 1] - c[1]).min()
            if d <= .30 and (best is None or d < best[0]):
                best = (d, m)
        if best is None:
            out.append(dict(centroid=s['centroid'], frozen_z=[s['z_min'], s['z_max']], component=None))
            continue
        d, m = best
        out.append(dict(centroid=s['centroid'], frozen_z=[s['z_min'], s['z_max']],
                        component=dict(n=len(m), z=[float(tall[m, 2].min()), float(tall[m, 2].max())],
                                       z_span=float(tall[m, 2].max() - tall[m, 2].min()),
                                       xy_span=[float(np.ptp(tall[m, 0])), float(np.ptp(tall[m, 1]))],
                                       min_dist_to_centroid=float(d))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    gt = json.loads((DET06 / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    prop = dict(status='PROPOSAL ONLY - not frozen; requires user confirmation before any freeze',
                note='person z_min v2 = lowest foreground point (B workspace crop, z>=0.10) inside the GT AABB '
                     'footprint; the DET-06 z_min is an empty-template-mask artifact. BEV metrics are unaffected '
                     '(they do not use z); this only fixes 3D box reporting. No fixture structure changes proposed.',
                person={}, fixtures=None)
    for f in gt['test_frames']:
        prop['person']['%s|%d' % (f['sid'], f['index'])] = person_zmin(f)
    prop['fixtures'] = fixture_check(gt)
    (a.out / 'gt_v2_proposal.json').write_text(json.dumps(prop, ensure_ascii=False, indent=2), encoding='utf-8')

    # one confirmation figure: x-z side view, one frame per session
    frames = []
    for sid in ['cap_20261008_114205', 'cap_20261008_114254', 'cap_20261008_114340', 'cap_20261008_114422']:
        fs = sorted((f for f in gt['test_frames'] if f['sid'] == sid), key=lambda f: f['index'])
        frames.append(fs[3])
    fig, axes = plt.subplots(1, 4, figsize=(18, 5.2), layout='constrained')
    for ax, f in zip(axes, frames):
        pts, _ = load_b(f['sid'], f['index'], NEW_FG, NEW_PRE)
        xn = f['box']['centroid_xy'][0]
        m = (pts[:, 0] > xn - 1.2) & (pts[:, 0] < xn + 1.2) & (pts[:, 1] > f['box']['centroid_xy'][1] - .6) & \
            (pts[:, 1] < f['box']['centroid_xy'][1] + .6)
        ax.scatter(pts[m, 0], pts[m, 2], s=2, c='#BBBBBB', linewidths=0, rasterized=True)
        mn, mx = f['box']['aabb_min'], f['box']['aabb_max']
        zmin2 = prop['person']['%s|%d' % (f['sid'], f['index'])]['v2']
        ax.add_patch(Rectangle((mn[0], mn[2]), mx[0] - mn[0], mx[2] - mn[2], fill=False, ec='#009E73', lw=1.8,
                               label='冻结 GT 框（z_min %.2f）' % mn[2]))
        ax.axhline(zmin2, c='#D55E00', ls='--', lw=1.6, label='v2 z_min %.2f' % zmin2)
        ax.axhline(0.0, c='k', ls=':', lw=1, label='地面（配平 z=0）')
        ax.set(xlabel='x (m)', ylabel='z (m)', title='%s #%d' % (f['sid'][-6:], f['index']), ylim=(-.4, 2.4))
        ax.grid(alpha=.2)
        ax.legend(fontsize=7, loc='upper right')
    fig.suptitle('GT v2 提案：人框 z_min（模板掩膜伪影修正）— 待用户确认，未冻结', fontsize=12)
    fig.savefig(a.out / 'fig_gt_zmin_proposal.png', dpi=110)
    plt.close(fig)
    print('DONE gt proposal', a.out)


if __name__ == '__main__':
    main()
