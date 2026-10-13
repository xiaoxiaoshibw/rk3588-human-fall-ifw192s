"""DET-06 review, offline (no model forwards): independent recount, LOSO operating-point check,
label / geometry / input / density diagnostics. Reuses det06_metrics, det06_annotate, det06_eval, det05, det06_compare."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from det05 import iou_rot_aabb
from det06_annotate import build_occupied, explained_mask, read_prepared
from det06_compare import draw, read_pre
from det06_eval import load_b
from det06_metrics import MATCH_M, TAUS, final_boxes, trace_path
from experiment import sha

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ROOT = Path(__file__).resolve().parent
DET = ROOT / 'artifacts/det06_r1'
EVAL = DET / 'eval'
PRE = ROOT / 'artifacts/det06_prepared_r1'
FG = ROOT / 'artifacts/det06_foreground_r1'
OLD_FG = ROOT / 'artifacts/det06_foreground_old_r1'
OLD_PRE = ROOT / 'artifacts/det02_prepared_r1'
UP = ROOT / 'artifacts/upstream'
ZS = 1.73
BUDGETS = (0.1, 0.5, 1.0)
RADII = (0.3, 0.4, MATCH_M)
TAU_GRID = (0.10, 0.20, 0.25, 0.35)
ARMS = ('base', 'zrank')
STRUCT_NAMES = ['fixture_A', 'table', 'fixture_B_seated']


def frame_rec(man, sid, index):
    sess = next(s for s in man['sessions'] if s['sid'] == sid)
    return next(f for f in sess['frames'] if f['index'] == index)


def hits(frames, traces, arm, tau, radius=MATCH_M):
    tp, fp, dup, iou = [], [], [], []
    for f in frames:
        b = final_boxes(traces[(f['sid'], f['index'], arm)], tau)
        xy = f['box']['centroid_xy']
        inside = np.hypot(b[:, 0] - xy[0], b[:, 1] - xy[1]) <= radius
        tp.append(int(inside.any()))
        fp.append(int((~inside).sum()))
        dup.append(int(inside.sum() >= 2))
        iou.append(int(max([iou_rot_aabb(x[:7], f['box']) for x in b], default=0.0) >= .5))
    return np.array(tp), np.array(fp), np.array(dup), np.array(iou)


def check_rows(rows, by, traces):
    counts = {}
    for r in rows:
        k = '%s/%s' % (r['kind'], r['arm'])
        counts[k] = counts.get(k, 0) + 1
        assert sha(trace_path(r)) == r['trace_sha256'], r['trace']
    assert len(by) == len(rows) == 74
    bad = []
    for r in rows:
        mine = final_boxes(traces[(r['sid'], r['index'], r['arm'])], 0.10)
        stored = sorted([d for d in r['stages']['clockwise']['detections'] if d['label'] == 0],
                        key=lambda d: -d['score'])
        same = len(mine) == len(stored) and all(
            abs(mine[i, 7] - stored[i]['score']) < 1e-5 and np.allclose(mine[i, :7], stored[i]['box'], atol=1e-4)
            for i in range(len(mine)))
        if not same:
            bad.append(dict(sid=r['sid'], index=r['index'], arm=r['arm'], mine=len(mine), stored=len(stored)))
    return dict(rows=len(rows), counts=counts, final_boxes_vs_model_mismatch=bad)


def sweep(frames, traces, arm):
    table = {}
    for t in TAUS:
        tp, fp, dup, iou = hits(frames, traces, arm, t)
        table[str(t)] = dict(recall_center=float(tp.mean()), recall_iou=float(iou.mean()),
                             fp_per_frame=float(fp.mean()), dup_frames=int(dup.sum()))
    return table


def operating(table):
    out = {}
    for b in BUDGETS:
        elig = [(float(k), v) for k, v in table.items() if v['fp_per_frame'] <= b + 1e-9]
        if not elig:
            out[str(b)] = None
            continue
        t, v = max(elig, key=lambda kv: (kv[1]['recall_center'], -kv[1]['fp_per_frame']))
        out[str(b)] = dict(tau=t, recall_center=v['recall_center'], fp_per_frame=v['fp_per_frame'])
    return out


def loso(frames, traces, arm):
    sess = np.array([f['sid'] for f in frames])
    per = [hits(frames, traces, arm, t) for t in TAUS]
    TP = np.stack([p[0] for p in per], 1).astype(float)
    FP = np.stack([p[1] for p in per], 1).astype(float)
    out = {}
    for b in BUDGETS:
        tp_sum = fp_sum = n_cov = 0
        picks = {}
        for s in sorted(set(sess)):
            tr = sess != s
            te = ~tr
            fp_tr = FP[tr].mean(0)
            rec_tr = TP[tr].mean(0)
            elig = np.flatnonzero(fp_tr <= b + 1e-9)
            if not len(elig):
                picks[s] = None
                continue
            k = max(elig, key=lambda j: (rec_tr[j], -fp_tr[j]))
            picks[s] = TAUS[k]
            tp_sum += TP[te, k].sum()
            fp_sum += FP[te, k].sum()
            n_cov += te.sum()
        out[str(b)] = dict(picks=picks, n_frames=int(n_cov),
                           recall_center=float(tp_sum / n_cov) if n_cov else None,
                           fp_per_frame=float(fp_sum / n_cov) if n_cov else None)
    return out


def loc_name(x, y, structs, rad=0.5):
    d = [np.hypot(x - c[0], y - c[1]) for c in structs]
    k = int(np.argmin(d))
    return STRUCT_NAMES[k] if d[k] <= rad else 'other'


def fp_locations(frames, traces, arm, structs, tau, gt_frames):
    cnt, other = {}, []
    for f in frames:
        b = final_boxes(traces[(f['sid'], f['index'], arm)], tau)
        if gt_frames:
            xy = f['box']['centroid_xy']
            keep = np.hypot(b[:, 0] - xy[0], b[:, 1] - xy[1]) > MATCH_M
        else:
            keep = np.ones(len(b), bool)
        for x in b[keep]:
            nm = loc_name(x[0], x[1], structs)
            cnt[nm] = cnt.get(nm, 0) + 1
            if nm == 'other':
                other.append((float(x[0]), float(x[1]), float(x[7])))
    n = len(frames)
    return {k: round(v / n, 3) for k, v in sorted(cnt.items())}, other


def grid_counts(other):
    grid = {}
    for x, y, _ in other:
        k = '(%.1f,%.1f)' % (np.floor(x * 2) / 2, np.floor(y * 2) / 2)
        grid[k] = grid.get(k, 0) + 1
    return dict(sorted(grid.items(), key=lambda kv: -kv[1])[:8])


def footprint_extent(b):
    c, s = np.cos(b[6]), np.sin(b[6])
    corners = np.array([[-b[3] / 2, -b[4] / 2], [b[3] / 2, -b[4] / 2],
                        [b[3] / 2, b[4] / 2], [-b[3] / 2, b[4] / 2]]) @ np.array([[c, -s], [s, c]]) + b[:2]
    return float(np.ptp(corners[:, 0])), float(np.ptp(corners[:, 1]))


def geometry(frames, traces, arm):
    out = []
    for f in frames:
        b = final_boxes(traces[(f['sid'], f['index'], arm)], 0.10)
        xy = np.asarray(f['box']['centroid_xy'])
        d = np.hypot(b[:, 0] - xy[0], b[:, 1] - xy[1]) if len(b) else np.zeros(0)
        ok = np.flatnonzero(d <= MATCH_M)
        g = f['box']
        mn, mx = np.asarray(g['aabb_min']), np.asarray(g['aabb_max'])
        rec = dict(sid=f['sid'], index=f['index'], matched=bool(len(ok)))
        if len(ok):
            best = b[ok[np.argmax(b[ok, 7])]]
            ex, ey = footprint_extent(best)
            zb = float(best[2]) + ZS
            rec.update(score=float(best[7]), dx=float(best[0] - xy[0]), dy=float(best[1] - xy[1]),
                       ex_minus_gt=ex - float(mx[0] - mn[0]), ey_minus_gt=ey - float(mx[1] - mn[1]),
                       box_w=float(best[3]), box_l=float(best[4]), box_h=float(best[5]),
                       h_minus_gt=float(best[5] - (mx[2] - mn[2])),
                       bottom_minus_gt=zb - float(mn[2]), top_minus_gt=zb + float(best[5]) - float(mx[2]),
                       yaw=float(best[6]), iou=float(iou_rot_aabb(best[:7], g)))
        out.append(rec)
    return out


def med(recs, key):
    v = [r[key] for r in recs if r['matched']]
    return dict(median=float(np.median(v)), min=float(np.min(v)), max=float(np.max(v)), n=len(v)) if v else None


def pooled_ops(test, empty, traces, arm):
    """FP per frame over test + empty frames (every frame is an FP opportunity), recall on test frames."""
    table = {}
    for t in TAUS:
        tp, fp_t, _, _ = hits(test, traces, arm, t)
        fp_e = np.array([len(final_boxes(traces[(e['sid'], e['index'], arm)], t)) for e in empty])
        n = len(test) + len(empty)
        table[str(t)] = dict(recall_center=float(tp.mean()), fp_per_frame_pooled=float((fp_t.sum() + fp_e.sum()) / n),
                             fp_per_empty_frame=float(fp_e.mean()), fp_per_test_frame=float(fp_t.mean()))
    out = {}
    for b in BUDGETS:
        elig = [(float(k), v) for k, v in table.items() if v['fp_per_frame_pooled'] <= b + 1e-9]
        if not elig:
            out[str(b)] = None
            continue
        t, v = max(elig, key=lambda kv: (kv[1]['recall_center'], -kv[1]['fp_per_frame_pooled']))
        out[str(b)] = dict(tau=t, recall_center=v['recall_center'], fp_per_frame_pooled=v['fp_per_frame_pooled'])
    return table, out


def fixture_visibility(test, fixture_xy, sensor_xy=(0.0, 0.0)):
    out = []
    for f in test:
        pts, _ = load_b(f['sid'], f['index'], FG, PRE)
        m = np.hypot(pts[:, 0] - fixture_xy[0], pts[:, 1] - fixture_xy[1]) <= .45
        xy = np.asarray(f['box']['centroid_xy'])
        ang = lambda p: float(np.degrees(np.arctan2(p[1] - sensor_xy[1], p[0] - sensor_xy[0])))
        out.append(dict(sid=f['sid'], index=f['index'], fixture_B_points_within_0p45=int(m.sum()),
                        bearing_person_deg=round(ang(xy), 2), bearing_fixture_deg=round(ang(fixture_xy), 2),
                        bearing_gap_deg=round(abs(ang(xy) - ang(fixture_xy)), 2)))
    return out


def fixture_points(empty, centre):
    zs, ints, counts = [], [], []
    for e in empty:
        fg, pr = (FG, PRE) if e['sid'].startswith('cap_20261008') else (OLD_FG, OLD_PRE)
        pts, _ = load_b(e['sid'], e['index'], fg, pr)
        m = np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1]) <= MATCH_M
        zs.append(pts[m, 2])
        ints.append(pts[m, 3])
        counts.append(int(m.sum()))
    z, i = np.concatenate(zs), np.concatenate(ints)
    bins = [.1, .3, .6, .9, 1.2, 1.5, 1.8, 2.2, 2.6]
    frac = np.histogram(z, bins=bins)[0] / len(z)
    return dict(n_per_frame_median=float(np.median(counts)), z_raw_p5_p50_p95=np.percentile(z, [5, 50, 95]).round(3).tolist(),
                band_frac=[round(float(v), 3) for v in frac], intensity_raw_p5_p50_p95=np.percentile(i, [5, 50, 95]).round(1).tolist(),
                intensity_div1023_p50=float(np.median(i) / 1023))


def anchor_field(traces, keys, centre, radius=.45):
    out = []
    for key in keys:
        tr = traces[key]
        a, s = tr['anchors'], tr['raw_cls_scores'][:, 0]
        d = np.hypot(a[:, 0] - centre[0], a[:, 1] - centre[1])
        m = np.flatnonzero(d <= radius)
        j = m[np.argmax(s[m])]
        nn = m[np.argmin(d[m])]
        out.append(dict(sid=key[0], index=key[1], arm=key[2], peak_score=float(s[j]),
                        peak_offset=[float(a[j, 0] - centre[0]), float(a[j, 1] - centre[1])],
                        nearest_score=float(s[nn]), nearest_dist=float(d[nn]), n_anchor=int(len(m))))
    return out


def label_checks(gt):
    man = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    lo, occ = build_occupied(man)
    frames = []
    for f in gt['test_frames']:
        pts, _ = read_prepared(f['sid'], frame_rec(man, f['sid'], f['index']))
        xy = np.asarray(f['box']['centroid_xy'])
        near = pts[np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1]) <= MATCH_M]
        expl = explained_mask(near, lo, occ)
        bands = []
        for a, b in [(-1, .10), (.10, .16), (.16, .20), (.20, .30), (.30, .60), (.60, 1.2), (1.2, 2.5)]:
            m = (near[:, 2] >= a) & (near[:, 2] < b)
            bands.append(dict(z=[a, b], n=int(m.sum()), explained=int((m & expl).sum())))
        unexpl = near[~expl, 2]
        frames.append(dict(sid=f['sid'], index=f['index'], gt_zmin=float(f['box']['aabb_min'][2]),
                           lowest_unexplained_z_in_cyl=float(unexpl.min()) if len(unexpl) else None,
                           bands=bands))
    hf = gt['hardneg_frame']
    hp, _ = read_prepared(hf['sid'], frame_rec(man, hf['sid'], hf['index']))
    fixtures = []
    for k, s in enumerate(gt['hard_negative_structures']):
        c = np.asarray(s['centroid'])
        z = hp[np.hypot(hp[:, 0] - c[0], hp[:, 1] - c[1]) <= MATCH_M, 2]
        fixtures.append(dict(name=STRUCT_NAMES[k], gt_cluster_zmin=s['z_min'], gt_cluster_zmax=s['z_max'],
                             cyl_n=int(len(z)), cyl_zmax=float(z.max()), cyl_zmax_ge015=float(z[z >= .15].max())))
    return frames, fixtures


def person_inputs(gt):
    rows, zs, ints = [], [], []
    for f in gt['test_frames']:
        pts, _ = load_b(f['sid'], f['index'], FG, PRE)
        xy = np.asarray(f['box']['centroid_xy'])
        m = np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1]) <= MATCH_M
        z = pts[m, 2]
        zs.append(z - ZS)
        ints.append(pts[m, 3])
        rows.append(dict(sid=f['sid'], index=f['index'], n_cyl=int(m.sum()),
                         frac_model_z_ge_anchor_bottom=float(((z - ZS) >= -.6).mean()),
                         z_raw_p5_p50_p95=np.percentile(z, [5, 50, 95]).round(3).tolist(),
                         intensity_p50_raw=float(np.median(pts[m, 3]))))
    return rows, np.concatenate(zs), np.concatenate(ints)


def pillar_stats(f, arm, pts, ids, n_pre):
    tag = '%s_%d_%s' % (f['sid'][-6:], f['index'], arm)
    P = np.load(EVAL / (tag + '_pillars.npz'))
    coords, icnt, cnt, xyzi = P['coords'], P['input_counts'], P['counts'], P['selected_xyzi']
    sat = icnt > 32
    sel_z = np.concatenate([xyzi[j, :cnt[j], 2] for j in range(len(cnt))]) + ZS
    key_pts = np.floor(pts[:, 0] / .16).astype(int) * 10000 + np.floor((pts[:, 1] + 39.68) / .16).astype(int)
    key_pil = coords[:, 0].astype(int) * 10000 + coords[:, 1].astype(int)
    all_z = pts[np.isin(key_pts, key_pil), 2]
    xy = np.asarray(f['box']['centroid_xy'])
    cyl = np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1]) <= MATCH_M
    return dict(n_pillars=int(len(cnt)), n_saturated=int(sat.sum()), input_points=int(icnt.sum()),
                kept_points=int(cnt.sum()), kept_frac=float(cnt.sum() / icnt.sum()),
                frac_points_in_saturated=float(icnt[sat].sum() / icnt.sum()),
                sel_z_median=float(np.median(sel_z)), all_z_median=float(np.median(all_z)),
                sel_frac_z_ge_1p5=float((sel_z >= 1.5).mean()), all_frac_z_ge_1p5=float((all_z >= 1.5).mean()),
                sel_frac_z_lt_0p6=float((sel_z < .6).mean()), all_frac_z_lt_0p6=float((all_z < .6).mean()),
                sel_file_pos_median=float(np.median(P['selected_source_ids']) / n_pre),
                cyl_file_pos_median=float(np.median(ids[cyl]) / n_pre))


def density(xyz):
    ix = np.floor(xyz[:, 0] / .16).astype(int)
    iy = np.floor((xyz[:, 1] + 39.68) / .16).astype(int)
    m = (xyz[:, 0] >= 0) & (xyz[:, 0] < 69.12) & (xyz[:, 1] >= -39.68) & (xyz[:, 1] < 39.68) & \
        (xyz[:, 2] >= -3) & (xyz[:, 2] < 1)
    _, cnt = np.unique(ix[m] * 1000 + iy[m], return_counts=True)
    stats = dict(pillars=int(len(cnt)), median=float(np.median(cnt)), p90=float(np.percentile(cnt, 90)),
                 p99=float(np.percentile(cnt, 99)), max=int(cnt.max()), frac_pillars_gt32=float((cnt > 32).mean()),
                 frac_points_dropped_by_cap=float(np.maximum(cnt - 32, 0).sum() / cnt.sum()))
    return stats, cnt


def mode_of(z, lo, hi, step):
    h, e = np.histogram(z, bins=np.arange(lo, hi + step, step))
    return float(e[np.argmax(h)] + step / 2)


def plot_z(path, person_z, kitti_z):
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    bins = np.arange(-2.2, 1.21, .05)
    ax.hist(kitti_z, bins=bins, density=True, histtype='step', lw=1.6, color='#0072B2',
            label='KITTI 000134 全部点（原始 z）')
    ax.hist(person_z, bins=bins, density=True, histtype='step', lw=1.6, color='#D55E00',
            label='C1 人框柱内点（z−1.73，24 帧合并）')
    ax.axvspan(-.6, 1.13, color='#009E73', alpha=.12, label='零偏移行人 anchor 竖向跨度 [-0.6, 1.13]')
    ax.axvline(-1.73, c='k', ls='--', lw=1, label='假设地面 −1.73')
    ax.set(xlabel='模型 z (m)', ylabel='密度', title='模型坐标系 z 分布：人 vs KITTI 样例')
    ax.legend(fontsize=7)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_pillars(path, kitti_cnt, ours_cnt, person_cnt):
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    bins = np.logspace(0, 3.2, 40)
    for c, lab, col in [(kitti_cnt, 'KITTI 000134 占用柱', '#0072B2'),
                        (ours_cnt, 'C1 整帧 B 占用柱（24 帧合并）', '#999999'),
                        (person_cnt, 'C1 人体局部柱（base 臂，24 帧合并）', '#D55E00')]:
        ax.hist(c, bins=bins, density=True, histtype='step', lw=1.6, color=col, label=lab)
    ax.axvline(32, c='k', ls='--', lw=1, label='每柱上限 32')
    ax.set_xscale('log')
    ax.set(xlabel='每柱输入点数（log）', ylabel='密度', title='柱内点数分布：KITTI 与本场景')
    ax.legend(fontsize=7)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_hits(path, frames, traces, arm, tau):
    fig, axes = plt.subplots(4, 6, figsize=(20, 14), layout='constrained')
    for ax, f in zip(axes.ravel(), frames):
        pts = read_pre(PRE, f['sid'], f['index'])
        boxes = final_boxes(traces[(f['sid'], f['index'], arm)], tau)
        title = '%s #%d | %s τ=%.2f' % (f['sid'][-6:], f['index'], arm, tau)
        draw(ax, pts, boxes, f['box'], title, f['box']['centroid_xy'])
    fig.savefig(path, dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    gt = json.loads((DET / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    rows = [json.loads(l) for l in (EVAL / 'rows.jsonl').read_text(encoding='utf-8').splitlines()]
    by = {(r['sid'], r['index'], r['arm']): r for r in rows}
    traces = {k: dict(np.load(trace_path(r))) for k, r in by.items()}
    metrics = json.loads((EVAL / 'metrics.json').read_text(encoding='utf-8'))
    test = gt['test_frames']
    empty = gt['empty_frames']
    structs = [tuple(s['centroid'][:2]) for s in gt['hard_negative_structures']]
    res = dict(rows_check=check_rows(rows, by, traces), metrics_recount={}, operating={}, loso={},
               radius={}, fp_location={}, empty_fp={}, geometry={}, top100={}, pillar={})
    for arm in ARMS:
        table = sweep(test, traces, arm)
        mt = metrics['test'][arm]['table']
        worst = max(abs(table[str(t)][k] - mt[str(t)][k]) for t in TAUS
                    for k in ('recall_center', 'recall_iou', 'fp_per_frame'))
        res['metrics_recount'][arm] = dict(max_abs_diff_vs_metrics_json=float(worst), table=table)
        res['operating'][arm] = dict(recount=operating(table), metrics_json=metrics['test'][arm]['operating_points'])
        res['loso'][arm] = loso(test, traces, arm)
        res['radius'][arm] = {str(t): {str(r): float(hits(test, traces, arm, t, r)[0].mean()) for r in RADII}
                              for t in TAU_GRID}
        res['fp_location'][arm], res['empty_fp'][arm] = {}, {}
        for t in TAU_GRID:
            cnt_t, other_t = fp_locations(test, traces, arm, structs, t, True)
            cnt_e, other_e = fp_locations(empty, traces, arm, structs, t, False)
            res['fp_location'][arm][str(t)] = dict(per_test_frame=cnt_t, other_grid_0p5m=grid_counts(other_t))
            res['empty_fp'][arm][str(t)] = dict(per_empty_frame=cnt_e, other_grid_0p5m=grid_counts(other_e))
        geo = geometry(test, traces, arm)
        res['geometry'][arm] = dict(per_frame=geo, summary=dict(
            dx=med(geo, 'dx'), dy=med(geo, 'dy'), ex_minus_gt=med(geo, 'ex_minus_gt'),
            ey_minus_gt=med(geo, 'ey_minus_gt'), h_minus_gt=med(geo, 'h_minus_gt'),
            bottom_minus_gt=med(geo, 'bottom_minus_gt'), top_minus_gt=med(geo, 'top_minus_gt'), iou=med(geo, 'iou')))
        ptab, pops = pooled_ops(test, empty, traces, arm)
        res.setdefault('pooled_ops', {})[arm] = dict(operating=pops, table=ptab)
        res['top100'][arm] = dict(
            local_top100_count_median=float(np.median([by[(f['sid'], f['index'], arm)]['local_top100_count'] for f in test])),
            target_top100_removed_sum=int(sum(by[(f['sid'], f['index'], arm)]['target_top100_removed'] for f in test)))
        res['pillar'][arm] = []
    pre_man = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    for f in test:
        pts, ids = load_b(f['sid'], f['index'], FG, PRE)
        n_pre = frame_rec(pre_man, f['sid'], f['index'])['points']
        for arm in ARMS:
            res['pillar'][arm].append(dict(sid=f['sid'], index=f['index'], **pillar_stats(f, arm, pts, ids, n_pre)))
    res['anchor_field'] = dict(
        person=[anchor_field(traces, [(f['sid'], f['index'], arm) for arm in ARMS], f['box']['centroid_xy'])
                for f in test],
        fixture_A=anchor_field(traces, [(e['sid'], e['index'], arm) for e in empty for arm in ARMS],
                               gt['hard_negative_structures'][0]['centroid']))
    fixA = gt['hard_negative_structures'][0]['centroid']
    res['fixture_visibility'] = fixture_visibility(test, fixA)
    res['fixture_A_points_empty_frames'] = fixture_points(empty, fixA)
    res['label_z_explained_mask'], res['hard_negative_fixture_heights'] = label_checks(gt)
    res['user_confirmation_lines_with_hash_or_person'] = [
        ln.strip() for ln in gt['user_confirmation'].splitlines() if '#' in ln or '人' in ln]
    res['hardneg_json_note'] = json.loads(
        (DET / 'annotate_r4/hardneg_cap_20261008_114819_122.json').read_text(encoding='utf-8'))['note']
    pin, person_z, person_int = person_inputs(gt)
    res['person_inputs'] = pin
    res['person_inputs_pooled'] = dict(
        z_model_p5_p50_p95=np.percentile(person_z, [5, 50, 95]).round(3).tolist(),
        frac_model_z_ge_anchor_bottom_m06=float((person_z >= -.6).mean()),
        intensity_raw_p5_p50_p95=np.percentile(person_int, [5, 50, 95]).round(1).tolist(),
        intensity_div1023_p50=float(np.median(person_int) / 1023))
    kitti = np.fromfile(UP / '000134.bin', dtype='<f4').reshape(-1, 4)
    kd, kcnt = density(kitti[:, :3])
    ours_stats, ours_cnt, person_cnt = [], [], []
    for f in test:
        pts, _ = load_b(f['sid'], f['index'], FG, PRE)
        shifted = pts[:, :3].copy()
        shifted[:, 2] -= ZS
        st, cnt = density(shifted)
        ours_stats.append(st)
        ours_cnt.append(cnt)
        person_cnt.append(np.load(EVAL / ('%s_%d_base_pillars.npz' % (f['sid'][-6:], f['index'])))['input_counts'])
    res['density'] = dict(kitti=kd, ours_median_over_24_frames={k: float(np.median([s[k] for s in ours_stats]))
                                                              for k in ours_stats[0]})
    res['intensity_kitti_p5_p50_p95'] = np.percentile(kitti[:, 3], [5, 50, 95]).round(3).tolist()
    empty_pre = read_prepared('cap_20261008_114819', frame_rec(json.loads((PRE / 'manifest.json').read_text(
        encoding='utf-8')), 'cap_20261008_114819', 41))[0]
    res['ground_mode'] = dict(kitti_mode_z=mode_of(kitti[:, 2], -2.2, -1.2, .02),
                              ours_prepared_floor_mode_z=mode_of(empty_pre[:, 2], -.3, .3, .02),
                              note='KITTI z native; ours = prepared (leveled, before the -1.73 model shift)')
    (a.out / 'summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    plot_z(a.out / 'fig_z_model_frame.png', person_z, kitti[:, 2])
    plot_pillars(a.out / 'fig_pillar_counts.png', kcnt, np.concatenate(ours_cnt), np.concatenate(person_cnt))
    for arm in ARMS:
        plot_hits(a.out / ('fig_gt_vs_hits_%s_tau025.png' % arm), test, traces, arm, .25)
    a.evidence.mkdir(parents=True, exist_ok=True)
    (a.evidence / ('offline_pointer_%s.json' % a.out.name)).write_text(json.dumps(
        dict(out=str(a.out), summary_sha256=sha(a.out / 'summary.json')), indent=2), encoding='utf-8')
    print('DONE offline', a.out)


if __name__ == '__main__':
    main()
