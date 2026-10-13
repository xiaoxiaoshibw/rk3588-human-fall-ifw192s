"""DET-06 author annotation proposal v1: person boxes on C1 frames via empty-reference diff,
person-like hard-negative structures on an empty frame. No network, no model forwards."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.patches import Rectangle

from det05_annotate import components
from experiment import sha

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
PRE = ROOT / 'artifacts/det06_prepared_r1'
C1 = ['cap_20261008_114205', 'cap_20261008_114254', 'cap_20261008_114340', 'cap_20261008_114422']
EMPTY = 'cap_20261008_114819'
EMPTY_OLD = 'cap_20261007_233658'
OLD_EMPTY_FRAMES = [17, 35, 53]
N_TEST = 6
VOX = .10
LINK = .08
HUMAN_MIN_N, HUMAN_MIN_TOP = 100, 1.2
HARD_MIN_N, HARD_MIN_TOP, HARD_MAX_TOP = 200, 1.2, 2.5
HARD_MAX_BOTTOM, HARD_MIN_ZS, HARD_MAX_SPAN = 0.6, 0.9, 1.2
SHOW_MIN_N = 50
COLORS = ['#D55E00', '#0072B2', '#009E73']


def spread(n, k):
    return [int(round(i / (k + 1) * (n - 1))) for i in range(1, k + 1)]


def read_prepared(sid, rec):
    f = PRE / sid / rec['file']
    r = Path(str(f) + '.rows')
    assert sha(f) == rec['sha256'] and sha(r) == rec['rows_sha256']
    pts = np.fromfile(f, dtype='<f4').reshape(-1, 4)
    rows = np.fromfile(r, dtype='<i8')
    assert len(pts) == len(rows) == rec['points']
    return pts, rows


def session_frames(manifest, sid):
    return next(s for s in manifest['sessions'] if s['sid'] == sid)['frames']


def build_occupied(manifest):
    chunks = []
    for rec in session_frames(manifest, EMPTY)[::8]:
        pts, _ = read_prepared(EMPTY, rec)
        chunks.append(pts)
    pts = np.concatenate(chunks)
    lo = pts[:, :3].min(0) - 1.0
    hi = pts[:, :3].max(0) + 1.0
    size = np.ceil((hi - lo) / VOX).astype(int) + 3
    occ = np.zeros(size, bool)
    k = np.floor((pts[:, :3] - lo) / VOX).astype(int) + 1
    occ[k[:, 0], k[:, 1], k[:, 2]] = True
    return lo, occ


def explained_mask(pts, lo, occ):
    k = np.floor((pts[:, :3] - lo) / VOX).astype(int) + 1
    k = np.clip(k, 1, np.asarray(occ.shape) - 2)
    out = np.zeros(len(k), bool)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                out |= occ[k[:, 0] + dx, k[:, 1] + dy, k[:, 2] + dz]
    return out


def cluster_list(xyz):
    ids, members = components(xyz, LINK)
    out = []
    for cid, mem in members.items():
        m = np.asarray(mem)
        out.append(dict(source_component=int(cid), n=len(mem), members=m,
                        z_min=float(xyz[m, 2].min()), z_max=float(xyz[m, 2].max()),
                        centroid=[float(xyz[m, 0].mean()), float(xyz[m, 1].mean())],
                        aabb_min=[float(xyz[m, 0].min()), float(xyz[m, 1].min())],
                        aabb_max=[float(xyz[m, 0].max()), float(xyz[m, 1].max())]))
    out.sort(key=lambda c: (-c['n'], c['source_component']))
    for i, c in enumerate(out):
        c['id'] = i
    return out


def clear_clusters(clusters):
    return [{k: v for k, v in c.items() if k != 'members'} for c in clusters]


def render(path, pts, draw_pts, clusters, title):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.6), layout='constrained')
    axes[0].scatter(pts[:, 0], pts[:, 1], s=2, c='#BBBBBB', alpha=.35, linewidths=0, rasterized=True)
    axes[1].scatter(pts[:, 0], pts[:, 2], s=2, c='#BBBBBB', alpha=.35, linewidths=0, rasterized=True)
    for c in clusters[:3]:
        m = c['members']
        col = COLORS[c['id'] % len(COLORS)]
        axes[0].scatter(draw_pts[m, 0], draw_pts[m, 1], s=6, c=col, alpha=.75, linewidths=0,
                        rasterized=True, label='#%d n=%d top=%.2f' % (c['id'], c['n'], c['z_max']))
        axes[1].scatter(draw_pts[m, 0], draw_pts[m, 2], s=6, c=col, alpha=.75, linewidths=0, rasterized=True)
        mn, mx = c['aabb_min'], c['aabb_max']
        axes[0].add_patch(Rectangle((mn[0], mn[1]), mx[0] - mn[0], mx[1] - mn[1],
                                    fill=False, ec=col, lw=1.6))
        axes[0].text(c['centroid'][0], c['centroid'][1], '#%d' % c['id'], fontsize=9, color=col)
    for ax, xl, yl in ((axes[0], 'x (m)', 'y (m)'), (axes[1], 'x (m)', 'z (m)')):
        ax.set(xlabel=xl, ylabel=yl)
        ax.grid(alpha=.15)
        ax.set_aspect('equal', adjustable='datalim')
    axes[0].legend(loc='upper right', fontsize=8, framealpha=.9)
    fig.suptitle(title, fontsize=11)
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
    manifest = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    lo, occ = build_occupied(manifest)
    params = dict(voxel_m=VOX, explain_step=1, link_m=LINK, human_min_n=HUMAN_MIN_N, human_min_top=HUMAN_MIN_TOP,
                  hard_min_n=HARD_MIN_N, hard_min_top=HARD_MIN_TOP, hard_max_top=HARD_MAX_TOP,
                  hard_max_bottom=HARD_MAX_BOTTOM, hard_min_z_span=HARD_MIN_ZS, hard_max_span=HARD_MAX_SPAN,
                  n_test_frames=N_TEST, empty_subsample=8, empty_frame=EMPTY, old_empty_frames=OLD_EMPTY_FRAMES)
    frames, lines = [], ['DET-06 annotation author proposal v2; deterministic; no model; pending user confirmation']
    for sid in C1:
        frames_all = session_frames(manifest, sid)
        session = next(s for s in manifest['sessions'] if s['sid'] == sid)
        for index in spread(len(frames_all), N_TEST):
            rec = next(f for f in frames_all if f['index'] == index)
            pts, rows = read_prepared(sid, rec)
            keep = explained_mask(pts, lo, occ)
            candidates = ~keep
            clusters = cluster_list(pts[candidates][:, :3])
            person = next((c for c in clusters if c['n'] >= HUMAN_MIN_N and c['z_max'] >= HUMAN_MIN_TOP), None)
            needs_manual = person is None
            gt = None
            if person is not None:
                m = person['members']
                gt = dict(centroid_xy=[float(pts[candidates][m, 0].mean()), float(pts[candidates][m, 1].mean())],
                          z_top=float(pts[candidates][m, 2].max()),
                          aabb_min=[float(pts[candidates][m, 0].min()), float(pts[candidates][m, 1].min()),
                                    float(pts[candidates][m, 2].min())],
                          aabb_max=[float(pts[candidates][m, 0].max()), float(pts[candidates][m, 1].max()),
                                    float(pts[candidates][m, 2].max())])
            payload = dict(sid=sid, index=index, name=session.get('name'), params=params,
                           provenance=dict(pre_manifest_sha256=sha(PRE / 'manifest.json'), pre_file=rec['file'],
                                           pre_sha256=rec['sha256'], pre_rows_sha256=rec['rows_sha256'],
                                           script_sha256=sha(Path(__file__))),
                           candidate_count=int(candidates.sum()),
                           clusters=clear_clusters(clusters[:8]), person_cluster_id=None if person is None else person['id'],
                           needs_manual=needs_manual, gt_proposal=gt,
                           person_rows=None if person is None else dict(
                               prepared=[int(v) for v in np.flatnonzero(candidates)[person['members']]],
                               raw=[int(v) for v in rows[np.flatnonzero(candidates)[person['members']]]]))
            json_path = out / ('ann_%s_%d.json' % (sid, index))
            with json_path.open('x', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, allow_nan=False)
            png_path = renders / ('ann_%s_%d.png' % (sid, index))
            shown = [c for c in clusters if c['n'] >= SHOW_MIN_N]
            hidden = len(clusters) - len(shown)
            title = ('DET-06 author proposal v2 (pending user confirmation) | %s %s frame %d/%d | cand=%d | %s%s'
                     % (sid[-6:], session.get('name'), index, len(frames_all), int(candidates.sum()),
                        'NEEDS MANUAL' if needs_manual else
                        'person #%d n=%d top=%.2f' % (person['id'], person['n'], person['z_max']),
                        '' if not hidden else ' | +%d small residues hidden (<%dpt)' % (hidden, SHOW_MIN_N)))
            render(png_path, pts, pts[candidates][:, :3], shown, title)
            frames.append(dict(sid=sid, index=index, candidate_count=int(candidates.sum()),
                               person=None if person is None else {k: v for k,
                               v in person.items() if k != 'members'}, needs_manual=needs_manual,
                               gt_proposal=gt, json=json_path.name, json_sha256=sha(json_path),
                               png=str(png_path.relative_to(WORK)).replace('\\', '/'), png_sha256=sha(png_path)))
            lines.append('%s frame %d cand=%d person=%s manual=%s' %
                         (sid[-6:], index, int(candidates.sum()),
                          None if person is None else 'n=%d top=%.2f' % (person['n'], person['z_max']), needs_manual))
    # person-like hard-negative structures on one empty frame
    empty_all = session_frames(manifest, EMPTY)
    hard_index = spread(len(empty_all), N_TEST)[2]
    rec = next(f for f in empty_all if f['index'] == hard_index)
    pts, rows = read_prepared(EMPTY, rec)
    tall = pts[pts[:, 2] >= .15]
    hard = []
    for c in cluster_list(tall[:, :3]):
        span_x = c['aabb_max'][0] - c['aabb_min'][0]
        span_y = c['aabb_max'][1] - c['aabb_min'][1]
        if (c['n'] >= HARD_MIN_N and HARD_MIN_TOP <= c['z_max'] <= HARD_MAX_TOP
                and c['z_min'] <= HARD_MAX_BOTTOM and (c['z_max'] - c['z_min']) >= HARD_MIN_ZS
                and max(span_x, span_y) <= HARD_MAX_SPAN):
            hard.append(c)
    hard = sorted(hard, key=lambda c: -c['z_max'])[:5]
    for i, c in enumerate(hard):
        c['id'] = i
    hard_payload = dict(sid=EMPTY, index=hard_index, params=params,
                        provenance=dict(pre_manifest_sha256=sha(PRE / 'manifest.json'), pre_file=rec['file'],
                                        pre_sha256=rec['sha256'], script_sha256=sha(Path(__file__))),
                        note='geometric person-like structures (tall, narrow); user confirms as non-person furniture',
                        structures=clear_clusters(hard))
    with (out / ('hardneg_%s_%d.json' % (EMPTY, hard_index))).open('x', encoding='utf-8') as f:
        json.dump(hard_payload, f, ensure_ascii=False, allow_nan=False)
    hard_png = renders / ('hardneg_%s_%d.png' % (EMPTY, hard_index))
    render(hard_png, pts, tall, hard, 'DET-06 hard negatives (geometric) | %s frame %d | %d tall structures'
           % (EMPTY[-6:], hard_index, len(hard)))
    summary = dict(tag=args.tag, script_sha256=sha(Path(__file__)), params=params,
                   pre_manifest_sha256=sha(PRE / 'manifest.json'),
                   empty_frames=dict(new=[dict(sid=EMPTY, index=i) for i in spread(len(empty_all), N_TEST)],
                                     old=[dict(sid=EMPTY_OLD, index=i) for i in OLD_EMPTY_FRAMES]),
                   frames=frames,
                   hardneg=dict(sid=EMPTY, index=hard_index, count=len(hard),
                                json=str((out / ('hardneg_%s_%d.json' % (EMPTY, hard_index))).relative_to(WORK)).replace('\\', '/'),
                                png=str(hard_png.relative_to(WORK)).replace('\\', '/'), png_sha256=sha(hard_png)),
                   files=[dict(path=str(p.relative_to(WORK)).replace('\\', '/'), sha256=sha(p))
                          for p in sorted(out.rglob('*')) if p.is_file()],
                   note='author proposal v2; render hides clusters <50pt; payload annotations unchanged; pending user confirmation before gt_eval_v1 freeze')
    with (out / 'ann_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, allow_nan=False, indent=2)
    with (evidence / (args.tag + '_author.json')).open('x', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, allow_nan=False, indent=2)
    (evidence / (args.tag + '_run.log')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    assert all(not f['needs_manual'] for f in frames), 'some frame needs manual person assignment'


if __name__ == '__main__':
    main()
