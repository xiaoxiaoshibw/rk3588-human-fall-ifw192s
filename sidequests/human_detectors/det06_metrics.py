"""DET-06 metrics: test PR / empty FP / hardneg / anchor aux from eval traces. Offline, no model."""
import json
from pathlib import Path

import numpy as np
import torch

from det05 import iou_rot_aabb
from experiment import sha
from upstream_kernel_check import fixed_nms

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
DET = ROOT / 'artifacts/det06_r1'
EVAL = DET / 'eval'
EV = WORK / 'docs/sidequests/evidence/2026-10-08_det06_r1'
GT_PATH = DET / 'frozen/gt_eval_v1.json'
TAUS = [round(.10 + .05 * i, 2) for i in range(17)]
MATCH_M, COMP_SEP = .55, .8


def trace_path(row):
    p = Path(row['trace'])
    return p if p.is_absolute() else WORK / p


def final_boxes(tr, tau, nms_thr=.01, max50=50):
    aid = tr['anchor_ids']
    pos = {int(a): i for i, a in enumerate(aid)}
    top = [int(a) for a in tr['top100']]
    idx = [pos[a] for a in top if a in pos]
    if not idx:
        return np.zeros((0, 8))
    s = tr['raw_cls_scores'][idx, 0].astype('f8')
    b = tr['decoded_boxes'][idx].astype('f8')
    sel = np.flatnonzero(s > tau)
    if not len(sel):
        return np.zeros((0, 8))
    bb, ss = b[sel], s[sel]
    bev = torch.cat([torch.from_numpy(bb[:, :2] - bb[:, 3:5] / 2).float(),
                     torch.from_numpy(bb[:, :2] + bb[:, 3:5] / 2).float(),
                     torch.from_numpy(bb[:, 6:7]).float()], 1)
    k = np.asarray(fixed_nms(bev, torch.from_numpy(ss).float(), nms_thr))
    keep = sel[k]
    keep = keep[np.argsort(-s[keep])[:max50]]
    out = np.zeros((len(keep), 8))
    out[:, :7], out[:, 7] = b[keep], s[keep]
    return out


def frame_stats(boxes, xy, gt_box):
    if not len(boxes):
        return dict(tp=0, fp=0, iou_max=0.0)
    d = np.hypot(boxes[:, 0] - xy[0], boxes[:, 1] - xy[1])
    inside = d <= MATCH_M
    iou_max = 0.0
    if gt_box is not None:
        for r in boxes:
            iou_max = max(iou_max, iou_rot_aabb(r[:7], gt_box))
    return dict(tp=1 if inside.any() else 0, fp=int((~inside).sum()), iou_max=float(iou_max))


def sweep_arm(gt, rows_by, arm):
    curves = {t: dict(tp=0, fp=0, iou_tp=0) for t in TAUS}
    per_frame = []
    for f in gt['test_frames']:
        row = rows_by[(f['sid'], f['index'], arm)]
        tr = dict(np.load(trace_path(row)))
        xy = f['box']['centroid_xy']
        gt_box = {'aabb_min': f['box']['aabb_min'], 'aabb_max': f['box']['aabb_max']}
        item = dict(sid=f['sid'], index=f['index'])
        for t in TAUS:
            st = frame_stats(final_boxes(tr, t), xy, gt_box)
            curves[t]['tp'] += st['tp']
            curves[t]['fp'] += st['fp']
            curves[t]['iou_tp'] += 1 if st['iou_max'] >= .5 else 0
            if t == .10:
                item.update(iou_max=st['iou_max'], fp_010=st['fp'], tp_010=st['tp'])
        per_frame.append(item)
    n = len(gt['test_frames'])
    table = {t: dict(recall_center=c['tp'] / n, recall_iou=c['iou_tp'] / n, fp_per_frame=c['fp'] / n)
             for t, c in curves.items()}
    ops = {}
    for budget in (.1, .5, 1.0):
        elig = [(t, v) for t, v in table.items() if v['fp_per_frame'] <= budget]
        if not elig:
            ops[str(budget)] = None
            continue
        t, v = max(elig, key=lambda kv: (kv[1]['recall_center'], -kv[1]['fp_per_frame']))
        ops[str(budget)] = dict(tau=t, recall_center=v['recall_center'], recall_iou=v['recall_iou'],
                                fp_per_frame=v['fp_per_frame'])
    return dict(table=table, operating_points=ops, per_frame=per_frame)


