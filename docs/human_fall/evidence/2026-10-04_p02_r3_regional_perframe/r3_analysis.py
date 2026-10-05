# -*- coding: utf-8 -*-
"""P02 R3 分区/逐帧地面建模（一次性研究脚本，不接运行时）。

输入只用冻结资产：2026-10-04_p02_four_roi_r1/02_FROZEN_POINTS.npz（392196 点，
row/session/region/frame/XYZ）与 03_RESULTS.json（联合单平面参照）。先冻结再估计，
不裁尾、不改 ROI、不调门。R2 纯函数经 AST 只载函数定义（plane_from_tls 等），
不运行其 main。输出 01_DIAGNOSIS.json / 02_MODEL_REGIONAL.json /
03_MODEL_PERFRAME.json + npz / 04_FRAME_RESIDUALS.csv / 05_UPGRADE_RECOMMENDATION.md。
拒绝覆盖既有产物。ponytail: TLS=SVD 同型实现，不另跑 SVD 凑"独立"证据。
"""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
R2 = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_four_roi_r1'
R2E = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_ground_r2'
STATES = {0: 'A', 2: 'C'}
REGIONS = (1, 2, 3, 4)
UP = np.array([0.0, 0.0, 1.0])  # source 系 Z 向即 R2 normalize 的 up 参照


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=1, allow_nan=False)


def normalize(n, d):
    return (n, d) if n @ UP >= 0 else (-n, -d)


def stats(points, n, d):
    z = points @ n + d
    return {'count': int(len(z)), 'rms_m': float(np.sqrt(np.mean(z * z))),
            'p95_m': float(np.percentile(np.abs(z), 95)),
            'median_m': float(np.median(z)),
            'support_fraction': float(np.mean(np.abs(z) <= .05))}


def quality(result):
    return ('PASS' if (result['count'] >= 20 and result['rms_m'] <= .03
                       and result['p95_m'] <= .05 and result['support_fraction'] >= .8)
            else 'FAIL')


def rotation(pitch_deg, roll_deg):
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cp, 0, sp], [sr * sp, cr, -sr * cp], [-cr * sp, sr, cr * cp]])


def pose_of(n, d):
    pitch = math.degrees(math.atan2(-n[0], n[2]))
    roll = math.degrees(math.asin(float(np.clip(n[1], -1.0, 1.0))))
    return pitch, roll


def cusum_flags(series, k, h):
    """双边 CUSUM 跳变点（stdlib 实现，不引新库）。k=允许漂移，h=报警阈。"""
    s_hi, s_lo, hits = 0.0, 0.0, []
    for i, v in enumerate(series):
        s_hi = max(0.0, s_hi + v - k)
        s_lo = min(0.0, s_lo + v + k)
        if s_hi > h or s_lo < -h:
            hits.append(i)
            s_hi, s_lo = 0.0, 0.0
    return hits


