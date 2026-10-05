"""Compare existing region geometry; diagnostics do not select or replace ROIs."""
import json
import math
from pathlib import Path
import sys
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path[:0] = [str(ROOT/'src/human_fall_detection'), str(ROOT/'src/human_fall_detection/scripts')]
from core.capture_input import load_adapted, gate_selection
from evaluate_gli02_candidate import _draft_region

old = ROOT/'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
draft = json.loads((old/'codex_review_01/work/filled_real_draft.json').read_text(encoding='utf-8'))
manifest, points = load_adapted(str(old/'08_real/real_candidate.adapted.npz'))
fit = _draft_region(draft['fit_region'], 'fit')
selectors = []
for entry in draft['validation_regions']:
    r = _draft_region(entry, 'validation')
    r['region_id'] = entry['region_id']
    selectors.append(r)
rows, regions = gate_selection(points, manifest, fit, None, fit['frame_group'], selectors)
hypotheses = json.loads((OUT/'25_prior_hypotheses_results.json').read_text(encoding='utf-8'))
best = hypotheses['hypotheses']['negative_x_26deg_unapproved']['actual_frozen_result']['candidates'][0]
local_n = np.asarray(best['normal'], dtype=np.float64)
local_d = best['offset_m']
historic_norm = float(np.linalg.norm([-0.51, -0.05, 1.0]))
models = [('local_fit_diagnostic', local_n, local_d),
          ('historical_equation_diagnostic', np.array([-0.51,-0.05,1.0])/historic_norm, 1.53/historic_norm)]
records = []
for label, indices in [('fit', rows)] + [(r['region_id'], r['indices']) for r in regions]:
    cloud = np.asarray(points[indices], dtype=np.float64)
    center = cloud.mean(axis=0)
    eigenvalues, eigenvectors = np.linalg.eigh((cloud-center).T @ (cloud-center))
    normal = eigenvectors[:,0]
    if normal[2] < 0:
        normal = -normal
    record = {'region': label, 'count': len(cloud), 'local_pca_normal_diagnostic': normal.tolist(),
              'local_pca_offset_m': -float(normal @ center),
              'local_pca_angle_to_fit_deg': math.degrees(math.acos(float(np.clip(normal @ local_n, -1, 1)))),
              'bounds_min': cloud.min(axis=0).tolist(), 'bounds_max': cloud.max(axis=0).tolist(), 'models': {}}
    for name, n, d in models:
        signed = cloud @ n + d
        absolute = np.abs(signed)
        record['models'][name] = {'rms_m': float(np.sqrt(np.mean(signed**2))),
            'p95_abs_m': float(np.percentile(absolute,95)), 'support_fraction_5cm': float(np.mean(absolute<=0.05)),
            'signed_p05_m': float(np.percentile(signed,5)), 'signed_median_m': float(np.median(signed)),
            'signed_p95_m': float(np.percentile(signed,95)),
            'points_above_5cm': int(np.count_nonzero(signed>0.05)), 'points_below_minus5cm': int(np.count_nonzero(signed< -0.05))}
    records.append(record)
payload = {'layer': 'Research diagnostics only; no automatic ROI/plane/prior changes',
           'physical_verified': False, 'regions': records}
with (OUT/'26_region_consistency_results.json').open('x', encoding='utf-8') as f:
    json.dump(payload,f,indent=2,allow_nan=False)
print(json.dumps(payload))