def aux_arm(gt, rows_by):
    out = []
    for f in gt['test_frames']:
        row = rows_by[(f['sid'], f['index'], 'base')]
        tr = dict(np.load(trace_path(row)))
        xy = np.asarray(f['box']['centroid_xy'], dtype='f8')
        d = np.hypot(tr['anchors'][:, 0] - xy[0], tr['anchors'][:, 1] - xy[1])
        j = int(np.argmin(d))
        boxes = final_boxes(tr, .10)
        dists = np.hypot(boxes[:, 0] - xy[0], boxes[:, 1] - xy[1]) if len(boxes) else np.zeros(0)
        gt_final = max([float(b[7]) for b, dd in zip(boxes, dists) if dd <= MATCH_M], default=0.0)
        comp = [(float(b[7]), float(dd)) for b, dd in zip(boxes, dists) if dd >= COMP_SEP]
        comp_best = min(comp, key=lambda t: t[1]) if comp else None
        out.append(dict(sid=f['sid'], index=f['index'],
                        nearest_anchor_score=float(tr['raw_cls_scores'][j, 0]),
                        nearest_anchor_dist=float(d[j]), nearest_anchor_rank=int(tr['rank'][j]) + 1,
                        final_gt_score=gt_float(gt_final),
                        competitor_score=(comp_best[0] if comp_best else None),
                        competitor_dist=(comp_best[1] if comp_best else None),
                        margin=gt_float(gt_final - (comp_best[0] if comp_best else 0.0))))
    return out


def gt_float(v):
    return round(float(v), 6)


def empty_analysis(gt, rows_by):
    frames, boxes_all = [], []
    for f in gt['empty_frames']:
        row = rows_by[(f['sid'], f['index'], 'base')]
        tr = dict(np.load(trace_path(row)))
        boxes = final_boxes(tr, .10)
        ped = [b for b in boxes if b[7] >= .10]
        top = sorted([dict(score=float(b[7]), x=round(float(b[0]), 3), y=round(float(b[1]), 3)) for b in ped],
                     key=lambda d: -d['score'])[:3]
        for b in ped:
            boxes_all.append((f['sid'], f['index'], b))
        frames.append(dict(sid=f['sid'], index=f['index'], global_raw_ped_max=gt_float(row['global_raw_ped_max']),
                           final_global_ped_max=gt_float(row['stages']['clockwise']['final_global_ped_max']),
                           n_boxes=len(ped), top=top))
    hard = []
    for s in gt['hard_negative_structures']:
        mn, mx = s['aabb_min'], s['aabb_max']
        cand = [(float(b[7]), sid, i) for sid, i, b in boxes_all
                if mn[0] - .05 <= b[0] <= mx[0] + .05 and mn[1] - .05 <= b[1] <= mx[1] + .05]
        cand.sort(key=lambda t: -t[0])
        hard.append(dict(centroid=s['centroid'], aabb=[mn, mx],
                         max_score=cand[0][0] if cand else 0.0,
                         at=([cand[0][1][-6:], cand[0][2]] if cand else None)))
    return frames, hard


def main():
    gt = json.loads(GT_PATH.read_text(encoding='utf-8'))
    rows = [json.loads(l) for l in (EVAL / 'rows.jsonl').read_text(encoding='utf-8').splitlines()]
    rows_by = {(r['sid'], r['index'], r['arm']): r for r in rows}
    result = dict(gt_sha256=sha(GT_PATH), eval_config_sha256=sha(EVAL / 'config.json'),
                  note='center<=0.55m primary; BEV IoU>=0.5 aux; per-frame FP counted on final pedestrian boxes; '
                       'empty FP independent of GT; descriptive, no p-values')
    result['test'] = {arm: sweep_arm(gt, rows_by, arm) for arm in ('base', 'zrank')}
    frames, hard = empty_analysis(gt, rows_by)
    result['empty'] = dict(frames=frames, hard_negative=hard)
    result['aux_base'] = aux_arm(gt, rows_by)
    result['reproduction'] = json.loads((EVAL / 'reproduction.json').read_text(encoding='utf-8'))
    (EVAL / 'metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with (EV / '05_metrics.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    for arm in ('base', 'zrank'):
        ops = result['test'][arm]['operating_points']
        print(arm, {k: (None if v is None else (v['tau'], round(v['recall_center'], 3), round(v['fp_per_frame'], 3)))
                    for k, v in ops.items()})
    print('empty max final ped:', max(f['final_global_ped_max'] for f in frames))
    print('hardneg scores:', [(h['centroid'][0], h['max_score']) for h in hard])
    print('DONE metrics')


if __name__ == '__main__':
    main()
