"""Independent safe checks after the writer stopped; no production writes."""
import ast
import contextlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
PKG = ROOT / 'src/human_fall_detection'
sys.path[:0] = [str(PKG), str(PKG / 'scripts')]
import numpy as np
from core.capture_input import load_adapted, gate_selection
from core.ground import (_balanced_sample, _tangent_basis,
                        fit_ground_plane_constrained, resolve_constrained_settings)
from evaluate_gli02_candidate import main, _draft_region

checks = {}
exits = {}
for name, folder in [('02_full_regression', 'src/human_fall_detection/tests'),
                     ('03_follow_regression', 'src/human_follow_calibration/tests')]:
    path = OUT / (name + '.txt')
    with path.open('xb') as log:
        command = [sys.executable, '-B', '-W', 'error', '-m', 'unittest', 'discover', '-s', folder, '-v']
        r = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    exits[name] = {'command': command, 'exit': r.returncode}
    checks[name] = r.returncode == 0

old = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
npz = old / '08_real/real_candidate.adapted.npz'
draft_path = old / 'codex_review_01/work/filled_real_draft.json'
draft = json.loads(draft_path.read_text(encoding='utf-8'))
target = OUT / 'real_default_candidate.json'
with (OUT / '04_default_real_cli.txt').open('x', encoding='utf-8') as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        rc = main(['--prepared-npz', str(npz), '--draft', str(draft_path),
                   '--source-kind', 'capture_export', '--output', str(target)])
checks['P01_default_real'] = rc == 2 and not target.exists()
exits['P01_default_real'] = {'exit': rc, 'artifact_exists': target.exists()}

manifest, points = load_adapted(str(npz))
fit = _draft_region(draft['fit_region'], 'fit')
validation = []
for region in draft['validation_regions']:
    r = _draft_region(region, 'validation')
    r['region_id'] = region['region_id']
    validation.append(r)
indices, regions = gate_selection(points, manifest, fit, None, fit['frame_group'], validation)
settings = resolve_constrained_settings({'spatial_cell_m': 0.05, 'max_points_per_cell': 8})
result = fit_ground_plane_constrained(points, settings=settings, frame='innolidar',
    up_axis=draft['up_axis'], sensor_height_interval_m=draft['sensor_height_interval_m'],
    fit_indices=indices, fit_frame_group=fit['frame_group'], validation_regions=regions)
checks['real_blocker_reproduced'] = result['reason'] == 'ground_degenerate' and result['sampled_fit_count'] == 1193

# Reproduce the exact frozen RNG draws without changing priors or settings.
up = np.asarray(draft['up_axis'], dtype=np.float64)
up /= np.linalg.norm(up)
array = np.asarray(points, dtype=np.float64)
selected = array[indices]
keep = np.all(np.isfinite(selected), axis=1) & (np.linalg.norm(selected, axis=1) > 0)
indices = indices[keep]
rng = np.random.RandomState(settings['seed'])
tu, tv = _tangent_basis(up)
sampled = _balanced_sample(array, indices, up, tu, tv,
    settings['spatial_cell_m'], settings['max_points_per_cell'], settings['fit_point_cap'], rng)
fp = array[sampled]
counts = dict(distance_degenerate=0, area_degenerate=0, angle_rejected=0,
              height_rejected_after_angle=0, evaluated=0)
for _ in range(settings['ransac_iterations']):
    p0, p1, p2 = fp[rng.choice(len(fp), size=3, replace=False)]
    if min(float(np.linalg.norm(p1-p0)), float(np.linalg.norm(p2-p0)),
           float(np.linalg.norm(p2-p1))) < settings['min_sample_separation_m']:
        counts['distance_degenerate'] += 1
        continue
    cross = np.cross(p1-p0, p2-p0)
    length = float(np.linalg.norm(cross))
    if length <= 0 or length/2 < settings['min_sample_triangle_area_m2']:
        counts['area_degenerate'] += 1
        continue
    normal = cross / length
    if float(normal @ up) < 0:
        normal = -normal
    if math.acos(max(-1., min(1., float(normal @ up)))) > settings['max_angle_rad']:
        counts['angle_rejected'] += 1
        continue
    offset = -float(normal @ p0)
    if not draft['sensor_height_interval_m'][0] <= offset <= draft['sensor_height_interval_m'][1]:
        counts['height_rejected_after_angle'] += 1
        continue
    counts['evaluated'] += 1
center = fp.mean(axis=0)
eigenvalues, eigenvectors = np.linalg.eigh((fp-center).T @ (fp-center))
normal = eigenvectors[:, 0]
if float(normal @ up) < 0:
    normal = -normal
geometry = {'normal': normal.tolist(), 'offset_m': -float(normal @ center),
    'angle_to_approved_up_deg': math.degrees(math.acos(max(-1., min(1., float(normal @ up))))),
    'eigenvalue_ratio': float(eigenvalues[1]/eigenvalues[2])}
checks['second_gate_exact_counts'] = counts == dict(distance_degenerate=19,
    area_degenerate=12, angle_rejected=828, height_rejected_after_angle=2, evaluated=0)
ast.parse((PKG/'scripts/evaluate_gli02_candidate.py').read_text(encoding='utf-8'), feature_version=(3, 8))
checks['unchanged_wrapper_python38_ast'] = True
payload = {'checks': checks, 'commands_and_exits': exits, 'real_variant_result': result,
           'counts': counts, 'pca_geometry_diagnostic_not_physical_calibration': geometry,
           'environment': {'python': sys.version, 'numpy': np.__version__},
           'new_config_exists': (PKG/'config/geometry_constrained_gli03_r1.yaml').exists(),
           'new_tests_exists': (PKG/'tests/test_gli03_candidate_override.py').exists()}
with (OUT/'05_review_results.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, allow_nan=False)
print(json.dumps({'checks': checks, 'counts': counts, 'geometry': geometry}))
sys.exit(0 if all(checks.values()) else 1)
