"""DET-05: frozen labels_v1 -> pure-human pillar audit -> paired base/pure_switch forwards (20 total) with GT-relative metrics. No training, no device."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from shapely.geometry import Polygon

from cpu_pointpillars import Voxelization, limit_period, load_model
from diagnose_low_scores import (ROOT, UP, PRE, FG, SEED_FILE, SamplingProbe, containing,
                                 load_cloud, sha_bytes, trace_heads)
from det04 import OLD as OLD03, adapted, read_json, verify_pillars, write_json
from experiment import sha

NEW = ROOT.parents[1] / 'docs/sidequests/evidence/2026-10-08_det05_r1'
FROZEN = ROOT / 'artifacts/det05_r1/frozen'
ITEMS = [('cap_20261007_215540', 32, 'B_workspace'),
         ('cap_20261007_215607', 33, 'B_workspace'),
         ('cap_20261007_215623', 33, 'B_workspace'),
         ('cap_20261007_215643', 28, 'B_workspace'),
         ('cap_20261007_215643', 3, 'B_workspace'),
         ('cap_20261007_215643', 7, 'E_cleanup'),
         ('cap_20261007_215643', 11, 'E_cleanup'),
         ('cap_20261007_215643', 12, 'E_cleanup'),
         ('cap_20261007_215643', 17, 'E_cleanup'),
         ('cap_20261007_215643', 37, 'E_cleanup')]
COMP_SEP = .8


def my_groups(p, base):
    valid = np.isfinite(p).all(1) & ((p[:, :3] >= base.bounds[:3]) & (p[:, :3] < base.bounds[3:])).all(1)
    keys = np.floor((p[:, :3] - base.bounds[:3]) / base.size).astype('i4')
    groups = {}
    for i in np.flatnonzero(valid):
        groups.setdefault(tuple(keys[i]), []).append(i)
    return valid, groups


def classify_pillars(groups, ids, label_map):
    """Strict purity: every valid point in the pillar must be labeled human."""
    out = {}
    for key, members in groups.items():
        labels = [label_map.get(int(ids[i])) for i in members]
        has_none = any(l is None for l in labels)
        has_f = 'furniture' in labels
        has_m = 'mixed_uncertain' in labels
        pure = not (has_none or has_f or has_m)
        reason = 'pure' if pure else ('unlabeled' if has_none else ('furniture' if has_f else 'mixed_uncertain'))
        out[key] = dict(n=len(members), pure=pure, reason=reason, human=labels.count('human'),
                        furniture=labels.count('furniture'), mixed_uncertain=labels.count('mixed_uncertain'),
                        unlabeled=sum(l is None for l in labels))
    return out


class PureSwitchProbe(SamplingProbe):
    """z_rank32 sampling only in listed pure pillars; first32 elsewhere, nothing else changed."""

    def __init__(self, base, switch_keys):
        super().__init__(base)
        self.switch_keys = {tuple(k) for k in switch_keys}

    def forward(self, points):
        v, c, n = self.base(points)
        p = points.numpy()
        valid = np.isfinite(p).all(1) & ((p[:, :3] >= self.base.bounds[:3]) & (p[:, :3] < self.base.bounds[3:])).all(1)
        indices = np.flatnonzero(valid)
        c3 = np.floor((p[valid, :3] - self.base.bounds[:3]) / self.base.size).astype('i4')
        groups = {}
        for i, key in zip(indices, map(tuple, c3)):
            groups.setdefault(key, []).append(i)
        chosen = []
        full_counts = []
        switched = []
        for j, key in enumerate(map(tuple, c.numpy())):
            ids = np.asarray(groups[key])
            full_counts.append(len(ids))
            if key in self.switch_keys and len(ids) > self.base.max_points:
                ordered = ids[np.argsort(p[ids, 2], kind='stable')]
                ids = ordered[np.rint(np.linspace(0, len(ids) - 1, self.base.max_points)).astype(int)]
                v[j, :len(ids)] = torch.from_numpy(p[ids])
                switched.append(j)
            else:
                ids = ids[:self.base.max_points]
            chosen.extend(ids.tolist())
        self.selected = np.asarray(chosen, dtype='i8')
        self.last = (v.clone(), c.clone(), n.clone(), np.asarray(full_counts))
        self.switched = switched
        return v, c, n


def full_stats(path, model, xy):
    """Recompute trace_heads-style raw fields from stored full heads (independent path)."""
    with np.load(path) as data:
        cls = torch.from_numpy(data['cls_logits'])
        reg = torch.from_numpy(data['reg'])
        dlog = torch.from_numpy(data['dir_logits'])
    scores = cls.permute(1, 2, 0).reshape(-1, 3).sigmoid()
    deltas = reg.permute(1, 2, 0).reshape(-1, 7)
    dirs = dlog.permute(1, 2, 0).reshape(-1, 2).argmax(1)
    anchors = model.anchors_generator.get_multi_anchors(torch.tensor(list(cls.shape[-2:]))).reshape(-1, 7)
    decode = model.get_predicted_bboxes_single.__globals__['anchors2bboxes']
    boxes = decode(anchors, deltas)
    boxes[:, 6] = limit_period(boxes[:, 6], 1, np.pi) + (1 - dirs) * np.pi
    b = boxes.numpy()
    s = scores.numpy()
    local = ((anchors[:, :2] - torch.tensor(xy)) ** 2).sum(1).numpy() <= .55 ** 2
    hits = containing(b, xy)
    dist = np.hypot(anchors[:, 0].numpy() - xy[0], anchors[:, 1].numpy() - xy[1])
    j = int(np.argmin(dist))
    score_max = scores.max(1).values
    order = score_max.argsort(descending=True)
    rank = torch.empty_like(order)
    rank[order] = torch.arange(len(order))
    loc = np.flatnonzero(local)
    order2 = loc[np.argsort(-s[loc, 0], kind='stable')]
    pos = int(np.flatnonzero(order2 == j)[0]) + 1
    return dict(local_max=float(s[local, 0].max()),
                containing_max=float(s[hits, 0].max()) if hits.any() else 0.0,
                global_max=float(s[:, 0].max()), nearest_anchor_id=j,
                nearest_anchor_score=float(s[j, 0]), nearest_anchor_dist=float(dist[j]),
                rank_global=int(rank[j]) + 1, rank_local=pos)


def iou_rot_aabb(box, gt):
    c, s = np.cos(box[6]), np.sin(box[6])
    corners = np.array([[-box[3] / 2, -box[4] / 2], [box[3] / 2, -box[4] / 2],
                        [box[3] / 2, box[4] / 2], [-box[3] / 2, box[4] / 2]]) @ np.array([[c, -s], [s, c]]) + box[:2]
    rect = Polygon(corners)
    ax = Polygon([(gt['aabb_min'][0], gt['aabb_min'][1]), (gt['aabb_max'][0], gt['aabb_min'][1]),
                  (gt['aabb_max'][0], gt['aabb_max'][1]), (gt['aabb_min'][0], gt['aabb_max'][1])])
    if not rect.is_valid or not ax.is_valid or rect.area <= 0 or ax.area <= 0:
        return 0.0
    inter = rect.intersection(ax).area
    union = rect.union(ax).area
    return float(inter / union) if union > 0 else 0.0


def main(out, evidence):
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    labels_all = read_json(FROZEN / 'labels_v1.json')
    gt_all = read_json(FROZEN / 'gt_v1.json')
    freeze = read_json(FROZEN / 'freeze_manifest.json')
    freeze_files = {Path(f['path']).name: f['sha256'] for f in freeze['files']}
    assert len(labels_all['labels']) == 10 and len(gt_all['frames']) == 10
    seeds = {s['session']: s['xy_m'] for s in read_json(SEED_FILE)['sessions']}
    fg, pre = read_json(FG / 'manifest.json'), read_json(PRE / 'manifest.json')
    assert fg['input_manifest_sha256'] == sha(PRE / 'manifest.json')
    sessions = {s['sid']: s for s in fg['sessions']}
    raw = {s['sid']: s for s in pre['sessions']}
    base_spec = Voxelization([.16, .16, 4], [0, -39.68, -3, 69.12, 39.68, 1], 32, (16000, 40000))
    config = dict(script_sha256=sha(Path(__file__)), plan_sha256=sha(NEW.parents[1] / 'DET05_PLAN.md'),
                  acceptance_sha256=sha(NEW.parents[1] / 'DET05_ACCEPTANCE.md'),
                  shared_sha256={p.name: sha(p) for p in [ROOT / 'diagnose_low_scores.py', ROOT / 'cpu_pointpillars.py',
                                                          ROOT / 'det04.py', ROOT / 'det05_annotate.py', ROOT / 'det05_freeze.py']},
                  checkpoint_sha256=sha(UP / 'epoch_160.pth'),
                  source_hashes={str(p): sha(p) for p in [FG / 'manifest.json', PRE / 'manifest.json', SEED_FILE,
                                                          FROZEN / 'labels_v1.json', FROZEN / 'gt_v1.json',
                                                          FROZEN / 'freeze_manifest.json']},
                  items=[dict(sid=s, index=i, variant=v) for s, i, v in ITEMS], competitor_separation_m=COMP_SEP,
                  sampling='base=first32 everywhere; pure_switch=z_rank32 in pure pillars only, first32 elsewhere',
                  pure_rule='all valid points labeled human in frozen labels_v1', score=.1, nms=.01, top100=100,
                  max50=50, voxel=[.16, .16, 4], max_points=32, model_z=-1.73, intensity_divisor=1023,
                  new_forwards=20, physical=False, gt_version='v1', labels_version='v1')
    write_json(out / 'config.json', config)
    write_json(evidence / '02_config.json', config)

    # Phase 1: purity audit, no model loaded.
    audit, pure_by_item = [], {}
    for sid, index, variant in ITEMS:
        frame_key = '%s|%d' % (sid, index)
        cloud, ids = load_cloud(sessions[sid], sessions[sid]['frames'][index], variant, raw[sid])
        p = adapted(cloud)
        valid, groups = my_groups(p, base_spec)
        label_map = dict(zip(labels_all['labels'][frame_key]['prepared_rows'], labels_all['labels'][frame_key]['cls']))
        gt_xy = gt_all['frames'][frame_key]['centroid_xy']
        pillars = classify_pillars(groups, ids, label_map)
        pure_keys = [tuple(int(x) for x in key) for key, info in pillars.items() if info['pure']]
        switchable = [key for key in pure_keys if pillars[key]['n'] > base_spec.max_points]
        pure_by_item[(sid, index, variant)] = set(pure_keys)
        reasons = dict(pure=0, furniture=0, mixed_uncertain=0, unlabeled=0)
        for info in pillars.values():
            reasons[info['reason']] += 1
        local = []
        for key, info in pillars.items():
            center = (np.asarray(key[:2], dtype='f8') + .5) * base_spec.size[:2] + base_spec.bounds[:2]
            if np.hypot(center[0] - gt_xy[0], center[1] - gt_xy[1]) <= .7:
                local.append(dict(key=[int(v) for v in key], n=info['n'], pure=info['pure'], reason=info['reason'],
                                  human=info['human'], furniture=info['furniture'],
                                  mixed_uncertain=info['mixed_uncertain'], unlabeled=info['unlabeled']))
        audit.append(dict(sid=sid, index=index, variant=variant, input_sha256=sha_bytes(cloud), ids_sha256=sha_bytes(ids),
                          valid_points=int(valid.sum()), pillars=len(pillars), reasons=reasons,
                          pure=len(pure_keys), switchable_pure_over32=len(switchable), local_pillars=local))
        print('PURITY %s %d %s pillars=%d pure=%d switchable=%d' %
              (sid[-6:], index, variant, len(pillars), len(pure_keys), len(switchable)), flush=True)
    write_json(evidence / '04_purity_audit.json',
               dict(rows=audit, note='pure = all valid points human in labels_v1; reasons priority unlabeled>furniture>mixed_uncertain; '
                                     'switchable = pure with over 32 valid points; local table within 0.7m of frozen GT'))

    # Phase 2: paired forwards.
    model = load_model(UP / 'epoch_160.pth', UP)
    assert (model.score_thr, model.nms_thr, model.nms_pre, model.max_num) == (.1, .01, 100, 50)
    actual_base = model.pillar_layer.voxel_layer
    assert np.allclose(actual_base.bounds, base_spec.bounds) and np.allclose(actual_base.size, base_spec.size)
    assert actual_base.max_points == base_spec.max_points == 32
    archived = {}
    for line in (OLD03 / 'det03_all_r1_rows.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['experiment'] == 'base':
            archived[(row['sid'], row['index'], row['variant'])] = row
    runs = []
    with (out / 'rows.jsonl').open('x', encoding='utf-8') as log:
        for sid, index, variant in ITEMS:
            frame_key = '%s|%d' % (sid, index)
            cloud, ids = load_cloud(sessions[sid], sessions[sid]['frames'][index], variant, raw[sid])
            p = adapted(cloud)
            t = torch.from_numpy(p)
            gt = gt_all['frames'][frame_key]
            gt_xy = gt['centroid_xy']
            seed_xy = seeds[sid]
            pure_keys = pure_by_item[(sid, index, variant)]
            rec = raw[sid]['frames'][index]
            rows_path = PRE / sid / (rec['file'] + '.rows')
            assert sha(rows_path) == rec['rows_sha256']
            prep_rows = np.fromfile(rows_path, dtype='<i8')
            valid, groups = my_groups(p, actual_base)
            probe32 = SamplingProbe(actual_base)
            probe32.mode = 'first32'
            probe_sw = PureSwitchProbe(actual_base, pure_keys)
            v_base = None
            for mode, probe in (('base', probe32), ('pure_switch', probe_sw)):
                tag = '%s_%d_%s_%s' % (sid, index, variant, mode)
                model.pillar_layer.voxel_layer = probe
                captured = []
                hook = model.head.register_forward_hook(lambda m, i, o: captured.extend(x.detach() for x in o))
                start = time.perf_counter()
                try:
                    with torch.inference_mode():
                        model([t], mode='test')
                finally:
                    hook.remove()
                    model.pillar_layer.voxel_layer = actual_base
                seconds = time.perf_counter() - start
                with torch.inference_mode():
                    row = trace_heads(model, captured, gt_xy, out / (tag + '_trace.npz'), True)
                v, c, n, full_counts = probe.last
                assert len(c) == len(groups)
                if mode == 'base':
                    changed = []
                    v_base = v
                    arch = archived[(sid, index, variant)]
                    verify_pillars(arch, dict(c=c.numpy(), n=n.numpy(), total=full_counts, v=v.numpy()), actual_base, seed_xy)
                    fs_seed = full_stats(out / (tag + '_trace.npz'), model, seed_xy)
                    exact = (fs_seed['local_max'] == arch['local_anchor_max'] and
                             fs_seed['containing_max'] == arch['raw_containing_max'] and
                             fs_seed['global_max'] == arch['global_raw_ped_max'])
                    ok = (np.isclose(fs_seed['local_max'], arch['local_anchor_max'], atol=1e-5) and
                          np.isclose(fs_seed['containing_max'], arch['raw_containing_max'], atol=1e-5) and
                          np.isclose(fs_seed['global_max'], arch['global_raw_ped_max'], atol=1e-5))
                    assert ok, (fs_seed, arch['local_anchor_max'], arch['raw_containing_max'], arch['global_raw_ped_max'])
                    seed_check = dict(exact=bool(exact), local=fs_seed['local_max'], containing=fs_seed['containing_max'],
                                      global_=fs_seed['global_max'], archived_local=arch['local_anchor_max'],
                                      archived_containing=arch['raw_containing_max'], archived_global=arch['global_raw_ped_max'])
                else:
                    changed = [j for j in range(len(v)) if not torch.equal(v[j], v_base[j])]
                    changed_keys = {tuple(int(x) for x in c.numpy()[j]) for j in changed}
                    assert changed_keys <= pure_keys, 'switch changed a non-pure pillar'
                    assert set(changed) <= set(probe.switched)
                    seed_check = None
                fs = full_stats(out / (tag + '_trace.npz'), model, gt_xy)
                assert np.isclose(fs['local_max'], row['local_anchor_max'], atol=1e-7)
                assert np.isclose(fs['containing_max'], row['raw_containing_max'], atol=1e-7)
                dets = [d for d in row['stages']['clockwise']['detections'] if d['label'] == 0]
                boxes = np.array([d['box'] for d in dets], dtype='f8') if dets else np.zeros((0, 7))
                contains = containing(boxes, gt_xy) if dets else np.zeros(0, dtype=bool)
                gt_final = max([d['score'] for d, hit in zip(dets, contains) if hit], default=0.0)
                dist = np.hypot(boxes[:, 0] - gt_xy[0], boxes[:, 1] - gt_xy[1]) if dets else np.zeros(0)
                comp_idx = np.flatnonzero(dist >= COMP_SEP) if dets else np.zeros(0, dtype='i8')
                competitor = None
                if len(comp_idx):
                    k = int(comp_idx[int(np.argmin(dist[comp_idx]))])
                    competitor = dict(score=float(dets[k]['score']), distance=float(dist[k]), anchor_id=int(dets[k]['anchor_id']))
                iou_max = 0.0
                for d in dets:
                    iou_max = max(iou_max, iou_rot_aabb(d['box'], gt))
                pure_mask = np.array([tuple(int(x) for x in k) in pure_keys for k in c.numpy()], dtype=bool)
                switched_mask = np.zeros(len(v), dtype=bool)
                switched_mask[changed] = True
                np.savez_compressed(out / (tag + '_pillars.npz'), coords=c.numpy(), counts=n.numpy(),
                                    input_counts=full_counts, voxels=v.numpy(), selected=probe.selected,
                                    prepared_ids=ids[probe.selected], raw_rows=prep_rows[ids[probe.selected]],
                                    pure=pure_mask, switched=switched_mask)
                row.update(sid=sid, index=index, variant=variant, experiment=mode, seconds=seconds,
                           input_sha256=sha_bytes(cloud), adapted_sha256=sha_bytes(p), ids_sha256=sha_bytes(ids),
                           cloud_points=len(cloud), valid_points=int(valid.sum()), pillars=len(c),
                           pure_pillars=int(pure_mask.sum()),
                           switchable_pillars=int(sum(1 for k in pure_keys if len(groups[k]) > actual_base.max_points)),
                           changed_pillars=len(changed), switched_pillars=len(getattr(probe, 'switched', [])),
                           gt_local_raw=fs['local_max'], gt_decoded_raw=fs['containing_max'], gt_final=float(gt_final),
                           gt_anchor_id=fs['nearest_anchor_id'], gt_anchor_score=fs['nearest_anchor_score'],
                           gt_anchor_dist=fs['nearest_anchor_dist'], gt_rank_global=fs['rank_global'],
                           gt_rank_local=fs['rank_local'], n_ped_final=len(dets), box_contains_gt=bool(contains.any()),
                           gt_iou_max=float(iou_max),
                           competitor_score=None if competitor is None else competitor['score'],
                           competitor_distance=None if competitor is None else competitor['distance'],
                           competitor_anchor_id=None if competitor is None else competitor['anchor_id'],
                           margin_final=None if competitor is None else float(gt_final - competitor['score']),
                           seed_consistency=seed_check,
                           pillars_sha256=sha(out / (tag + '_pillars.npz')),
                           labels_sha256=freeze_files['labels_v1.json'], gt_sha256=freeze_files['gt_v1.json'])
                runs.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
                log.flush()
                print('RUN %s local=%.4f final=%.4f comp=%s changed=%d' %
                      (tag, row['gt_local_raw'], row['gt_final'],
                       'None' if competitor is None else '%.4f' % competitor['score'], len(changed)), flush=True)
    assert len(runs) == 20
    write_json(out / 'rows.json', runs)
    write_json(evidence / '05_run_rows.json', runs)
    with (evidence / '05_run_rows.jsonl').open('x', encoding='utf-8') as f:
        for row in runs:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

    metric_names = ['gt_local_raw', 'gt_decoded_raw', 'gt_final', 'gt_rank_global', 'gt_rank_local',
                    'competitor_score', 'competitor_distance', 'margin_final', 'box_contains_gt', 'gt_iou_max',
                    'pure_pillars', 'switchable_pillars', 'changed_pillars']
    comparisons = []
    for sid, index, variant in ITEMS:
        b = next(r for r in runs if (r['sid'], r['index'], r['variant'], r['experiment']) == (sid, index, variant, 'base'))
        s = next(r for r in runs if (r['sid'], r['index'], r['variant'], r['experiment']) == (sid, index, variant, 'pure_switch'))
        delta = {}
        for k in metric_names:
            if isinstance(b[k], bool) or b[k] is None or s[k] is None:
                delta[k] = None
            else:
                delta[k] = float(s[k] - b[k])
        comparisons.append(dict(sid=sid, index=index, variant=variant, base={k: b[k] for k in metric_names},
                                switch={k: s[k] for k in metric_names}, delta=delta))
    write_json(evidence / '06_metrics.json',
               dict(items=comparisons, new_forwards=20, seed_consistency=[r['seed_consistency'] for r in runs if r['experiment'] == 'base'],
                    note='GT-relative metrics from frozen gt_v1; competitor = nearest final pedestrian box with center at least 0.8m from GT; '
                         'no global-max or cross-frame-median substitutes; descriptive only, no P/R'))
    attribution = []
    for row in comparisons:
        attribution.append(dict(sid=row['sid'], index=row['index'], variant=row['variant'],
                                changed_pillars=row['switch']['changed_pillars'], switchable=row['switch']['switchable_pillars'],
                                delta_local=row['delta']['gt_local_raw'], delta_final=row['delta']['gt_final'],
                                delta_margin=row['delta']['margin_final'], delta_rank_global=row['delta']['gt_rank_global'],
                                scope='Single same-person frame; frozen periphery; descriptive only, no causal or accuracy claim'))
    write_json(evidence / '07_attribution.json',
               dict(rows=attribution, new_forwards=20,
                    note='pure-pillar-only sampling switch vs base; all other pillars value-frozen; no threshold tuning; '
                         'execution PASS is not recognition usability'))
    print('DONE: 10 items x 2 runs = 20 forwards; purity audit and GT metrics written', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    main(args.out.resolve(), args.evidence.resolve())
