"""Read-only inspect approved single-group draft against frozen fit code."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'src/human_fall_detection/scripts'), str(ROOT / 'src/human_fall_detection')]
from core.capture_input import load_adapted, gate_selection
from core.ground import fit_ground_plane_constrained, resolve_constrained_settings
from evaluate_gli02_candidate import _draft_region

old = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
draft = json.loads((old / 'codex_review_01/work/filled_real_draft.json').read_text(encoding='utf-8'))
manifest, points = load_adapted(str(old / '08_real/real_candidate.adapted.npz'))
fit = _draft_region(draft['fit_region'], 'fit')
validation = []
for i, region in enumerate(draft['validation_regions']):
    item = _draft_region(region, 'validation')
    item['region_id'] = region['region_id']
    validation.append(item)
fit_rows, regions = gate_selection(points, manifest, fit, None, fit['frame_group'], validation)
results = {'total_points': len(points), 'frame_groups': len(manifest['frame_groups']),
           'fit_index_count': len(fit_rows), 'fit_frame_group': fit['frame_group'],
           'validation_counts': [len(r['indices']) for r in regions], 'runs': {}}
for label, settings in [('default', None), ('explicit_variant', {'spatial_cell_m': 0.05, 'max_points_per_cell': 8})]:
    result = fit_ground_plane_constrained(
        points, settings=resolve_constrained_settings(settings), frame='innolidar',
        up_axis=draft['up_axis'], sensor_height_interval_m=draft['sensor_height_interval_m'],
        fit_indices=fit_rows, fit_frame_group=fit['frame_group'], validation_regions=regions)
    results['runs'][label] = result
with (OUT / '00_preflight_results.json').open('x', encoding='utf-8') as f:
    json.dump(results, f, indent=2, allow_nan=False)
print(json.dumps({k: v for k, v in results.items() if k != 'runs'}))
print(json.dumps({k: {x: r.get(x) for x in ('status', 'reason', 'sampled_fit_count', 'fit_inlier_count', 'sensor_height_m')} for k, r in results['runs'].items()}))
