"""Conditional centroid/count variability, never a physical point correspondence."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from run_experiment import ROOT, EMPTY, load, write, sha, summarize


def audit(output):
    output = output.resolve()
    evidence = ROOT/'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1'
    if output.parent != evidence.resolve(): raise ValueError('Use a new direct evidence child')
    output.mkdir(exist_ok=False)
    meta, raw, hashes = load(ROOT/'data/sessions'/EMPTY)
    result = {}
    for size in (.12, .15):
        frames = []; seen = defaultdict(list)
        for frame in meta['frames']:
            start = frame['offset_points']
            p = raw[start:start+frame['count_points']].astype('f8')
            p = p[np.isfinite(p).all(1) & np.any(p != 0, axis=1)]
            radius = np.linalg.norm(p, axis=1)
            p = p[(radius >= .3) & (radius <= 12)]
            keys, inv, count = np.unique(np.floor(p/size).astype('i8'), axis=0, return_inverse=True, return_counts=True)
            center = np.column_stack([np.bincount(inv, weights=p[:, d])/count for d in range(3)])
            codes = keys[:, 0]*20001**2+keys[:, 1]*20001+keys[:, 2]
            order = np.argsort(codes)
            codes, center, count = codes[order], center[order], count[order]
            bins = np.minimum(2, (np.linalg.norm(center, axis=1)//4).astype(int))
            frames.append((codes, center, bins))
            for code, n, r in zip(codes, count, bins): seen[(int(code), int(r))].append(int(n))
        bands = []
        for r in range(3):
            hits = [counts for (_, b), counts in seen.items() if b == r]
            lags = {}
            for lag in (1, 5, 10, 20):
                drift = []
                for i in range(lag, len(frames)):
                    a, b = frames[i-lag], frames[i]
                    _, ia, ib = np.intersect1d(a[0], b[0], assume_unique=True, return_indices=True)
                    keep = (a[2][ia] == r) & (b[2][ib] == r)
                    drift.extend(np.linalg.norm(a[1][ia[keep]]-b[1][ib[keep]], axis=1).tolist())
                lags[str(lag)] = summarize(drift)
            bands.append(dict(range_bin=r, unique_observed_cells=len(hits),
                              observed_hit_frequency=summarize([len(c)/len(frames) for c in hits]),
                              count_variance_when_hit=summarize([float(np.var(c)) for c in hits]),
                              within_same_voxel_centroid_drift_m=lags))
        result[str(size)] = bands
    final = {p: sha(p) for p in hashes}
    if final != hashes: raise ValueError('Source drift')
    write(output/'STATIC_AUDIT.json', dict(source_sha256=hashes, results=result,
          semantic='HISTORICAL_EMPTY_NOT_CURRENT_HUMAN_REVIEW',
          caveats='Same spatial voxel, not same surface or physical point; counts conditional on hit, absences UNKNOWN; exploratory full empty data, not threshold tuning',
          code_sha256={str(Path(__file__).resolve()): sha(Path(__file__).resolve())}))
    print('STATIC AUDIT DONE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    audit(parser.parse_args().output)
