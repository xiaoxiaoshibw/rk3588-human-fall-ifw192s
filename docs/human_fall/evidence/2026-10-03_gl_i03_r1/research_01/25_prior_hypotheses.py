"""WHAT_IF only: frozen math, existing data, no approved-prior/artifact writes."""
import json
import math
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'), str(ROOT / 'src/human_fall_detection/scripts')]
from core.capture_input import load_adapted, gate_selection
from core.ground import fit_ground_plane_constrained, resolve_constrained_settings
from evaluate_gli02_candidate import _draft_region

old = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
draft = json.loads((old / 'codex_review_01/work/filled_real_draft.json').read_text(encoding='utf-8'))
manifest, points = load_adapted(str(old / '08_real/real_candidate.adapted.npz'))
fit = _draft_region(draft['fit_region'], 'fit')
selectors = []
for region in draft['validation_regions']:
    r = _draft_region(region, 'validation')
    r['region_id'] = region['region_id']
    selectors.append(r)
indices, regions = gate_selection(points, manifest, fit, None, fit['frame_group'], selectors)
array = np.asarray(points, dtype=np.float64)
roi = array[indices]
center = roi.mean(axis=0)
_, vectors = np.linalg.eigh((roi-center).T @ (roi-center))
roi_normal = vectors[:, 0]
if roi_normal[2] < 0:
    roi_normal = -roi_normal
approved = np.asarray(draft['up_axis'], dtype=np.float64)
negative_x = approved.copy()
negative_x[0] *= -1
settings = resolve_constrained_settings({'spatial_cell_m': 0.05, 'max_points_per_cell': 8})
payload = {'layer': 'WHAT_IF research; not approved calibration or physical verification',
           'approved_draft_unchanged': True, 'physical_verified': False,
           'fit_count': len(indices), 'roi_normal_diagnostic': roi_normal.tolist(), 'hypotheses': {}}
for label, axis in [('approved_positive_x', approved), ('negative_x_26deg_unapproved', negative_x),
                    ('roi_normal_unapproved', roi_normal)]:
    result = fit_ground_plane_constrained(points, settings=settings, frame='innolidar', up_axis=axis.tolist(),
        sensor_height_interval_m=draft['sensor_height_interval_m'], fit_indices=indices,
        fit_frame_group=fit['frame_group'], validation_regions=regions)
    report = {'axis': axis.tolist(), 'roi_angle_deg': math.degrees(math.acos(float(np.clip(roi_normal @ (axis/np.linalg.norm(axis)), -1, 1)))),
              'actual_frozen_result': result, 'holdout_diagnostics_not_fit_validation': []}
    candidates = result.get('competition_candidates') or result.get('candidates') or []
    if candidates:
        best = candidates[0]
        normal = np.asarray(best['normal'], dtype=np.float64)
        offset = best['offset_m']
        for region in regions:
            selected = np.asarray(region['indices'], dtype=np.int64)
            residual = np.abs(array[selected] @ normal + offset)
            rms = float(np.sqrt(np.mean(residual**2)))
            p95 = float(np.percentile(residual, 95))
            fraction = float(np.mean(residual <= settings['inlier_threshold_m']))
            report['holdout_diagnostics_not_fit_validation'].append({
                'region_id': region['region_id'], 'point_count': len(selected),
                'rms_m': rms, 'p95_m': p95, 'support_fraction': fraction,
                'would_pass_existing_residual_gates': rms <= settings['untruncated_rms_max_m'] and p95 <= settings['abs_residual_p95_max_m'] and fraction >= settings['support_fraction_min']})
    payload['hypotheses'][label] = report
historic_normal = np.array([-0.51, -0.05, 1.0])
historic_normal /= np.linalg.norm(historic_normal)
payload['historic_floor_equation_angle_check'] = {
    'equation': 'Z=0.51X+0.05Y-1.53 (historical, not a newly verified physical model)'}
payload['historic_floor_equation_angle_check'].update({
    label: math.degrees(math.acos(float(np.clip(historic_normal @ (axis/np.linalg.norm(axis)), -1, 1))))
    for label, axis in [('positive_x', approved), ('negative_x', negative_x)]})
with (OUT / '25_prior_hypotheses_results.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, allow_nan=False)
print(json.dumps({'layer': payload['layer'], 'hypotheses': {label: {
    'status': report['actual_frozen_result']['status'], 'reason': report['actual_frozen_result']['reason'],
    'sampled_fit_count': report['actual_frozen_result']['sampled_fit_count'],
    'roi_angle_deg': report['roi_angle_deg'],
    'competition_truncated': report['actual_frozen_result'].get('competition_truncated'),
    'holdout': report['holdout_diagnostics_not_fit_validation']}
    for label, report in payload['hypotheses'].items()},
    'historic_angle_check': payload['historic_floor_equation_angle_check']}))
