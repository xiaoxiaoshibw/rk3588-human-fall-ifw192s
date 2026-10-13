"""DET-05 author annotation proposal: point labels (human/furniture/mixed_uncertain) with prepared/raw row binding, review renders, summary. No network."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
PRE = ROOT / 'artifacts/det02_prepared_r1'
FG = ROOT / 'artifacts/det02_foreground_r1'
SEED_FILE = WORK / 'docs/sidequests/evidence/2026-10-07_det01_r2/user_truth_seeds.json'
LABEL_FRAMES = [('cap_20261007_215540', 32), ('cap_20261007_215607', 33), ('cap_20261007_215623', 33),
                ('cap_20261007_215643', 3), ('cap_20261007_215643', 7), ('cap_20261007_215643', 11),
                ('cap_20261007_215643', 12), ('cap_20261007_215643', 17), ('cap_20261007_215643', 28),
                ('cap_20261007_215643', 37)]
SCOPE_R = 1.0
Z_MIN, Z_MAX, Z_HUMAN = .05, 2.30, .15
LINK = .08
HUMAN_MIN_N, HUMAN_MIN_TOP, HUMAN_MAX_DIST = 50, 1.2, .45
FURN_MIN_N = 10
COLORS = {'human': '#D55E00', 'furniture': '#0072B2', 'mixed_uncertain': '#9A9A9A'}
CLASSES = ['human', 'furniture', 'mixed_uncertain']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def components(xyz, radius):
    """Single-linkage components via cKDTree at radius; ids canonicalized to smallest member index."""
    tree = cKDTree(xyz)
    parent = np.arange(len(xyz))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in tree.query_pairs(radius):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    root = np.array([find(i) for i in range(len(xyz))])
    first = {}
    for i in range(len(xyz)):
        first.setdefault(int(root[i]), i)
    ids = np.array([first[int(r)] for r in root], dtype='i8')
    members = {}
    for i, cid in enumerate(ids.tolist()):
        members.setdefault(cid, []).append(i)
    return ids, members


def classify(pre, seed_xy):
    """Deterministic author proposal for one frame; returns scope rows, classes, clusters, human, gt."""
    dist = np.hypot(pre[:, 0] - seed_xy[0], pre[:, 1] - seed_xy[1])
    scope = (dist <= SCOPE_R) & (pre[:, 2] >= Z_MIN) & (pre[:, 2] <= Z_MAX)
    idx = np.flatnonzero(scope)
    high = pre[idx, 2] >= Z_HUMAN
    ids, members = components(pre[idx[high]][:, :3], LINK)
    high_idx = idx[high]
    clusters = []
    for cid, mem in members.items():
        rows = high_idx[np.asarray(mem)]
        clusters.append(dict(source_component=int(cid), n=len(mem),
                             z_min=float(pre[rows, 2].min()), z_max=float(pre[rows, 2].max()),
                             centroid=[float(pre[rows, 0].mean()), float(pre[rows, 1].mean())],
                             xspan=float(pre[rows, 0].max() - pre[rows, 0].min()),
                             dist_seed=float(np.hypot(pre[rows, 0].mean() - seed_xy[0],
                                                      pre[rows, 1].mean() - seed_xy[1]))))
    clusters.sort(key=lambda c: (-c['n'], c['source_component']))
    for k, c in enumerate(clusters):
        c['id'] = k
    candidates = [c for c in clusters if c['n'] >= HUMAN_MIN_N and c['z_max'] >= HUMAN_MIN_TOP]
    human = min(candidates, key=lambda c: (c['dist_seed'], c['id'])) if candidates else None
    needs_manual = human is None
    if not needs_manual and human['dist_seed'] > HUMAN_MAX_DIST:
        needs_manual, human = True, None
    cid_map = {c['source_component']: c['id'] for c in clusters}
    size_map = {c['source_component']: c['n'] for c in clusters}
    cls = np.full(len(idx), 'furniture', dtype='<U16')
    cls[high] = 'mixed_uncertain'
    human_cid = human['source_component'] if human is not None else None
    hi_pos = np.flatnonzero(high)
    for k, source in enumerate(ids.tolist()):
        if human_cid is not None and source == human_cid:
            cls[hi_pos[k]] = 'human'
        elif size_map[source] >= FURN_MIN_N:
            cls[hi_pos[k]] = 'furniture'
    for c in clusters:
        c['cls'] = ('human' if human_cid is not None and c['source_component'] == human_cid else
                    'furniture' if c['n'] >= FURN_MIN_N else 'mixed_uncertain')
    point_cluster = np.full(len(idx), -1, dtype='i8')
    for k, source in enumerate(ids.tolist()):
        point_cluster[hi_pos[k]] = cid_map[source]
    human_mask = cls == 'human'
    gt = None
    if human_mask.any():
        rows = idx[human_mask]
        gt = dict(centroid_xy=[float(pre[rows, 0].mean()), float(pre[rows, 1].mean())],
                  z_top=float(pre[rows, 2].max()), n_human=int(human_mask.sum()),
                  aabb_min=[float(pre[rows, 0].min()), float(pre[rows, 1].min()), float(pre[rows, 2].min())],
                  aabb_max=[float(pre[rows, 0].max()), float(pre[rows, 1].max()), float(pre[rows, 2].max())])
    return idx, cls, clusters, human_cid, needs_manual, gt, point_cluster


def render(path, pre, idx, cls, clusters, gt, seed_xy, sid, index, needs_manual):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.6), layout='constrained')
    p = pre[idx]
    for name in CLASSES:
        m = cls == name
        if not m.any():
            continue
        axes[0].scatter(p[m, 0], p[m, 1], s=5, c=COLORS[name], alpha=.6, linewidths=0, rasterized=True,
                        label='%s (%d)' % (name, int(m.sum())))
        axes[1].scatter(p[m, 0], p[m, 2], s=5, c=COLORS[name], alpha=.6, linewidths=0, rasterized=True)
    ax = axes[0]
    for c in clusters:
        if c['n'] >= FURN_MIN_N:
            ax.text(c['centroid'][0], c['centroid'][1], '#%d n=%d' % (c['id'], c['n']),
                    fontsize=7, color=COLORS[c['cls']] if c['cls'] in COLORS else '#333333')
    if gt is not None:
        ax.plot(gt['centroid_xy'][0], gt['centroid_xy'][1], marker='*', ms=14, c='#CC79A7')
        axes[1].plot(gt['centroid_xy'][0], gt['z_top'], marker='*', ms=12, c='#CC79A7')
    ax.plot(seed_xy[0], seed_xy[1], marker='x', ms=10, c='red')
    for r, style in [(.55, '--'), (1.0, ':')]:
        ax.add_patch(Circle(seed_xy, r, fill=False, edgecolor='#666666', linewidth=.8, linestyle=style))
    x0, x1 = float(p[:, 0].min()) - .1, float(p[:, 0].max()) + .1
    y0, y1 = float(p[:, 1].min()) - .1, float(p[:, 1].max()) + .1
    gx = np.arange(np.floor(x0 / .16) * .16, x1, .16)
    gy = np.arange(np.floor(y0 / .16) * .16, y1, .16)
    for g in gx:
        ax.axvline(g, lw=.35, color='#CCCCCC', zorder=0)
    for g in gy:
        ax.axhline(g, lw=.35, color='#CCCCCC', zorder=0)
    ax.set(xlabel='x (m)', ylabel='y (m)', aspect='equal',
           title='BEV (0.16m pillar grid, dashed r=0.55, dotted r=1.0)')
    ax.grid(alpha=.15)
    ax.legend(loc='upper right', fontsize=8, framealpha=.9)
    side = axes[1]
    side.axvline(seed_xy[0], color='red', lw=.8, ls=':')
    side.axhline(.15, color='#666666', lw=.8, ls='--')
    side.set(xlabel='x (m)', ylabel='z (m)', title='side x-z (dashed: z=0.15 human-class floor)')
    side.grid(alpha=.2)
    counts = {name: int((cls == name).sum()) for name in CLASSES}
    fig.suptitle('DET-05 author proposal (pending user confirmation) | %s frame %d | n=%d human=%d furniture=%d mixed=%d%s'
                 % (sid[-6:], index, len(idx), counts['human'], counts['furniture'], counts['mixed_uncertain'],
                    ' | NEEDS MANUAL' if needs_manual else ''), fontsize=11)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--tag', default='03_annotation')
    args = parser.parse_args()
    out = args.out.resolve()
    evidence = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    renders = out / 'renders'
    renders.mkdir()
    pre_manifest = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    fg_manifest = json.loads((FG / 'manifest.json').read_text(encoding='utf-8'))
    seed_all = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    seeds = {s['session']: s['xy_m'] for s in seed_all['sessions']}
    pres = {s['sid']: s for s in pre_manifest['sessions']}
    fgs = {s['sid']: s for s in fg_manifest['sessions']}
    params = dict(scope_r=SCOPE_R, z=[Z_MIN, Z_MAX], z_human=Z_HUMAN, r_link=LINK,
                  human_min_n=HUMAN_MIN_N, human_min_top=HUMAN_MIN_TOP, human_max_dist=HUMAN_MAX_DIST,
                  furn_min_n=FURN_MIN_N, classes=CLASSES)
    frames = []
    lines = ['DET-05 annotation author proposal; deterministic; no network; pending user confirmation']
    for sid, index in LABEL_FRAMES:
        pre_rec = next(f for f in pres[sid]['frames'] if f['index'] == index)
        pre_path = PRE / sid / pre_rec['file']
        rows_path = PRE / sid / (pre_rec['file'] + '.rows')
        assert sha(pre_path) == pre_rec['sha256'] and sha(rows_path) == pre_rec['rows_sha256']
        pre = np.fromfile(pre_path, dtype='<f4').reshape(-1, 4)
        rows = np.fromfile(rows_path, dtype='<i8')
        assert len(pre) == len(rows) == pre_rec['points']
        fg_rec = next(f for f in fgs[sid]['frames'] if f['index'] == index)
        variant_bind = {}
        for variant in ('B_workspace', 'E_cleanup'):
            rec = fg_rec['variants'][variant]
            fpath, ipath = FG / sid / rec['file'], FG / sid / (rec['file'] + '.ids')
            assert sha(fpath) == rec['sha256'] and sha(ipath) == rec['ids_sha256']
            variant_bind[variant] = dict(file=rec['file'], sha256=rec['sha256'], ids_sha256=rec['ids_sha256'])
        idx, cls, clusters, human_cid, needs_manual, gt, point_cluster = classify(pre, seeds[sid])
        payload = dict(sid=sid, index=index, seed_xy=seeds[sid], params=params,
                       provenance=dict(pre_file=pre_rec['file'], pre_sha256=pre_rec['sha256'],
                                       pre_rows_sha256=pre_rec['rows_sha256'], fg_variants=variant_bind,
                                       seed_sha256=sha(SEED_FILE), script_sha256=sha(Path(__file__))),
                       scope_n=len(idx), human_component_id=human_cid, needs_manual=needs_manual,
                       points=dict(prepared_rows=idx.tolist(), raw_rows=rows[idx].tolist(),
                                   x=pre[idx, 0].tolist(), y=pre[idx, 1].tolist(), z=pre[idx, 2].tolist(),
                                   intensity=pre[idx, 3].tolist(), cluster=point_cluster.tolist(),
                                   cls=cls.tolist()),
                       clusters=clusters, gt_proposal=gt)
        json_path = out / ('ann_%s_%d.json' % (sid, index))
        with json_path.open('x', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, allow_nan=False)
        png_path = renders / ('ann_%s_%d.png' % (sid, index))
        render(png_path, pre, idx, cls, clusters, gt, seeds[sid], sid, index, needs_manual)
        counts = {name: int((cls == name).sum()) for name in CLASSES}
        frames.append(dict(sid=sid, index=index, needs_manual=needs_manual, counts=counts,
                           gt_proposal=gt, human_component_id=human_cid,
                           json=json_path.name, json_sha256=sha(json_path),
                           png=str(png_path.relative_to(WORK)).replace('\\', '/'), png_sha256=sha(png_path)))
        lines.append('%s/%d scope=%d human=%d furniture=%d mixed=%d top=%s manual=%s' %
                     (sid[-6:], index, len(idx), counts['human'], counts['furniture'],
                      counts['mixed_uncertain'], None if gt is None else '%.2f' % gt['z_top'], needs_manual))
    manifest = dict(script_sha256=sha(Path(__file__)), params=params, seed_sha256=sha(SEED_FILE),
                    pre_manifest_sha256=sha(PRE / 'manifest.json'), fg_manifest_sha256=sha(FG / 'manifest.json'),
                    frames=frames,
                    files=[dict(path=str(p.relative_to(WORK)).replace('\\', '/'), sha256=sha(p))
                           for p in sorted(out.rglob('*')) if p.is_file()])
    with (out / 'ann_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, allow_nan=False, indent=2)
    summary = dict(tag=args.tag, script_sha256=manifest['script_sha256'], params=params,
                   seed_sha256=manifest['seed_sha256'], pre_manifest_sha256=manifest['pre_manifest_sha256'],
                   fg_manifest_sha256=manifest['fg_manifest_sha256'],
                   artifacts_dir='sidequests/human_detectors/artifacts/det05_r1/annotate',
                   frames=frames, note='author proposal v1; labels bind prepared frames and raw capture rows; pending user confirmation before any experiment')
    with (evidence / (args.tag + '_author.json')).open('x', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, allow_nan=False, indent=2)
    with (evidence / (args.tag + '_run.log')).open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    assert all(not f['needs_manual'] for f in frames), 'some frame needs manual human component assignment'
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
