"""Audit fixed spatial boxes frame by frame, without pooling a fit or editing selections."""
import json
from pathlib import Path
import sys
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path[:0] = [str(ROOT/'src/human_fall_detection')]
from core.capture_input import load_adapted, select_group_region

old = ROOT/'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
draft = json.loads((old/'codex_review_01/work/filled_real_draft.json').read_text(encoding='utf-8'))
manifest, points = load_adapted(str(old/'08_real/real_candidate.adapted.npz'))
h = json.loads((OUT/'25_prior_hypotheses_results.json').read_text(encoding='utf-8'))
best = h['hypotheses']['negative_x_26deg_unapproved']['actual_frozen_result']['candidates'][0]
n = np.asarray(best['normal'], dtype=np.float64)
d = best['offset_m']
records, summary = {}, {}
boxes = [('fit', draft['fit_region'])] + [(r['region_id'], r) for r in draft['validation_regions']]
for label, box in boxes:
    series = []
    for gid, group in manifest['frame_groups'].items():
        rows = select_group_region(points, manifest, dict(box['bounds'], frame_group=gid))
        if not len(rows):
            continue
        residual = np.asarray(points[rows], dtype=np.float64) @ n + d
        frame = manifest['frames'][group['ordinal']]
        series.append({'frame_group': gid, 'ordinal': group['ordinal'], 'bag_time_sec': frame.get('bag_time_sec'),
            'count': len(rows), 'signed_median_m': float(np.median(residual)),
            'rms_m': float(np.sqrt(np.mean(residual**2))), 'p95_abs_m': float(np.percentile(np.abs(residual),95)),
            'support_fraction_5cm': float(np.mean(np.abs(residual)<=0.05))})
    records[label] = series
    medians = np.array([r['signed_median_m'] for r in series])
    rms = np.array([r['rms_m'] for r in series])
    summary[label] = {'frames_with_points': len(series), 'count_min': min(r['count'] for r in series),
        'count_max': max(r['count'] for r in series), 'signed_median_min_m': float(medians.min()),
        'signed_median_max_m': float(medians.max()), 'signed_median_std_m': float(medians.std()),
        'rms_min_m': float(rms.min()), 'rms_max_m': float(rms.max())}
payload = {'layer': 'Research diagnostic, fixed box per source frame; no pooled fit, new ROI, or physical claim',
    'physical_verified': False, 'reference_plane': best, 'summary': summary, 'records': records}
with (OUT/'30_temporal_regions_results.json').open('x', encoding='utf-8') as f:
    json.dump(payload,f,indent=2,allow_nan=False)
print(json.dumps(summary))