def main():
    for name in ['01_DIAGNOSIS.json', '02_MODEL_REGIONAL.json', '03_MODEL_PERFRAME.json',
                 '03_MODEL_PERFRAME.npz', '04_FRAME_RESIDUALS.csv']:
        assert not (OUT / name).exists(), 'immutable output exists: ' + name

    baseline = json.loads((OUT / '00_BASELINE.json').read_text(encoding='utf-8'))
    for rel, expected in baseline['inputs'].items():
        assert sha(ROOT / rel) == expected, 'input drift: ' + rel

    frozen = np.load(R2 / '02_FROZEN_POINTS.npz')
    points = frozen['source']
    rows = frozen['source_rows']
    sess = frozen['session_code']
    region = frozen['region_code']
    ordinal = frozen['frame_ordinal']
    assert hashlib.sha256(points.tobytes()).hexdigest() == baseline['frozen_point_sha256']
    assert hashlib.sha256(rows.tobytes()).hexdigest() == baseline['frozen_row_sha256']
    assert len(points) == baseline['frozen_point_count'] == 392196

    # R2 已审 TLS 纯函数（AST 只载定义，不运行其 main/旧输出）
    tree = ast.parse((R2E / 'p02_same_domain_estimators.py').read_text(encoding='utf-8'))
    definitions = [node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'plane_from_tls']
    assert len(definitions) == 1
    namespace = {'np': np, 'math': math}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), 'reused_tls', 'exec'), namespace)
    tls = namespace['plane_from_tls']

    r2 = json.loads((R2 / '03_RESULTS.json').read_text(encoding='utf-8'))
    joint = {'normal': np.array(r2['estimators']['tls']['normal_source']),
             'd': float(r2['estimators']['tls']['d_source_m']),
             'rms_m': float(r2['estimators']['tls']['rms_m']),
             'p95_m': float(r2['estimators']['tls']['p95_m']),
             'support_fraction': float(r2['estimators']['tls']['support_fraction'])}

    # ── 3.1 分区诊断 ─────────────────────────────────────────────────────
    # 每 ROI 独立 TLS 平面（4 个）
    region_planes = {}
    for r in REGIONS:
        mask = region == r
        n, d = normalize(*tls(points[mask]))
        pitch, roll = pose_of(n, d)
        region_planes[r] = {'normal': n, 'd': d, 'pitch_deg': pitch, 'roll_deg': roll,
                            'count': int(mask.sum()), **stats(points[mask], n, d)}
        region_planes[r]['quality'] = quality(region_planes[r])

    # a. 成对一致性矩阵（6 对）：normal 夹角、d 差、全点互预测
    pairwise = []
    for i, ra in enumerate(REGIONS):
        for rb in REGIONS[i + 1:]:
            pa, pb = region_planes[ra], region_planes[rb]
            angle = math.degrees(math.acos(float(np.clip(pa['normal'] @ pb['normal'], -1, 1))))
            d_gap = abs(pa['d'] - pb['d'])
            cross = {}
            for src, dst in [(ra, rb), (rb, ra)]:
                key = '%d_fit_predicts_%d' % (dst, src)
                result = stats(points[region == src], region_planes[dst]['normal'],
                               region_planes[dst]['d'])
                result['quality'] = quality(result)
                cross[key] = result
            pairwise.append({'pair': [ra, rb], 'normal_angle_deg': angle, 'd_gap_m': d_gap,
                             'consistency_reference': 'PASS' if (angle < 0.5 and d_gap < 0.005) else 'FAIL',
                             **{k: {kk: vv for kk, vv in v.items()} for k, v in cross.items()}})

    # b. 分区×分帧 fit：region×session 8 平面 + 全 193×4 帧残差序列
    frame_keys = sorted({(int(s), int(o)) for s, o in zip(sess, ordinal)})
    assert len(frame_keys) == 193
    cell_planes = {}   # (region, session_code) -> plane
    cell_list = []
    for r in REGIONS:
        for scode in STATES:
            mask = (region == r) & (sess == scode)
            n, d = normalize(*tls(points[mask]))
            pitch, roll = pose_of(n, d)
            cell = {'region': r, 'session': STATES[scode], 'normal': n, 'd': d,
                    'pitch_deg': pitch, 'roll_deg': roll, 'count': int(mask.sum()),
                    **stats(points[mask], n, d)}
            cell['quality'] = quality(cell)
            cell_planes[(r, scode)] = cell
            cell_list.append({k: (v.tolist() if isinstance(v, np.ndarray) else v)
                              for k, v in cell.items()})

    # 逐帧到「各自分区平面」（同 region、跨 session 联合的 4 平面）残差
    frames = []
    for scode, o in frame_keys:
        for r in REGIONS:
            mask = (sess == scode) & (ordinal == o) & (region == r)
            z = points[mask] @ region_planes[r]['normal'] + region_planes[r]['d']
            assert len(z) >= 20, 'frame cell too small'
            frames.append({'session': STATES[scode], 'ordinal': int(o), 'region': r,
                           'count': int(len(z)), 'median_m': float(np.median(z)),
                           'mean_m': float(np.mean(z)), 'std_m': float(np.std(z)),
                           'rms_m': float(np.sqrt(np.mean(z * z))),
                           'p05_m': float(np.percentile(z, 5)),
                           'p95_m': float(np.percentile(z, 95))})

    # c. 残差分解：帧内结构项（帧 std）/ 分区平面间慢变项（帧 median 摆动）/ 真噪声项
    decomp = {}
    for r in REGIONS:
        rs = [f for f in frames if f['region'] == r]
        within = np.array([f['std_m'] for f in rs])
        med = np.array([f['median_m'] for f in rs])
        decomp[str(r)] = {
            'within_frame_structure_std_m': {'mean': float(within.mean()), 'max': float(within.max())},
            'inter_frame_slow_std_m': float(med.std()),
            'inter_frame_slow_range_m': [float(med.min()), float(med.max())],
            'total_median_std_m': float(med.std()),
            'noise_floor_mad_m': float(np.median(np.abs(med - np.median(med)))),
            'within_over_slow_ratio': float(within.mean() / med.std()) if med.std() > 0 else None}

    # 逐帧、逐 ROI TLS 平面序列（模型 II 原料，先算好供 3.1 类型判定 + 3.2 复用）
    seq = []
    for scode, o in frame_keys:
        for r in REGIONS:
            mask = (sess == scode) & (ordinal == o) & (region == r)
            pts = points[mask]
            n, d = normalize(*tls(pts))
            pitch, roll = pose_of(n, d)
            A = np.column_stack([pts, np.ones(len(pts))])
            atacov = np.linalg.inv(A.T @ A)
            resid = A @ np.append(n, d)
            sigma2 = float(resid @ resid / (len(pts) - 4))
            seq.append({'session': STATES[scode], 'ordinal': int(o), 'region': r,
                        'n': n, 'd': d, 'pitch_deg': pitch, 'roll_deg': roll,
                        'cov': sigma2 * atacov, 'count': int(len(pts))})

    per_region_frame_spread = {}
    for r in REGIONS:
        sub = [s for s in seq if s['region'] == r]
        normals = np.array([s['n'] for s in sub])
        ref = region_planes[r]['normal']
        angles = np.degrees(np.arccos(np.clip(normals @ ref, -1, 1)))
        ds = np.array([s['d'] for s in sub])
        per_region_frame_spread[str(r)] = {
            'normal_angle_std_deg': float(angles.std()),
            'normal_angle_max_deg': float(angles.max()),
            'pitch_std_deg': float(np.std([s['pitch_deg'] for s in sub])),
            'roll_std_deg': float(np.std([s['roll_deg'] for s in sub])),
            'd_std_m': float(ds.std()), 'frames': len(sub)}

    # d. 类型判定（门写死在 00_BASELINE，先看数据再分类 = 违规；按声明门执行）
    pair_angles = [p['normal_angle_deg'] for p in pairwise]
    pair_dgaps = [p['d_gap_m'] for p in pairwise]
    max_pair_angle, max_pair_d = max(pair_angles), max(pair_dgaps)
    region_std_max = max(v['normal_angle_std_deg'] for v in per_region_frame_spread.values())
    d_std_max = max(v['d_std_m'] for v in per_region_frame_spread.values())
    slow_std_max = max(v['inter_frame_slow_std_m'] for v in decomp.values())
    if region_std_max >= 0.05 or d_std_max >= 0.005:
        gtype, basis = 'C', 'region per-frame normal std %.4f deg / d std %.5f m exceeds 0.05 deg / 5 mm' % (region_std_max, d_std_max)
    elif max_pair_angle >= 0.5 or max_pair_d >= 0.005:
        gtype, basis = 'B', 'max pairwise normal gap %.4f deg / d gap %.5f m exceeds 0.5 deg / 5 mm; per-frame std within regions <0.05 deg' % (max_pair_angle, max_pair_d)
    else:
        within = max_pair_angle <= max(region_std_max, 1e-12) * 3 and max_pair_d <= max(slow_std_max, 1e-12) * 3
        gtype = 'A' if within else 'B'
        basis = ('all pairwise gaps under reference; inter-region gaps comparable to per-frame spread'
                 if within else
                 'pairwise gaps under 0.5 deg/5 mm but exceed 3x per-frame spread; classify B (conservative)')

    diagnosis = {
        'input_npz_sha256': baseline['inputs']['docs/human_fall/evidence/2026-10-04_p02_four_roi_r1/02_FROZEN_POINTS.npz'],
        'point_sha256': baseline['frozen_point_sha256'],
        'region_planes': {str(r): {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                                   for k, v in region_planes[r].items()} for r in REGIONS},
        'pairwise_matrix': pairwise,
        'cell_planes_region_x_session': cell_list,
        'frame_residuals_to_region_plane': frames,
        'residual_decomposition': decomp,
        'per_region_frame_spread': per_region_frame_spread,
        'type_classification': {'type': gtype, 'basis': basis,
                                'max_pairwise_normal_angle_deg': max_pair_angle,
                                'max_pairwise_d_gap_m': max_pair_d,
                                'max_within_region_frame_normal_std_deg': region_std_max,
                                'max_within_region_frame_d_std_m': d_std_max},
        'gates_unchanged': baseline['gates'],
        'physical_verified': False, 'runtime_eligible': False}
    write_json('01_DIAGNOSIS.json', diagnosis)
    print('type:', gtype, '|', basis, flush=True)

    # ── 3.2 模型 I：分区平面集 ────────────────────────────────────────────
    models = {}
    footprints = {}
    for r in REGIONS:
        mask = region == r
        n, d = region_planes[r]['normal'], region_planes[r]['d']
        pitch, roll = region_planes[r]['pitch_deg'], region_planes[r]['roll_deg']
        R = rotation(pitch, roll)
        assert abs(np.linalg.det(R) - 1) < 1e-12
        assert float(np.max(np.abs(R @ n - [0, 0, 1]))) < 1e-12
        leveled = points[mask] @ R.T + np.array([0.0, 0.0, d])
        assert float(np.max(np.abs(leveled[:, 2] - (points[mask] @ n + d)))) < 1e-12
        back = (leveled - np.array([0.0, 0.0, d])) @ R
        assert float(np.max(np.abs(back - points[mask]))) < 1e-12
        footprints[r] = {'x_m': [float(points[mask][:, 0].min()), float(points[mask][:, 0].max())],
                         'y_m': [float(points[mask][:, 1].min()), float(points[mask][:, 1].max())]}
        models[str(r)] = {
            'kind': 'observed_ground_display_leveling', 'schema': 1, 'status': 'research_display',
            'from_frame': 'innolidar', 'to_frame': 'ground_display_roi%d' % r, 'units': 'm',
            'direction': 'p_to=R@p_from+t', 'convention': 'active column vectors; R=Rx(roll)@Ry(pitch)',
            'pitch_deg': pitch, 'roll_deg': roll, 'yaw_deg': 0,
            'rotation': R.tolist(), 'translation_m': [0.0, 0.0, d],
            'plane_source': {'normal': n.tolist(), 'offset_m': d},
            'xy_footprint_source_m': footprints[r],
            'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False,
            'coverage': 'frozen annotator #%d 2cm-interior ROI, A/C data; outside footprint unverified' % r}

    # 联合评估：全 392196 点各用本区平面 vs R2 联合单平面
    z_regional = np.empty(len(points))
    for r in REGIONS:
        mask = region == r
        z_regional[mask] = points[mask] @ region_planes[r]['normal'] + region_planes[r]['d']
    regional_eval = {'count': int(len(points)),
                     'rms_m': float(np.sqrt(np.mean(z_regional ** 2))),
                     'p95_m': float(np.percentile(np.abs(z_regional), 95)),
                     'support_fraction': float(np.mean(np.abs(z_regional) <= .05))}
    regional_eval['quality'] = quality(regional_eval)
    joint_eval = {'count': joint['count'] if 'count' in joint else int(len(points)),
                  'rms_m': joint['rms_m'], 'p95_m': joint['p95_m'],
                  'support_fraction': joint['support_fraction'],
                  'quality': quality({'count': len(points), **joint_eval_minimal(joint)})}

    model_i = {
        'model': 'I_regional_plane_set', 'status': 'research_display',
        'input_npz_sha256': baseline['inputs']['docs/human_fall/evidence/2026-10-04_p02_four_roi_r1/02_FROZEN_POINTS.npz'],
        'regions': models,
        'region_lookup_contract': {
            'query': 'z_ground(p_source, region=None)',
            'rule': ['region 给定时直接用该区 n/d；不给定时按 xy_footprint_source_m 包含测试查表',
                     'footprint 互不重叠（冻结 ROI 已断言 disjoint）；未命中任何 footprint -> 返回 None 并标 unverified，不外推',
                     '边界重叠（若未来 ROI 改动导致）：取 |n.p+d| 最小者并在日志记录 ambiguous'],
            'fallback': '未命中 = 无地面高度，不默认 0、不沿用邻区'},
        'joint_evaluation_regional': regional_eval,
        'joint_evaluation_single_plane_r2': joint_eval,
        'comparison': 'regional RMS %.6f m vs single-plane %.6f m' % (regional_eval['rms_m'], joint['rms_m']),
        'physical_height_record_m': 1.14,
        'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False}
    write_json('02_MODEL_REGIONAL.json', model_i)
    print('model I regional RMS %.6f / P95 %.6f vs joint %.6f / %.6f'
          % (regional_eval['rms_m'], regional_eval['p95_m'], joint['rms_m'], joint['p95_m']), flush=True)

    # ── 3.2 模型 II：逐帧估计序列（两型都交）─────────────────────────────
    variability = {}
    for r in REGIONS:
        sub = [s for s in seq if s['region'] == r]
        entry = {}
        for key in ['pitch_deg', 'roll_deg', 'd']:
            series = np.array([s[key if key != 'd' else 'd'] for s in sub])
            diff = np.diff(series)
            t = np.arange(len(series))
            slope, intercept = np.polyfit(t, series, 1)
            sigma = diff.std() if diff.std() > 0 else 1e-12
            entry[key] = {'diff_std': float(diff.std()),
                          'linear_slope_per_frame': float(slope),
                          'total_trend': float(slope * (len(series) - 1)),
                          'series_std': float(series.std()),
                          'cusum_jumps': cusum_flags(series - series.mean(), 0.5 * sigma, 5 * sigma)}
        variability[str(r)] = entry

    np.savez_compressed(
        OUT / '03_MODEL_PERFRAME.npz',
        normal=np.array([s['n'] for s in seq]), d=np.array([s['d'] for s in seq]),
        cov=np.array([s['cov'] for s in seq]),
        region_code=np.array([s['region'] for s in seq], dtype=np.uint8),
        session_code=np.array([0 if s['session'] == 'A' else 2 for s in seq], dtype=np.uint8),
        frame_ordinal=np.array([s['ordinal'] for s in seq], dtype=np.int16),
        count=np.array([s['count'] for s in seq], dtype=np.int32))
    model_ii = {
        'model': 'II_per_frame_sequence', 'status': 'research_display',
        'records': len(seq), 'layout': 'npz rows = session-major frame order x region 1..4; 193x4',
        'npz_sha256': sha(OUT / '03_MODEL_PERFRAME.npz'),
        'param_covariance': 'sigma2*(A^T A)^-1 from TLS normal equations; A=[x y z 1], params [nx ny nz d]; eigh normal => covariance of the constrained 4-param solve is approximate (normal lives on unit sphere); treat as scale reference, not rigorous CI',
        'variability': variability,
        'consumption_contract': {
            'time_indexed_lookup': 'frame key (session, ordinal) -> nearest record; O(1) dict; recommended for replay parity',
            'interpolation': 'linear blend of adjacent frames in n (then renormalize) and d; smooths quantization but invents unsampled states; NOT recommended without evidence that inter-frame motion is smooth',
            'tradeoff': 'lookup preserves measured values and keeps FAIL frames visible; interpolation hides jumps. Given per-frame std already <0.05 deg, lookup suffices.'},
        'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False}
    write_json('03_MODEL_PERFRAME.json', model_ii)
    print('model II: %d records, npz sha %s' % (len(seq), model_ii['npz_sha256'][:16]), flush=True)

    # ── 04 全量帧残差 CSV（193x4 全列）────────────────────────────────────
    with (OUT / '04_FRAME_RESIDUALS.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['session', 'ordinal', 'region', 'count',
                                                    'median_m', 'mean_m', 'std_m', 'rms_m',
                                                    'p05_m', 'p95_m'])
        writer.writeheader()
        writer.writerows(frames)

    print('frames rows: %d' % len(frames), flush=True)


def joint_eval_minimal(joint):
    return {'rms_m': joint['rms_m'], 'p95_m': joint['p95_m'],
            'support_fraction': joint['support_fraction']}


if __name__ == '__main__':
    main()
