"""Synthetic verification for the new calibration layer.

The r07 body2 capsule generator is imported read-only.  Its true capsule
samples are used only to define the expected region-edge lengths; estimate()
sees the observed points, never the truth.  The four scenarios use a fixed
posture/cloud per scenario with small per-frame sensor jitter so the test
isolates persistent calibration, not unregistered motion tracking.
"""
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
R07 = ROOT / 'sidequests/hfus_tcms_02/realdev/r07'
R04_SKELETON = ROOT / 'sidequests/human_fusion_lab_next/real_fall/r04'
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1'
sys.path.insert(0, str(R04_SKELETON))
import paths  # noqa: F401  (r04 skeleton's read-only import dependency)
import skeleton as SK
sys.path.insert(0, str(HERE))
from calibrate import CalibrationLayer

SCENARIOS = ['upright', 'bent', 'lying', 'occluded']
SEEDS = {'upright': 2101, 'bent': 2102, 'lying': 2103, 'occluded': 2104}
# Body-axis embeddings are independent of the sensor Z axis.  They are chosen
# before any observed value is inspected.
AXES = {
    'upright': np.array([0.0, 0.0, 1.0]),
    'bent': np.array([0.8660254037844386, 0.0, 0.5]),
    'lying': np.array([0.9848077530122080, 0.0, 0.1736481776669303]),
    'occluded': np.array([0.0998334166468282, 0.0, 0.9950041652780258]),
}
LATERAL = np.array([0.0, 1.0, 0.0])
CENTER = np.array([1.0, 2.0, 1.2])
FRAMES = 60
DENSITY = 10000.0
JITTER_M = 0.002
TRUTH_SAMPLES = 24
TRUTH_DENSITY = 3500.0
TOL_ABS_M = 0.04
TOL_REL = 0.08
GATE_FRACTION = 0.8
GATE_SCENARIOS = 3


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = module('skeleton02_body2', R07 / 'body2.py')


def embed(points, axis, lateral, center):
    u = np.asarray(axis, dtype=float)
    u = u / np.linalg.norm(u)
    v = np.asarray(lateral, dtype=float)
    v = v - np.dot(v, u) * u
    v = v / np.linalg.norm(v)
    n = np.cross(u, v)
    p = np.asarray(points, dtype=float)
    return center + np.outer(p[:, 0], u) + np.outer(p[:, 1], v) + np.outer(p[:, 2], n)


def body_spec(name, seed):
    spec = B.scenario(name, np.random.default_rng(seed))
    # Symmetric, near-straight limbs keep the registered regionalisation
    # well-posed; posture comes from the 3D body-axis embedding above.
    for key in ('arm', 'elbow', 'leg', 'knee'):
        spec['angles'][key + '_L'] = 0.0
        spec['angles'][key + '_R'] = 0.0
    # Make the bilateral limb dimensions exact mirrors.  body2 draws each side
    # independently; unmirrored lengths tilt PCA and make the regional median
    # jump between branches.  This is a synthetic fixture definition, not an
    # extractor change.
    for key in ('UPPER_ARM', 'FOREARM', 'THIGH', 'SHIN'):
        spec['lengths'][key + '_R'] = spec['lengths'][key + '_L']
    return spec


