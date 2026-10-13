"""只读重建 C1 候选，保留51维历史基线；新增18维研究特征。"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OLD = ROOT / 'docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization'
sys.path.insert(0, str(ROOT / 'pc_apps/human_ml'))
from frame_feature import extract_features, FEAT_NAMES

R = np.array([[.893544, 0, .448975], [-.014337, .99949, .028533],
              [-.448746, -.031932, .893089]])
T = np.array([0, 0, 1.380286])  # 既有软件变换复现，不作物理标定主张
NEW_NAMES = ([f'layer{k}_fraction' for k in range(5)] +
             [f'layer{k}_xy_width' for k in range(5)] +
             ['layer_width_cv', 'linearity', 'planarity', 'scattering',
              'local03_planarity', 'local06_planarity', 'local06_scattering',
              'range_squared_count'])


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    with Path(path).open('x', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)


def shape(xyz):
    if len(xyz) < 10:
        return np.zeros(3)
    w = np.maximum(np.linalg.eigvalsh(np.cov(xyz.T))[::-1], 0)
    if w[0] < 1e-10:
        return np.zeros(3)
    return np.array([(w[0]-w[1])/w[0], (w[1]-w[2])/w[0], w[2]/w[0]])


def extra(xyzi):
    if xyzi.ndim != 2 or xyzi.shape[1] != 4 or not np.isfinite(xyzi).all():
        raise ValueError('finite Nx4 required')
    if len(xyzi) < 10:
        return np.zeros(18, dtype=np.float32)
    xyz = xyzi[:, :3].astype(float)
    z = xyz[:, 2]
    lo, hi = np.percentile(z, [2, 98])
    norm = np.clip((z-lo)/max(hi-lo, 1e-8), 0, 1)
    layers = np.minimum((norm*5).astype(int), 4)
    fractions, widths = [], []
    for k in range(5):
        part = xyz[layers == k, :2]
        fractions.append(len(part)/len(xyz))
        widths.append(float(np.linalg.norm(np.diff(np.percentile(part, [10, 90], axis=0), axis=0)))
                      if len(part) >= 10 else 0.)
    cv = np.std(widths)/max(np.mean(widths), 1e-8)
    center = np.median(xyz, axis=0)
    radius = np.linalg.norm(xyz-center, axis=1)
    small, large = shape(xyz[radius <= .3]), shape(xyz[radius <= .6])
    range2 = float(np.sum(np.mean(xyz[:, :2], axis=0)**2))
    # ponytail: 密度只是range²代理；扫描/遮挡实测后再校准，不靠它硬拒。
    result = np.array(fractions + widths + [cv] + list(shape(xyz)) +
                      [small[1], large[1], large[2], len(xyz)*range2], dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError('feature overflow')
    return result


def candidates(points, bg):
    lev = points[:, :3].astype(float) @ R.T + T
    valid = np.isfinite(points[:, :4]).all(axis=1) & (lev[:, 2] > .1) & (lev[:, 2] < 2.3)
    ids = np.flatnonzero(valid)
    xyz = lev[valid]
    keys = np.floor(xyz[:, 0]/.05).astype(np.int64)*4096 + np.floor(xyz[:, 1]/.05).astype(np.int64)
    base = np.array([bg.get(str(int(k)), -10.) for k in keys])
    hot = np.flatnonzero((base > -9) & (xyz[:, 2] > base+.25))
    grid = {}
    for p in hot:
        grid.setdefault(int(keys[p]), []).append(p)
    seen, groups = set(), []
    for key in grid:
        if key in seen:
            continue
        stack, members = [key], []
        seen.add(key)
        while stack:
            cur = stack.pop()
            members.extend(grid[cur])
            a, b = divmod(cur, 4096)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbor = (a+dx)*4096+b+dy
                    if neighbor in grid and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        if len(members) >= 30:
            groups.append(np.array(members))
    groups.sort(key=len, reverse=True)
    return [(np.column_stack([xyz[g], points[ids[g], 3]]).astype(np.float32), ids[g])
            for g in groups[:4]]


def main():
    out = HERE / 'prepared'
    out.mkdir(exist_ok=False)
    datafile = OLD / 'rf_v2/cluster_dataset.jsonl'
    with datafile.open(encoding='utf8') as f:
        rows = [json.loads(l) for l in f]
    bgfile = ROOT / 'pc_apps/human_replay/bg_envelope.json'
    with bgfile.open(encoding='utf8') as f:
        bg = json.load(f)
    by_sid = {}
    for i, row in enumerate(rows):
        by_sid.setdefault(row['sid'], {}).setdefault(row['frame'], []).append((i, row))
    X = np.empty((len(rows), 69), dtype=np.float32)
    provenance = [{'path':str(p.relative_to(ROOT)), 'sha256':sha(p)} for p in
                  [datafile, bgfile, ROOT/'pc_apps/human_ml/frame_feature.py']]
    bindings, latencies = [], []
    for sid, frames in sorted(by_sid.items()):
        folder = ROOT/'captures/remote'/sid
        with (folder/'meta.json').open(encoding='utf8') as f:
            meta = json.load(f)
        if meta.get('point_stride_bytes') != 28:
            raise ValueError('only audited canonical 28-byte source supported')
        for p in [folder/'meta.json', folder/'points.bin', folder/'ai_labels.json']:
            provenance.append({'path':str(p.relative_to(ROOT)), 'sha256':sha(p)})
        raw = np.memmap(folder/'points.bin', mode='r', dtype=np.uint8).reshape(-1, 28).view('<f4').reshape(-1, 7)
        for fi, records in sorted(frames.items()):
            frame = meta['frames'][fi]
            offset, count = frame['offset_points'], frame['count_points']
            if offset < 0 or count < 0 or offset+count > len(raw):
                raise ValueError('frame out of bounds')
            groups = candidates(raw[offset:offset+count], bg)
            for i, row in records:
                pts, ids = groups[row['rank']]
                tick = time.perf_counter()
                fv = extract_features(pts)
                ext = extra(pts)
                latencies.append((time.perf_counter()-tick)*1000)
                np.testing.assert_allclose(fv, row['fv'], rtol=1e-5, atol=1e-5)
                if len(pts) != int(row['fv'][0]):
                    raise ValueError('candidate count mismatch')
                X[i] = np.r_[fv, ext]
                bindings.append({'row':i, 'sid':sid, 'frame_index':fi, 'frame_seq':frame['seq'],
                                 'rank':row['rank'], 'source_point_indices_sha256':hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest(),
                                 'weak_label':row['cls'], 'label_source':'legacy_C1_position_rule',
                                 'gt_status':'UNVERIFIED', 'posture':'stand_weak', 'scene':'same_room',
                                 'horizontal_range':float(np.linalg.norm(pts[:, :2].mean(axis=0)))})
        del raw
        print(sid, 'bound', sum(len(v) for v in frames.values()), flush=True)
    np.savez(out/'dataset.npz', X=X, y=np.array([int(r['cls']=='person') for r in rows]),
             sid=np.array([r['sid'] for r in rows]))
    save(out/'bindings.json', sorted(bindings, key=lambda b:b['row']))
    save(out/'provenance.json', provenance)
    names = list(FEAT_NAMES)
    actual = {40:'pca_r02',41:'radial_distance_std',42:'height_p90_p10',43:'log10_height_range',
              44:'upper_middle_count_ratio',45:'intensity_p10',46:'intensity_p50',47:'intensity_p90',
              48:'fraction_horizontal_range_lt3',49:'height_p90_duplicate',50:'covariance_trace'}
    for i, n in actual.items(): names[i] = n
    corr = np.zeros((69, 69))
    varying = np.std(X.astype(float), axis=0)>1e-10
    corr[np.ix_(varying, varying)] = np.corrcoef(X[:, varying].T)
    save(out/'feature_audit.json', {'legacy_names':FEAT_NAMES, 'actual_names':names+NEW_NAMES,
         'constant_indices':np.flatnonzero(~varying).tolist(),
         'correlated_pairs_abs_ge_095':[[int(i),int(j),float(corr[i,j])] for i in range(69) for j in range(i+1,69) if abs(corr[i,j])>=.95],
         'feature_ms_p50_p95':np.percentile(latencies,[50,95]).tolist(),
         'all_1239_legacy_vectors_reproduced':len(rows), 'new_dimensions':18,
         'numeric_policy':'n<10 zero; local insufficient/degenerate PCA zero; nonfinite rejected',
         'transform':'fixed existing C1 R/T, software coordinate only; no physics conclusion'})
    print('prepared', X.shape, flush=True)


if __name__ == '__main__':
    main()
