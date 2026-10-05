"""Codex implementation self-checks, explicitly not independent acceptance."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
PKG = ROOT / 'src/human_fall_detection'
sys.path[:0] = [str(PKG), str(PKG / 'scripts'), str(PKG / 'tests')]
from core.capture_input import load_adapted, gate_selection
from core.ground import fit_ground_plane_constrained, resolve_constrained_settings
from evaluate_gli02_candidate import _draft_region, _load_constrained_settings, main
from sensor_health import load_config
from test_gli02_candidate import write_planar_export, make_draft

checks = {}
commands = {}
for name, folder in [('21_full_regression', 'src/human_fall_detection/tests'),
                     ('22_follow_regression', 'src/human_follow_calibration/tests')]:
    command = [sys.executable, '-B', '-W', 'error', '-m', 'unittest', 'discover', '-s', folder, '-v']
    with (OUT / (name + '.txt')).open('xb') as log:
        process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    commands[name] = {'command': command, 'exit': process.returncode}
    checks[name] = process.returncode == 0

script = PKG / 'scripts/evaluate_gli02_candidate.py'
frozen = PKG / 'config/geometry_constrained.yaml'
variant = PKG / 'config/geometry_constrained_gli03_r1.yaml'
a, b = load_config(str(frozen)), load_config(str(variant))
changed = {k for k in a['ground_constrained'] if a['ground_constrained'][k] != b['ground_constrained'].get(k)}
checks['K02_K05_only_two_values'] = changed == {'spatial_cell_m', 'max_points_per_cell'} and set(a['ground_constrained']) == set(b['ground_constrained'])
checks['frozen_settings_equal_defaults'] = _load_constrained_settings(str(frozen)) == resolve_constrained_settings(None)
for path in (script, PKG / 'tests/test_gli03_candidate_override.py'):
    ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 8))
checks['python38_ast'] = True

# Preserve a reviewable synthetic artifact instead of leaving only temporary outputs.
cap = OUT / 'synthetic_capture'
write_planar_export(cap)
adapted = OUT / 'synthetic.adapted.npz'
from core.capture_input import prepare_npz
prepare_npz(str(cap), 'innolidar', 'm', str(adapted))
manifest, _ = load_adapted(str(adapted))
draft_path = OUT / 'synthetic_draft.json'
with draft_path.open('x', encoding='utf-8') as f:
    json.dump(make_draft(list(manifest['frame_groups'])), f, indent=2)
for label, config in [('default', None), ('variant', variant)]:
    output = OUT / ('synthetic_' + label + '_candidate.json')
    args = ['--prepared-npz', str(adapted), '--draft', str(draft_path), '--output', str(output), '--source-kind', 'synthetic_fixture']
    if config is not None:
        args += ['--constrained-config', str(config)]
    rc = main(args)
    artifact = json.loads(output.read_text(encoding='utf-8'))
    checks['synthetic_' + label] = rc == 0 and artifact['status']['ground'] == 'candidate' and artifact['ground']['status'] == 'valid'
    checks['physical_false_' + label] = artifact['verification']['ground_physical_verified'] is False and artifact['input']['input_manifest']['provenance']['physical_verified'] is False and 'ground_derived' not in artifact

old = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
real_npz = old / '08_real/real_candidate.adapted.npz'
real_draft = old / 'codex_review_01/work/filled_real_draft.json'
draft = json.loads(real_draft.read_text(encoding='utf-8'))
manifest, points = load_adapted(str(real_npz))
fit = _draft_region(draft['fit_region'], 'fit')
regions = []
for region in draft['validation_regions']:
    item = _draft_region(region, 'validation')
    item['region_id'] = region['region_id']
    regions.append(item)
indices, validation = gate_selection(points, manifest, fit, None, fit['frame_group'], regions)
real_results = {}
for label, config, reason in [('default', None, 'ground_points_insufficient'), ('variant', variant, 'ground_degenerate')]:
    output = OUT / ('real_' + label + '_candidate.json')
    command = [sys.executable, '-B', '-W', 'error', str(script), '--prepared-npz', str(real_npz), '--draft', str(real_draft), '--output', str(output), '--source-kind', 'capture_export']
    if config is not None:
        command += ['--constrained-config', str(config)]
    with (OUT / ('23_real_' + label + '_cli.txt')).open('xb') as log:
        process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    commands['real_' + label] = {'command': command, 'exit': process.returncode, 'candidate_exists': output.exists()}
    result = fit_ground_plane_constrained(points, settings=_load_constrained_settings(None if config is None else str(config)), frame='innolidar',
        up_axis=draft['up_axis'], sensor_height_interval_m=draft['sensor_height_interval_m'], fit_indices=indices,
        fit_frame_group=fit['frame_group'], validation_regions=validation)
    real_results[label] = result
    checks['real_' + label + '_honest_refusal'] = process.returncode == 2 and not output.exists() and result['reason'] == reason

files = [script, variant, PKG / 'tests/test_gli03_candidate_override.py']
payload = {'role': 'Codex writer self-check, not independent acceptance', 'checks': checks,
    'commands': commands, 'real_results': real_results,
    'changed_config_keys': sorted(changed), 'sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
with (OUT / '24_selfcheck_results.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, allow_nan=False)
print(json.dumps({'role': payload['role'], 'checks': checks, 'sha256': payload['sha256'],
    'real_counts': {label: result['sampled_fit_count'] for label, result in real_results.items()}}))
sys.exit(0 if all(checks.values()) else 1)