def regionalise(points):
    """Apply the r04 band/branch rules to a true, noiseless point cloud."""
    p = np.asarray(points, dtype=float)
    center = p.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov((p - center).T))
    axis = vectors[:, -1].copy()
    if axis[2] < 0:
        axis = -axis
    lateral = np.cross(axis, [1.0, 0.0, 0.0])
    if np.linalg.norm(lateral) < 0.1:
        lateral = np.cross(axis, [0.0, 1.0, 0.0])
    lateral = lateral / np.linalg.norm(lateral)
    depth = np.cross(lateral, axis)
    basis = np.column_stack([lateral, depth, axis])
    local = (p - center) @ basis
    lo, hi = np.quantile(local[:, 2], [0.02, 0.98])
    fractions = (local[:, 2] - lo) / (hi - lo)
    nodes = {}
    bands = [(0.88, 1.03), (0.70, 0.88), (0.52, 0.70), (0.33, 0.52), (-0.03, 0.33)]
    for name, (low, high) in zip(SK.SLOTS[:5], bands):
        ids = np.flatnonzero((fractions >= low) & (fractions < high))
        nodes[name] = (center + np.median(local[ids], axis=0) @ basis.T
                       if len(ids) >= 6 else None)
    for label, sign in [('A', -1), ('B', 1)]:
        branch = sign * local[:, 0] > 0.08
        masks = [
            ('UPPER_' + label, branch & (fractions >= 0.52) & (fractions < 0.88)),
            ('OUTER_' + label, (sign * local[:, 0] > 0.20) & (fractions >= 0.33) & (fractions < 0.88)),
            ('LOWER_' + label, branch & (fractions >= 0.12) & (fractions < 0.33)),
            ('END_' + label, branch & (fractions >= -0.03) & (fractions < 0.12)),
        ]
        for name, mask in masks:
            ids = np.flatnonzero(mask)
            nodes[name] = (center + np.median(local[ids], axis=0) @ basis.T
                           if len(ids) >= 6 else None)
    for a, b in [('LOWER_A', 'LOWER_B'), ('END_A', 'END_B')]:
        if nodes[a] is not None and nodes[b] is not None and np.linalg.norm(nodes[a] - nodes[b]) < 0.10:
            nodes[a] = nodes[b] = None
    return nodes


def truth_nodes(noiseless_points, axis):
    """Paired truth: same true body cloud with sensor noise removed."""
    out = regionalise(embed(noiseless_points, axis, LATERAL, CENTER))
    edges = {}
    for a, b in SK.EDGES:
        if out[a] is not None and out[b] is not None:
            edges[(a, b)] = float(np.linalg.norm(out[a] - out[b]))
    return out, edges


def measure_skeleton(skeleton):
    out = {}
    for a, b in SK.EDGES:
        na, nb = skeleton['nodes'][a], skeleton['nodes'][b]
        if na['valid'] and nb['valid']:
            out[(a, b)] = float(np.linalg.norm(
                np.asarray(na['xyz'], dtype=float) - np.asarray(nb['xyz'], dtype=float)))
    return out


def run_scenario(name, frames=FRAMES):
    spec = body_spec(name, SEEDS[name])
    axis = AXES[name] / np.linalg.norm(AXES[name])
    t0 = time.perf_counter()
    base, _ = B.sample(spec, np.random.default_rng(SEEDS[name] + 10000),
                       density=DENSITY, noise=0.0, drop=spec['drop'])
    truth_position, truth_edges = truth_nodes(base, axis)
    layer = CalibrationLayer(SK.EDGES)
    previous_axis = None
    previous_lateral = None
    trace = []
    for fi in range(frames):
        jitter = np.random.default_rng(6000 + SEEDS[name] + fi).normal(0.0, JITTER_M, base.shape)
        points = embed(base + jitter, axis, LATERAL, CENTER)
        skeleton, measured_axis = SK.estimate(
            points, (np.arange(len(points)) + fi * 100000).tolist(),
            previous_axis, previous_lateral, dt=0.1, reference_age=0.0)
        if measured_axis is not None:
            previous_axis = measured_axis
            previous_lateral = skeleton.get('basis_lateral')
        measurements = measure_skeleton(skeleton)
        frame = layer.update(fi, measurements)
        trace.append(dict(
            frame=fi,
            valid_nodes=sum(1 for n in skeleton['nodes'].values() if n['valid']),
            edge_count=len(skeleton.get('edges', [])),
            measurement_count=len(measurements),
            edges={key: dict(state=v['state'], mean=v['mean'], sigma=v['sigma'],
                             n=v['n'], measurement=v['measurement'])
                   for key, v in frame['edges'].items()},
        ))
    summary = layer.summary()
    per_edge = {}
    within = calibrated = truth_count = 0
    for edge, true_length in truth_edges.items():
        key = '%s|%s' % edge
        record = summary['edges'][key]
        tolerance = max(TOL_ABS_M, TOL_REL * true_length)
        error = (abs(record['mean'] - true_length)
                 if record['mean'] is not None else None)
        ok = bool(error is not None and error <= tolerance)
        cal_ok = bool(record['state'] == 'CALIBRATED'
                      and record['first_calibrated_frame'] is not None
                      and record['first_calibrated_frame'] < frames)
        within += int(ok)
        calibrated += int(cal_ok)
        truth_count += 1
        per_edge[key] = dict(
            true_length_m=true_length,
            estimate_mean_m=record['mean'],
            abs_error_m=error,
            tolerance_m=tolerance,
            within=ok,
            state=record['state'],
            calibrated=cal_ok,
            first_calibrated_frame=record['first_calibrated_frame'],
            n=record['n'],
            sigma_m=record['sigma'],
        )
    return dict(
        scenario=name,
        seed=SEEDS[name],
        frames=frames,
        density=DENSITY,
        jitter_m=JITTER_M,
        posture={
            'body_axis': axis.tolist(),
            'limb_angles_rad': 0.0,
            'generator_tilt_field': spec.get('tilt'),
            'drop': list(spec.get('drop', ())),
        },
        truth_nodes={k: (None if v is None else v.tolist()) for k, v in truth_position.items()},
        truth_edges={('%s|%s' % e): v for e, v in truth_edges.items()},
        truth_measurable_edges=truth_count,
        within=within,
        within_fraction=(within / truth_count) if truth_count else 0.0,
        calibrated=calibrated,
        calibrated_fraction=(calibrated / truth_count) if truth_count else 0.0,
        per_edge=per_edge,
        gate_within=bool(truth_count and within / truth_count >= GATE_FRACTION),
        gate_calibrated=bool(truth_count and calibrated / truth_count >= GATE_FRACTION),
        state_events=summary['state_events'],
        drift_events=summary['drift_events'],
        frames_trace=trace,
        elapsed_s=time.perf_counter() - t0,
    )


