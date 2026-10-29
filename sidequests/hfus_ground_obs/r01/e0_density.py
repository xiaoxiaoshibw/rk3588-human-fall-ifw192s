"""E0 真实采样密度实测（协议 docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1/PROTOCOL_V1.json 运行前冻结）。

输出：results/E0_SUMMARY.json + E0_ARRAYS.npz + MANIFEST_E0.json（全部排他写）。
实测描述统计与 MODEL_ESTIMATE 理论估计严格分列；无 GT 不产准确率。
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import source_io as sio

EVID = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1'
RESULTS = EVID / 'results'
SESSION = ROOT / 'data/sessions/cap_20261017_113516'
PROTOCOL = EVID / 'PROTOCOL_V1.json'
VOXEL = 0.05
BANDS = [(2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8)]


def sha_file(p):
    import hashlib
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def grid_lock(v_deg, step, tol=0.02):
    d = np.abs((v_deg / step + 0.5) % 1.0 - 0.5) * step
    return float(np.mean(d <= tol))


def empirical_step(v_deg):
    u = np.unique(np.round((v_deg + 180.0) % 360.0, 3))
    d = np.diff(np.sort(u))
    d = d[d > 1e-6]
    return (float(np.median(d)), int(len(u))) if len(d) else (None, int(len(u)))


def elevation_levels(el_deg):
    u = np.unique(np.round(el_deg, 2))
    d = np.diff(np.sort(u))
    d = d[d > 1e-6]
    return int(len(u)), (float(np.median(d)) if len(d) else None)


def frame_metrics(ses, fi):
    p = ses.xyz(fi)
    finite, valid = sio.validity(p)
    v = p[valid]
    r = np.linalg.norm(v, axis=1)
    az = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
    el = np.degrees(np.arctan2(v[:, 2], np.hypot(v[:, 0], v[:, 1])))
    az_step, az_unique = empirical_step(az)
    el_levels, el_gap = elevation_levels(el)
    return dict(fi=fi, rel_s=round(ses.rel_s(fi), 6), rows=int(len(p)),
                finite=int(finite.sum()), nonfinite=int((~finite).sum()),
                valid=int(valid.sum()), invalid_zero=int((finite & ~valid).sum()),
                conservation_ok=bool(len(p) == int(finite.sum()) + int((~finite).sum())),
                az_min=round(float(az.min()), 4), az_max=round(float(az.max()), 4),
                el_min=round(float(el.min()), 4), el_max=round(float(el.max()), 4),
                grid_lock={str(s): round(grid_lock(az, s), 4) for s in (0.25, 0.5, 1.0)},
                grid_lock_el={str(s): round(grid_lock(el, s), 4) for s in (0.25, 0.5, 1.0)},
                az_unique_1e3deg=az_unique, az_empirical_step_deg=az_step,
                el_levels_0p01deg=el_levels, el_level_gap_deg=el_gap), v, r, az, el


def spacing_by_band(v, r):
    nn = cKDTree(v).query(v, k=2)[0][:, 1]
    out = {'overall': nn_stats(nn)}
    for lo, hi in BANDS:
        m = (r >= lo) & (r < hi)
        cells = np.floor(v[m] / VOXEL).astype(np.int64)
        uniq = np.unique(cells, axis=0).shape[0] if m.any() else 0
        s = nn_stats(nn[m])
        s['occupied_voxels_0p05m'] = int(uniq)
        s['rows_in_band'] = int(m.sum())
        out[f'[{lo},{hi})'] = s
    return out


def nn_stats(x):
    if not len(x):
        return dict(count=0, median=None, mean=None, p05=None, p95=None)
    return dict(count=int(len(x)), median=round(float(np.median(x)), 5),
                mean=round(float(np.mean(x)), 5), p05=round(float(np.percentile(x, 5)), 5),
                p95=round(float(np.percentile(x, 95)), 5))


def voxel_key(v):
    c = np.floor(v / VOXEL).astype(np.int64) + (1 << 20)
    return (c[:, 0] << 42) | (c[:, 1] << 21) | c[:, 2]


def angle_key(az, el):
    a = np.round(az / 0.5).astype(np.int64) + (1 << 10)
    e = np.round(el / 0.5).astype(np.int64) + (1 << 10)
    return (a << 20) | e


def accumulation(ses, frame_ids, checkpoints):
    vox, ang, phase = [], [], []
    for fi in frame_ids:
        p = ses.xyz(fi)
        _, valid = sio.validity(p)
        v = p[valid]
        az = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
        el = np.degrees(np.arctan2(v[:, 2], np.hypot(v[:, 0], v[:, 1])))
        vox.append(voxel_key(v))
        ang.append(angle_key(az, el))
        m = np.abs(az) < 150
        ph = float(np.mean((az[m] / 0.5 - np.round(az[m] / 0.5)) * 0.5)) if m.any() else None
        phase.append(dict(fi=fi, az_phase_offset_deg=None if ph is None else round(ph, 6)))
    curves = {}
    for label, keys in (('voxel_0p05m', vox), ('angle_cell_0p5deg', ang)):
        run = keys[0]
        growth = [int(np.unique(run).size)]
        for k in range(2, len(keys) + 1):
            run = np.concatenate([run, keys[k - 1]])
            growth.append(int(np.unique(run).size))
        curves[label] = dict(union_at_k={k: growth[k - 1] for k in sorted(checkpoints) if k <= len(growth)},
                             union_growth=growth,
                             new_per_added_frame=[growth[0]] + [growth[i] - growth[i - 1] for i in range(1, len(growth))])
    return curves, phase


def theory(nn_by_band):
    """MODEL_ESTIMATE：泊松命中概率，假设规则等角采样、无遮挡/反射率差异。"""
    rows = []
    for R in (2, 3, 4, 5, 6, 7, 8):
        d_ideal = R * math.tan(math.radians(0.5))
        band = nn_by_band.get(f'[{R},{R + 1})', {})
        d_meas = band.get('median')
        for s in (0.05, 0.10, 0.15, 0.20, 0.30, 0.50):
            for orient in 'ABCDE':
                if orient == 'A':
                    areas, assume = [(s * s, 'vertical plane facing radar, incidence 0')], 'A'
                elif orient == 'B':
                    areas, assume = [], 'B'
                    for h in (1.10, 1.35663):
                        alpha = math.atan(h / R)
                        areas.append((s * s * math.sin(alpha), f'horizontal patch, depression atan({h}/R); h is sensitivity value, NOT measured height'))
                elif orient == 'C':
                    areas, assume = [(s * s * math.cos(math.radians(45)), 'tilted 45deg facing radar')], 'C'
                elif orient == 'D':
                    areas, assume = [(0.7 * s * s, 'torso curved band lower bound factor 0.7 (assumption)'),
                                     (1.0 * s * s, 'torso curved band upper bound factor 1.0 (assumption)')], 'D'
                else:
                    areas, assume = [(s * 0.05, f'limb bar {s}m x 0.05m head-on')], 'E'
                for area, area_note in areas:
                    for d_label, d in (('IDEAL_R_tan_0p5deg', d_ideal), ('MEASURED_BAND_NN_MEDIAN', d_meas)):
                        if d is None:
                            continue
                        lam = area / (d * d)
                        p0, p1 = math.exp(-lam), lam * math.exp(-lam)
                        p2 = lam * lam / 2 * math.exp(-lam)
                        rows.append(dict(label='MODEL_ESTIMATE', R_m=R, size_m=s, orientation=orient,
                                         projected_area_m2=round(area, 5), area_note=area_note,
                                         spacing_label=d_label, spacing_m=round(d, 5),
                                         lambda_expected_points=round(lam, 3),
                                         P_0=round(p0, 4), P_1=round(p1, 4), P_2=round(p2, 4),
                                         P_ge3=round(max(0.0, 1 - p0 - p1 - p2), 4)))
    return rows


def main():
    t0 = time.time()
    ses = sio.Session(SESSION)
    src_sha = ses.sha256()
    fit_fis = [fi for fi in range(len(ses.frames)) if ses.rel_s(fi) < 20.0]
    a_fit = [fi for fi in range(0, 191, 10)]
    a_act = list(range(250, 751, 50))
    b_fit, b_act = [20, 60, 100, 140, 180], [400]
    assert all(fi in fit_fis for fi in a_fit + b_fit), 'E0 frame plan must stay inside FIT'
    assert all(ses.rel_s(fi) >= 20.0 for fi in a_act + b_act), 'context frames must stay outside FIT'

    frames_A = []
    for fi in a_fit + a_act:
        m, v, r, az, el = frame_metrics(ses, fi)
        m['role'] = 'FIT' if fi in fit_fis else 'ACTION_CONTEXT_NOT_FOR_MODEL'
        frames_A.append(m)

    spacing_B = {}
    for fi in b_fit + b_act:
        p = ses.xyz(fi)
        _, valid = sio.validity(p)
        v = p[valid]
        r = np.linalg.norm(v, axis=1)
        spacing_B[str(fi)] = dict(role='FIT' if fi in fit_fis else 'ACTION_CONTEXT_NOT_FOR_MODEL',
                                  **spacing_by_band(v, r))

    step2 = [fi for fi in fit_fis if fi % 2 == 0]
    checkpoints = {1, 2, 5, 10, 20, 30, 50, 75, 97}
    curves, phase = accumulation(ses, step2, checkpoints)

    nn_meas = {k: v for k, v in spacing_B['20'].items() if k.startswith('[')}
    summary = dict(
        item='HFUS-GROUND-OBSERVABILITY-RD-01', measurement='E0',
        source=dict(sid='cap_20261017_113516', sha256=src_sha, stride=28,
                    interpreted='bytes 0..11 float32 XYZ', opaque='bytes 12..27 NOT_INTERPRETED'),
        run=dict(argv=sys.argv, wall_s=round(time.time() - t0, 2),
                 code_sha256={p.name: sha_file(p) for p in (HERE / 'source_io.py', HERE / 'e0_density.py')},
                 protocol_sha256=sha_file(PROTOCOL)),
        fit_frames_count=len(fit_fis), fit_frame_range=[fit_fis[0], fit_fis[-1]],
        frames_A=frames_A,
        spacing_B=spacing_B,
        accumulation_C=dict(frames=step2, checkpoints=sorted(checkpoints), **curves, grid_phase=phase),
        theory_E=dict(label='MODEL_ESTIMATE',
                      assumptions=['regular equal-angle sampling at 0.5 deg', 'uniform density', 'no occlusion/reflectivity variation', 'Poisson hit counts are MODEL_ESTIMATE, not measured hit rate'],
                      rows=theory(nn_meas)),
    )
    sio.write_new(RESULTS / 'E0_SUMMARY.json', summary)
    sio.save_new_npz(RESULTS / 'E0_ARRAYS.npz',
                     accumulation_voxel=np.array(curves['voxel_0p05m']['union_growth']),
                     accumulation_angle=np.array(curves['angle_cell_0p5deg']['union_growth']))
    manifest = dict(item='HFUS-GROUND-OBSERVABILITY-RD-01', run='E0', argv=sys.argv,
                    exit_code=0, wall_s=round(time.time() - t0, 2),
                    source_sha256=src_sha,
                    code_sha256={p.name: sha_file(p) for p in (HERE / 'source_io.py', HERE / 'e0_density.py')},
                    protocol_sha256=sha_file(PROTOCOL),
                    outputs=['results/E0_SUMMARY.json', 'results/E0_ARRAYS.npz'],
                    notes=['tail 16B never interpreted', 'no GT: descriptive statistics + MODEL_ESTIMATE only',
                           'peak RSS not measured on Windows (NOT_MEASURED)'])
    sio.write_new(RESULTS / 'MANIFEST_E0.json', manifest)
    print('E0 done wall_s=', manifest['wall_s'], 'fit_frames=', len(fit_fis))


if __name__ == '__main__':
    main()
