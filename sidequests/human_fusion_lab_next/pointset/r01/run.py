"""Offline nine-session comparison; GT is consumed only after unsupervised inference."""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import yaml
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

from core import R, T, PARTS, cluster, decode_indices, describe, independence, roi_mask, sample_points, skeleton, valid_raw, voxelize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = ROOT / 'docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1'
LAB = ROOT / 'sidequests/human_fusion_lab'
OUT = HERE / 'output'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def dump(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')


def load(rec):
    folder = ROOT / 'captures/remote' / rec['sid']
    hashes = {n: sha(folder / file) for n, file in [('meta', 'meta.json'), ('points', 'points.bin')]}
    if hashes != rec['input_sha256']:
        raise ValueError('Frozen input drift: '+rec['sid'])
    meta = json.loads((folder/'meta.json').read_text(encoding='utf-8'))
    if meta.get('leveling') or meta['point_stride_bytes'] != 28 or meta['point_layout']['fields'] != ['x', 'y', 'z', 'intensity', 'ring', 'timestamp']:
        raise ValueError('Unexpected point contract')
    if (folder/'points.bin').stat().st_size != meta['total_points']*28:
        raise ValueError('Truncated source')
    raw = np.memmap(folder/'points.bin', dtype='u1', mode='r')
    xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
    intensity = np.ndarray(meta['total_points'], dtype='<f4', buffer=raw, offset=12, strides=(28,))
    end = 0
    stamps = []
    for f in meta['frames']:
        if f['offset_points'] != end or f['count_points'] < 0:
            raise ValueError('Noncontiguous point frames')
        end += f['count_points']
        stamps.append(f['stamp_sec']+f['stamp_nanosec']*1e-9)
    if end != meta['total_points'] or not np.isfinite(stamps).all() or np.any(np.diff(stamps) <= 0):
        raise ValueError('Invalid source frames/time')
    return meta, xyz, intensity, hashes


def frame(xyz, f):
    return xyz[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')


def valid_domain(p, cfg):
    radius = np.linalg.norm(p, axis=1)
    lv = p @ R.T + T
    keep = valid_raw(p) & (radius > cfg['range_min_m']) & (radius < cfg['range_max_m'])
    keep &= (lv[:, 2] >= cfg['z_min_m']) & (lv[:, 2] <= cfg['z_max_m'])
    return lv, keep


def background(rec, cfg):
    meta, raw, _, hashes = load(rec)
    bank = {}
    fit = list(range(0, len(meta['frames']), 3))
    calibration = list(range(1, len(meta['frames']), 3))
    holdout = list(range(2, len(meta['frames']), 3))
    for fi in fit:
        lv, mask = valid_domain(frame(raw, meta['frames'][fi]), cfg)
        keys, centers, _, _ = voxelize(lv[mask], cfg['voxel_m'])
        for k, p in zip(keys, centers):
            key = tuple(k)
            if key not in bank:
                bank[key] = [np.zeros(3), 0]
            bank[key][0] += p
            bank[key][1] += 1
    static = np.array([a/n for a, n in bank.values() if n >= np.ceil(len(fit)*cfg['background_min_frame_fraction'])])
    if not len(static):
        raise ValueError('Empty frozen background')
    tree = cKDTree(static)
    distances = []
    for fi in calibration:
        lv, mask = valid_domain(frame(raw, meta['frames'][fi]), cfg)
        distances.append(tree.query(lv[mask], k=1)[0])
    distances = np.concatenate(distances)
    measured = float(np.quantile(distances, cfg['background_calibration_quantile']))
    tolerance = min(cfg['background_tolerance_cap_m'], measured + cfg['voxel_m']/2)
    report = {'source_session': rec['sid'], 'source_sha': hashes, 'fit': fit, 'calibration': calibration, 'holdout': holdout,
              'static_voxels': len(static), 'calibration_distance_quantile_m': measured,
              'tolerance_m': tolerance, 'cap_reached': measured+cfg['voxel_m']/2 > cfg['background_tolerance_cap_m'],
              'never_updated_from_person_sessions': True, 'ground_rule': '3D measured-background match only; no height deletion'}
    np.savez_compressed(OUT/'background.npz', xyz=static, R=R, T=T)
    dump(OUT/'background.json', report)
    return tree, tolerance, report


def gt_document(rec, hashes):
    path = Path(rec['gt_path'])
    doc = json.loads(path.read_text(encoding='utf-8'))
    valid = rec['eligible'] and sha(path) == rec['gt_sha256'] and doc['session_id'] == rec['sid']
    valid &= doc.get('review_status') == 'reviewed' and doc.get('session_sha256') == hashes
    return doc if valid else None


def objects(doc, fi, raw):
    if doc is None or str(fi) not in doc['frames_objects'] or any(w['start'] <= fi <= w['end'] for w in doc.get('uncertain_intervals', [])):
        return None
    obs = [doc['objects'][i] for i in doc['frames_objects'][str(fi)]]
    if not obs or any(o['class_name'] == 'UNKNOWN' for o in obs):
        return None
    valid_ids = np.flatnonzero(valid_raw(raw))
    result, seen = [], set()
    for o in obs:
        ids = decode_indices(o['raw_point_indices'])
        if len(ids) and ids.max() >= len(valid_ids):
            raise ValueError('Compact GT indices out of bound')
        mapped = valid_ids[ids]
        key = (o['class_name'], tuple(mapped))
        if key in seen:
            continue
        seen.add(key)
        result.append({'id': o['object_id'], 'class_name': o['class_name'], 'source': o.get('source'),
                       'track_id': o.get('track_id'), 'ids': mapped})
    return result


def overlap(ids, obs):
    return [{'id': o['id'], 'class_name': o['class_name'], 'intersection': int(len(np.intersect1d(ids, o['ids']))),
             'reference_point_count': len(o['ids'])} for o in obs or []]


def bind_display(points, ids, cfg):
    count = min(len(ids), cfg['display_sample_points'])
    ix = np.floor(np.arange(count)*len(ids)/count).astype(int) if count else np.empty(0, int)
    return {'points': np.round(points[ix], 4).tolist(), 'display_source_indices': ids[ix].tolist(),
            'source_indices': ids.tolist(), 'point_count': len(ids),
            'bbox': {'min': points.min(axis=0).tolist(), 'max': points.max(axis=0).tolist()},
            'skeleton': skeleton(points, ids, cfg)}


def candidate_set(lv, ids, bg_dist, tree, tolerance, cfg, dims, model):
    p = lv[ids]
    groups, _ = cluster(p, cfg, dims)
    results = []
    if groups:
        inputs = np.stack([sample_points(p[g]).T for g in groups])
        logits = model.run(['logit'], {'points': inputs})[0].reshape(-1)
        probs = 1/(1+np.exp(-np.clip(logits, -60, 60)))
    for i, g in enumerate(groups):
        members = ids[g]
        other_ids = np.concatenate([a for j, a in enumerate(groups) if j != i]) if len(groups) > 1 else np.empty(0, int)
        quality = independence(p[g], bg_dist[members], p[other_ids], tolerance, cfg)
        results.append({'id': f'{dims}d-c{i}', 'kind': 'AUTOMATIC_CANDIDATE', 'dimensions': dims,
                        **bind_display(p[g], members, cfg), 'features_xyz': describe(p[g]),
                        'roi_point_fraction': float(np.mean(roi_mask(p[g], cfg['roi_xy']))),
                        'independence': quality, 'pointnet_prob': float(probs[i]),
                        'human_decision': 'MODEL_CANDIDATE' if probs[i] >= cfg['model_probability_threshold'] else 'UNKNOWN'})
    return results


def evaluate_groups(groups, obs, foreground_ids):
    if obs is None:
        return {'status': 'UNKNOWN_NO_QUALIFIED_REFERENCE', 'persons': []}
    persons = []
    for o in obs:
        if o['class_name'] != 'PERSON' or not len(o['ids']):
            continue
        hits = [int(len(np.intersect1d(c['source_indices'], o['ids']))) for c in groups]
        best = int(np.argmax(hits)) if hits and max(hits) else None
        c = groups[best] if best is not None else None
        h = max(hits, default=0)
        furniture = sum(x['intersection'] for x in (c or {}).get('reference_overlap', []) if x['class_name'] == 'FURNITURE')
        other_person = sum(x['intersection'] for x in (c or {}).get('reference_overlap', []) if x['class_name'] == 'PERSON' and x['id'] != o['id'])
        unassigned = (c['point_count']-sum(x['intersection'] for x in c['reference_overlap'])) if c else None
        persons.append({'reference_id': o['id'], 'reference_count': len(o['ids']),
                        'fg_kept': int(len(np.intersect1d(foreground_ids, o['ids']))), 'best_cluster': None if c is None else c['id'],
                        'best_cluster_point_count': c['point_count'] if c else 0, 'intersection': h,
                        'reference_coverage': h/len(o['ids']), 'annotated_person_overlap_fraction': h/c['point_count'] if c else None,
                        'furniture_points': furniture, 'other_person_points': other_person, 'unannotated_points': unassigned,
                        'fragments_with_reference_points': sum(v > 0 for v in hits),
                        'pure_human_status': 'NOT_EVALUATED_WITH_NONEXHAUSTIVE_REFERENCE'})
    return {'status': 'BOUND_EXISTING_REFERENCE_NOT_INDEPENDENT_NEW_TRUTH', 'persons': persons}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--session')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    cfg = yaml.safe_load((HERE/'config.yaml').read_text(encoding='utf-8'))
    audit = json.loads((LAB/'results/AUDIT.json').read_text(encoding='utf-8'))
    frozen = LAB/'models/pointnet_shadow.onnx'
    assets = {str(p): sha(p) for p in [frozen, LAB/'results/AUDIT.json', LAB/'core/leveling.js']}
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    model = ort.InferenceSession(str(frozen), sess_options=options, providers=['CPUExecutionProvider'])
    tree, tolerance, bg = background(next(r for r in audit['sessions'] if r['sid'] == cfg['background_session']), cfg)
    catalog = []
    training = []
    all_candidates = []
    for rec in audit['sessions']:
        if args.session and rec['sid'] != args.session:
            continue
        started = time.perf_counter()
        meta, raw, intensity, hashes = load(rec)
        doc = gt_document(rec, hashes)
        summary = {'session_id': rec['sid'], 'activity': rec['activity'], 'frame_count': len(meta['frames']),
                   'duration_sec': meta['duration_sec'], 'source_sha256': hashes,
                   'reference_status': 'BOUND_EXISTING_REVIEWED_LABELS' if doc else 'BLOCKED_INVALID_BINDING',
                   'reference_gt_level': doc.get('gt_level') if doc else None,
                   'scope_note': 'Action is recording description, not per-frame action truth', 'frames': []}
        t0 = meta['frames'][0]['stamp_sec']+meta['frames'][0]['stamp_nanosec']*1e-9
        reference_chunks, reference_ids, reference_frames, reference_intensity = [], [], [], []
        for fi, f in enumerate(meta['frames']):
            if args.max_frames and fi >= args.max_frames:
                break
            p = frame(raw, f)
            lv, domain = valid_domain(p, cfg)
            distance = np.full(len(p), np.inf)
            distance[domain] = tree.query(lv[domain], k=1)[0]
            foreground = np.flatnonzero(domain & (distance > tolerance))
            in_roi = roi_mask(lv, cfg['roi_xy']) & domain
            foreground_roi = foreground[in_roi[foreground]]
            # Complete all automatic inference before GT decoding/evaluation.
            full = candidate_set(lv, foreground, distance, tree, tolerance, cfg, 3, model)
            roi = candidate_set(lv, foreground_roi, distance, tree, tolerance, cfg, 3, model)
            baseline_2d = candidate_set(lv, foreground, distance, tree, tolerance, cfg, 2, model)
            obs = objects(doc, fi, p)
            references = []
            for o in obs or []:
                if not len(o['ids']):
                    continue
                features = describe(lv[o['ids']])
                if o['class_name'] in ['PERSON', 'FURNITURE'] and fi % 4 == 0:
                    training.append({'sid': rec['sid'], 'fi': fi, 'features': features,
                                     'label': int(o['class_name'] == 'PERSON'), 'object_id': o['id']})
                if o['class_name'] == 'PERSON':
                    references.append({'id': o['id'], 'track_id': o['track_id'], 'kind': 'EXISTING_MANUAL_REFERENCE',
                                       **bind_display(lv[o['ids']], o['ids'], cfg),
                                       'roi_point_fraction': float(np.mean(in_roi[o['ids']])), 'body_parts': 'UNKNOWN_UNANNOTATED'})
                    reference_chunks.append(lv[o['ids']].astype('f4'))
                    reference_ids.append(o['ids'].astype('u4'))
                    reference_frames.append(np.full(len(o['ids']), fi, dtype='u4'))
                    reference_intensity.append(intensity[f['offset_points']+o['ids']])
            for scope, groups in [('full_3d', full), ('roi_3d', roi), ('full_2d', baseline_2d)]:
                for c in groups:
                    c['reference_overlap'] = overlap(np.asarray(c['source_indices']), obs)
                    person = [x for x in c['reference_overlap'] if x['class_name'] == 'PERSON' and x['intersection'] > 0]
                    furn = sum(x['intersection'] for x in c['reference_overlap'] if x['class_name'] == 'FURNITURE')
                    label = 1 if len(person) == 1 and person[0]['intersection']/c['point_count'] >= .8 and furn/c['point_count'] <= .2 else None
                    if obs and not person and furn/c['point_count'] >= .8:
                        label = 0
                    all_candidates.append({'sid': rec['sid'], 'fi': fi, 'scope': scope, 'id': c['id'],
                                           'features': c['features_xyz'], 'label': label, 'pointnet_prob': c['pointnet_prob']})
            fg_sample = foreground[np.floor(np.arange(min(1800, len(foreground)))*len(foreground)/min(1800, len(foreground))).astype(int)] if len(foreground) else []
            row = {'schema_version': cfg['schema_version'], 'session_id': rec['sid'], 'frame_index': fi,
                   'source_frame': {k: f[k] for k in ['offset_points', 'count_points', 'seq', 'stamp_sec', 'stamp_nanosec']},
                   't_sec': f['stamp_sec']+f['stamp_nanosec']*1e-9-t0, 'coordinate_frame': 'leveled-IFW192S', 'units': 'm',
                   'background_split': ('FIT' if fi in bg['fit'] else 'CALIBRATION' if fi in bg['calibration'] else 'HOLDOUT') if rec['sid'] == cfg['background_session'] else 'EXTERNAL_SESSION',
                   'roi_status': cfg['roi_status'], 'action_label': {'name': rec['activity'], 'provenance': 'SESSION_DESCRIPTION', 'per_frame_reviewed': False},
                   'raw_count': len(p), 'valid_domain_count': int(domain.sum()), 'background_removed': int(np.sum(domain & (distance <= tolerance))),
                   'fg_count': len(foreground), 'roi_fg_count': len(foreground_roi), 'reference': references,
                   'full_3d': full, 'roi_3d': roi, 'full_2d': baseline_2d,
                   'foreground_display': np.round(lv[fg_sample], 4).tolist(),
                   'metrics': {scope: evaluate_groups(groups, obs, foreground if scope != 'roi_3d' else foreground_roi)
                               for scope, groups in [('full_3d', full), ('roi_3d', roi), ('full_2d', baseline_2d)]}}
            dump(OUT/rec['sid']/f'{fi:04d}.json', row)
            summary['frames'].append({'fi': fi, 't': row['t_sec'], 'fg': len(foreground), 'roi_fg': len(foreground_roi),
                                      'full_clusters': len(full), 'roi_clusters': len(roi), 'reference_persons': len(references),
                                      'metrics': row['metrics']})
            if fi % 100 == 0:
                print(rec['activity'], fi, '/', len(meta['frames']), 'fg', len(foreground), '3d clusters', len(full), flush=True)
        summary['elapsed_sec'] = time.perf_counter()-started
        if reference_chunks:
            np.savez_compressed(OUT/rec['sid']/'human_reference.npz', xyz=np.concatenate(reference_chunks),
                                source_indices=np.concatenate(reference_ids), frame_indices=np.concatenate(reference_frames),
                                intensity=np.concatenate(reference_intensity), R=R, T=T)
        dump(OUT/rec['sid']/'summary.json', summary)
        catalog.append({k: v for k, v in summary.items() if k != 'frames'})
        dump(OUT/'catalog.json', {'schema_version': cfg['schema_version'], 'sessions': catalog, 'roi_xy': cfg['roi_xy'],
                                'roi_status': cfg['roi_status'], 'R': R.tolist(), 'T': T.tolist(), 'part_classes': PARTS})
    dump(OUT/'reference_object_features.json', training)
    dump(OUT/'candidate_features.json', all_candidates)
    split = audit['splits']
    train = [r for r in training if r['sid'] in split['train'] and (r['sid'] != cfg['background_session'] or r['fi'] % 3 == 0)]
    learned = RandomForestClassifier(n_estimators=cfg['rf_trees'], max_depth=cfg['rf_max_depth'], min_samples_leaf=cfg['rf_min_samples_leaf'], class_weight='balanced', random_state=cfg['seed'], n_jobs=2)
    if len(set(r['label'] for r in train)) == 2:
        learned.fit([r['features'] for r in train], [r['label'] for r in train])
        import pickle
        with (OUT/'rf_xyz_shadow.pkl').open('wb') as f:
            pickle.dump(learned, f)
        report = {'training': 'EXISTING_MANUAL_OBJECTS_THREE_DIMENSIONAL_DESCRIPTORS', 'train_sids': split['train'], 'splits': {}}
        for name, sids in split.items():
            rows = [r for r in all_candidates if r['sid'] in sids and r['label'] is not None and r['scope'] == 'full_3d']
            if rows:
                y = [r['label'] for r in rows]
                rf = learned.predict_proba([r['features'] for r in rows])[:, list(learned.classes_).index(1)]
                pn = np.array([r['pointnet_prob'] for r in rows])
                report['splits'][name] = {'n': len(rows), 'rf_xyz_confusion_tn_fp_fn_tp': confusion_matrix(y, rf >= cfg['model_probability_threshold'], labels=[0, 1]).ravel().tolist(),
                                          'pointnet_confusion_tn_fp_fn_tp': confusion_matrix(y, pn >= cfg['model_probability_threshold'], labels=[0, 1]).ravel().tolist(),
                                          'negative_rows': y.count(0), 'positive_rows': y.count(1)}
        report['limits'] = ['Known overlap rows only; unannotated membership is UNKNOWN, not negative.', 'These sessions have prior development exposure; split is not independent new-person/new-room evidence.', 'Part segmentation and joints have no anatomy GT; BLOCKED.']
        dump(OUT/'model_comparison.json', report)
    else:
        dump(OUT/'model_comparison.json', {'status': 'BLOCKED_NO_TWO_CLASS_TRAINING'})
    assert all(sha(Path(p)) == h for p, h in assets.items()), 'Frozen source/model changed during run'
    dump(EVIDENCE/'RUN_MANIFEST.json', {'config': cfg, 'assets_sha256': assets, 'sessions': catalog,
                                     'versions': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'onnxruntime': ort.__version__},
                                     'command': sys.argv, 'parts_accuracy': 'BLOCKED_NO_ANATOMICAL_LABELS', 'device': 'WINDOWS_LOCAL_OFFLINE'})
    print('Nine-session run finished', len(catalog), flush=True)


if __name__ == '__main__':
    main()