def main(output=None):
    before = {str(p.relative_to(ROOT)): sha(p) for p in [
        R07 / 'body2.py', R04_SKELETON / 'skeleton.py', R04_SKELETON / 'paths.py',
        ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py',
        ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/prototype_params_v1.json',
    ]}
    results = {name: run_scenario(name) for name in SCENARIOS}
    after = {k: sha(ROOT / k) for k in before}
    scenarios_within = sum(r['gate_within'] for r in results.values())
    scenarios_calibrated = sum(r['gate_calibrated'] for r in results.values())
    total_edges = sum(r['truth_measurable_edges'] for r in results.values())
    total_within = sum(r['within'] for r in results.values())
    total_calibrated = sum(r['calibrated'] for r in results.values())
    document = dict(
        item='HFUS-HUMAN-SKELETON-02',
        version=1,
        generator='sidequests/hfus_tcms_02/realdev/r07/body2.py',
        generator_sha256=before[str((R07 / 'body2.py').relative_to(ROOT))],
        reuse=before,
        reuse_files_unchanged=bool(before == after),
        scenarios=results,
        gate=dict(
            scenario_within_fraction=GATE_FRACTION,
            scenario_calibrated_fraction=GATE_FRACTION,
            scenarios_required_within=4,
            scenarios_required_calibrated=GATE_SCENARIOS,
            scenarios_within=scenarios_within,
            scenarios_calibrated=scenarios_calibrated,
            total_measurable_edges=total_edges,
            total_within=total_within,
            total_within_fraction=total_within / total_edges if total_edges else 0.0,
            total_calibrated=total_calibrated,
            total_calibrated_fraction=total_calibrated / total_edges if total_edges else 0.0,
        ),
        truth_note='The generator truth is used only for scoring. estimate() receives observed points only.',
        PASS=False,
    )
    document['PASS'] = bool(
        scenarios_within == 4 and scenarios_calibrated >= GATE_SCENARIOS
        and document['gate']['total_within_fraction'] >= GATE_FRACTION
        and before == after)
    if output:
        out = Path(output)
        with out.open('x', encoding='utf8', newline='\n') as f:
            json.dump(document, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    return document


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else EV / 'SYNTHETIC_CALIBRATION_R2.json'
    doc = main(target)
    print(json.dumps(dict(PASS=doc['PASS'], gate=doc['gate'],
                          reuse_files_unchanged=doc['reuse_files_unchanged']),
                     ensure_ascii=False))
