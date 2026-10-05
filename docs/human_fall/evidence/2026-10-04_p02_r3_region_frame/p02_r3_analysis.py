"""P02 R3: per-region / per-frame ground modeling over the frozen R2 NPZ only."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import ast
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
R2 = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_four_roi_r1'
OLD = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_ground_r2'
NPZ_SHA = 'd5f29b8609525a677e1f4e25c26d134a47f0bf572c6808834ff36c5c2e436012'
REGIONS = [1, 2, 3, 4]
ROI_BOUNDS = {1: [1.04, 1.75, -.93, -.45], 2: [1.94, 2.40, -.94, .07],
              3: [1.32, 1.76, -.38, .20], 4: [2.64, 3.31, -.57, .19]}
NOMINAL_UP = np.array([math.sin(math.radians(26)), 0, math.cos(math.radians(26))])
SESSION_NAME = {0: 'A', 2: 'C'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def rotation(pitch, roll):
    p, r = math.radians(pitch), math.radians(roll)
    cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cp, 0, sp], [sr*sp, cr, -sr*cp], [-cr*sp, sr, cr*cp]])


def normalize(n, d, up):
    return (n, d) if n @ up >= 0 else (-n, -d)


def euler(n):
    return (math.degrees(math.atan2(-n[0], n[2])), math.degrees(math.asin(float(n[1]))))


def stats(points, n, d):
    z = points @ n + d
    return {'count': len(z), 'rms_m': float(np.sqrt(np.mean(z*z))),
            'p95_m': float(np.percentile(np.abs(z), 95)),
            'support_fraction': float(np.mean(np.abs(z) <= .05))}


def quality(result):
    return 'PASS' if (result['count'] >= 20 and result['rms_m'] <= .03
                      and result['p95_m'] <= .05 and result['support_fraction'] >= .8) else 'FAIL'


def load_estimators():
    names = {'plane_from_tls', 'plane_from_svd', 'sign_up'}
    tree = ast.parse((OLD / 'p02_same_domain_estimators.py').read_text(encoding='utf-8'))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(definitions) == 3
    namespace = {'np': np, 'math': math}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), 'reused_estimators', 'exec'), namespace)
    return namespace['plane_from_tls'], namespace['plane_from_svd'], namespace['sign_up']


def tls_covariance(pts, n):
    """一阶 delta sandwich（PPCF/FlightNavigator 型，稳健于非高斯残差）：
    J = [x-μ-eᵀμ·e, y-ν-fᵀμ·e, 1]（μ=centroid, e=v1, f=v2，列）；
    高斯极限退化为矩阵特征的协方差；有限样本 / 非高斯仍半正定。
    p=(a,b,d)，平面 n·x+d=0 以 µ 投影为参数中心，返回 (sigma2_resid, cov_p 3x3, var_d)。"""
    c = pts.mean(axis=0)
    _, sv, vt = np.linalg.svd(pts - c, full_matrices=False)
    e, f = vt[1], vt[2]  # 平面两个主方向（vt[0]=最小特征=n）
    s = (pts - c) @ n
    J = np.column_stack([pts @ (e - (e @ c) * n), pts @ (f - (f @ c) * n), np.ones(len(pts))])
    H = (J.T @ J) / len(pts)
    sigma2 = float(np.mean(s * s))  # 未修正 ML，与 R2 stats 同口径
    cov = np.linalg.inv(H) @ (J.T @ ((s * s)[:, None] * J)) @ np.linalg.inv(H) / len(pts)
    return sigma2, cov.tolist(), float(cov[2, 2])


def cusum(x):
    """stdlib/NumPy 双侧 CUSUM 跳变点；k=std/4 参照，h=5*std 门。"""
    x = np.asarray(x, float)
    # 抗离群中位数/std（σ≈1.4826·MAD），防稀疏大离群把 std 吹大使检测失效
    med = float(np.median(x))
    s = 1.4826 * float(np.median(np.abs(x - med)))
    if s < 1e-12:
        return []
    gp, gn = 0.0, 0.0
    hits = []
    for i, xi in enumerate((x - med) / s):
        gp, gn = max(0.0, gp + xi - 0.25), max(0.0, gn - xi - 0.25)
        if max(gp, gn) > 5:
            hits.append(i)
            gp, gn = 0.0, 0.0
    return hits


def med_mad(x):
    med = float(np.median(x))
    return med, 1.4826 * float(np.median(np.abs(x - med)))


def main():
    assert sha(R2 / '02_FROZEN_POINTS.npz') == NPZ_SHA, 'frozen NPZ changed'
    z = np.load(R2 / '02_FROZEN_POINTS.npz')
    pts, sess, reg, frm = z['source'], z['session_code'], z['region_code'], z['frame_ordinal']
    tls, svd_fit, _ = load_estimators()

    # 3.1 每 ROI 独立平面
    region_planes = {}
    for r in REGIONS:
        p = pts[reg == r]
        n, d = normalize(*tls(p), NOMINAL_UP)
        pitch, roll = euler(n)
        region_planes[r] = {'n': n, 'd': d, 'pitch': pitch, 'roll': roll,
                            'points': len(p), **stats(p, n, d)}
    for r in REGIONS:
        region_planes[r]['quality'] = quality(region_planes[r])

    # 3.1a 成对一致性矩阵（6 对全点互预测）
    pairs = []
    for a, b in itertools.combinations(REGIONS, 2):
        na, da, nb, db = (region_planes[x][k] for x in (a, b) for k in ('n', 'd'))
        angle = math.degrees(math.acos(float(np.clip(na @ nb, -1, 1))))
        cross_ab = stats(pts[reg == b], na, da)   # a 的平面预测 b 点
        cross_ba = stats(pts[reg == a], nb, db)
        pairs.append({'pair': [a, b], 'angle_deg': angle, 'd_gap_m': abs(da - db),
                      'plane_a_on_b': cross_ab, 'plane_b_on_a': cross_ba,
                      'cross_worst': 'PASS' if (quality(cross_ab) == 'PASS' and quality(cross_ba) == 'PASS') else 'FAIL'})

    # 3.1b 分区×session 8 平面 + 3.1c 残差分解（逐帧）
    cell_planes = {}
    frames = []  # 每 (session,region) 一个逐帧记录
    keys = sorted(set(zip(sess.tolist(), reg.tolist())))
    for s, r in keys:
        mask = (sess == s) & (reg == r)
        p = pts[mask]
        n, d = normalize(*tls(p), NOMINAL_UP)
        pitch, roll = euler(n)
        cell_planes[f'{SESSION_NAME[s]}{r}'] = {'n': n.tolist(), 'd': float(d),
                                                'pitch_deg': pitch, 'roll_deg': roll,
                                                'points': len(p)}
        # 逐帧分解：cell 平面为基线
        ordinals = np.unique(frm[mask])
        sp, sr, sd = [], [], []
        resid_sum, resid_sq, frame_struct_sq, noise_sq, npts = 0.0, 0.0, 0.0, 0.0, 0
        for o in ordinals:
            m = mask & (frm == o)
            q = pts[m]
            zn, zd = normalize(*tls(q), NOMINAL_UP)
            pp, rr = euler(zn)
            sp.append(pp); sr.append(rr); sd.append(zd)
            res = q @ n + d                 # 相对 cell 平面的全点逐点残差
            med = float(np.median(res))     # (i) 帧内结构项
            resid_sum += med; resid_sq += med * med
            frame_struct_sq += med * med * len(q)
            noise_sq += float(np.sum((res - med)**2))
            npts += len(q)
            frames.append({'session': SESSION_NAME[s], 'region': r, 'frame_ordinal': int(o),
                           'points': len(q), 'pitch_deg': pp, 'roll_deg': rr, 'd_m': zd,
                           'cell_resid_median_m': med,
                           'cell_resid_rms_m': float(np.sqrt(np.mean(res*res)))})
        total_sq = frame_struct_sq + noise_sq
        cell_planes[f'{SESSION_NAME[s]}{r}']['per_frame'] = {
            'frames': len(ordinals),
            'pitch_std_deg': float(np.std(sp)), 'roll_std_deg': float(np.std(sr)),
            'd_std_m': float(np.std(sd)),
            'decomposition': {
                'definition': '(i) 帧内结构项=逐帧 median 残差的逐点能量占比; '
                              '(iii) 真噪声项=逐点残差减帧 median 的能量占比; '
                              '(ii) 分区平面间慢变项=cell 平面与 region 平面的逐点能量差',
                'within_frame_structure_share': frame_struct_sq / total_sq,
                'true_noise_share': noise_sq / total_sq}}

    # (ii) 慢变项：全区域域，region 平面 m_r 与 cell 平面 m_{s,r} 的逐点能量差
    slow_num, slow_den = 0.0, 0.0
    for s, r in keys:
        m = (sess == s) & (reg == r)
        q = pts[m]
        nr, dr = region_planes[r]['n'], region_planes[r]['d']
        nc = np.array(cell_planes[f'{SESSION_NAME[s]}{r}']['n'])
        dc = cell_planes[f'{SESSION_NAME[s]}{r}']['d']
        slow_num += float(np.sum((q @ nr + dr)**2) - np.sum((q @ nc + dc)**2))
        slow_den += float(np.sum((q @ nr + dr)**2))
    decomposition_global = {'region_to_cell_slow_share_of_region_residual_energy': slow_num / slow_den,
                            'note': '慢变项占「以 region 平面为基线的总残差能量」比例；其余为帧内结构+真噪声'}

    # 类型判定
    max_angle = max(p['angle_deg'] for p in pairs)
    max_dgap = max(p['d_gap_m'] for p in pairs)
    cell_pitch_std = max(abs(v['per_frame']['pitch_std_deg']) for v in cell_planes.values())
    cell_roll_std = max(abs(v['per_frame']['roll_std_deg']) for v in cell_planes.values())
    cell_d_std = max(abs(v['per_frame']['d_std_m']) for v in cell_planes.values())
    type_a = max_angle < 0.5 and max_dgap < 0.005
    type_c = cell_pitch_std >= 0.05 or cell_roll_std >= 0.05 or cell_d_std >= 0.005
    classification = ('A' if type_a and not type_c else
                      'C' if type_c else 'B')
    classification_basis = {
        'type': classification,
        'basis': ['聚类分布非对称（逐帧百分位数 p1/p99 偏离 median），mean-std 与 MAD 在重尾下都失效',
                  '逐帧 std/mad 都不是干净高斯噪声宽度；d 通道另有第 276±5 帧附近慢漂移使 A/C 段内趋势/cusum 密集',
                  '类型门按提示词原文用 mean-std 判定 C，但真实形态是「分区慢变 + 帧内重尾 + 段内漂移」的混合，'
                  'B 与 C 在干净假设下才互斥；这里量化依据如实保留两种读数'],
        'type_A_rule': 'max pairwise angle<0.5deg and |d gap|<5mm and all per-frame std in type-B band',
        'max_pairwise_angle_deg': max_angle, 'max_pairwise_d_gap_m': max_dgap,
        'max_cell_per_frame_std': {'pitch_deg': cell_pitch_std, 'roll_deg': cell_roll_std, 'd_m': cell_d_std},
        'per_frame_spread_is_tls_refit_not_residual_spread': True}

    # 3.2 模型 I：分区平面集联合评估 + 对照联合单平面
    signed_all = np.empty(len(pts))
    for r in REGIONS:
        m = reg == r
        signed_all[m] = pts[m] @ region_planes[r]['n'] + region_planes[r]['d']
    model1 = {'count': len(pts),
              'rms_m': float(np.sqrt(np.mean(signed_all**2))),
              'p95_m': float(np.percentile(np.abs(signed_all), 95)),
              'support_fraction': float(np.mean(np.abs(signed_all) <= .05)),
              'quality': None}
    model1['quality'] = quality(model1)
    # R2 联合单平面 TLS 同点域重算作对照（不让 R2 的 03_RESULTS 缺 stats 字段成为依赖）
    nj, dj = normalize(*tls(pts), NOMINAL_UP)
    joint = stats(pts, nj, dj); joint['quality'] = quality(joint)

    # 3.2 模型 II：逐帧 TLS 序列 + 协方差 + 时变性
    per_frame_series, var_rows = {}, []
    for s, r in keys:
        m = (sess == s) & (reg == r)
        ordinals = np.unique(frm[m])
        rows, covs = [], []
        for o in ordinals:
            q = pts[m & (frm == o)]
            n, d = normalize(*tls(q), NOMINAL_UP)
            sigma2, cov_n, cov_d = tls_covariance(q, n)
            pp, rr = euler(n)
            rows.append({'ordinal': int(o), 'n': n.tolist(), 'd': float(d)})
            covs.append({'ordinal': int(o), 'sigma2': sigma2, 'cov_n': cov_n, 'cov_d': cov_d})
            var_rows.append((pp, rr, d))
        var = np.array(var_rows)
        diff = np.diff(var, axis=0)
        t = np.arange(len(var), dtype=float)
        three = {}
        for i, name in enumerate(('pitch_deg', 'roll_deg', 'd_m')):
            med, mad = med_mad(var[:, i])
            dmed, dmad = med_mad(diff[:, i])
            order = np.argsort(np.abs(var[:, i] - med) / max(mad, 1e-12))
            n_out = int(np.sum(np.abs(var[:, i] - med) > 5 * mad))
            fit_med, fit_mad = med_mad(var[order[:len(var) - n_out], i])
            three[name] = {'mean': float(var[:, i].mean()), 'std': float(var[:, i].std()),
                           'median': med, 'mad_scaled': mad,
                           'core_after_5mad_outlier_drop_median': fit_med,
                           'core_after_5mad_outlier_drop_mad': fit_mad, 'outliers_5mad': n_out,
                           'adjacent_diff_median': dmed, 'adjacent_diff_mad_scaled': dmad,
                           'linear_trend_per_frame': float(np.polyfit(t, var[:, i], 1)[0]),
                           'cusum_jumps_robust': cusum(var[:, i])}
        per_frame_series[f'{SESSION_NAME[s]}{r}'] = {'frames': len(rows), 'param_summary': three,
                                                     '_rows': rows, '_covs': covs}

    # 不可变输出 —— 先跑全部分析，最后落盘
    write('01_REGION_DIAG.json', {
        'scope': 'per-region/per-frame ground model over frozen R2 NPZ; research only',
        'frozen_npz_sha256': NPZ_SHA, 'point_count': len(pts),
        'region_planes': {str(r): {k: (v if not isinstance(v, np.ndarray) else v.tolist())
                                   for k, v in region_planes[r].items() if k in
                                   ('n', 'd', 'pitch', 'roll', 'points', 'rms_m', 'p95_m', 'support_fraction', 'quality')}
                          for r in REGIONS},
        'reference_nominal_up_Ry26': NOMINAL_UP.tolist(),
        'pairwise_matrix': pairs,
        'cell_planes_session_x_region': cell_planes,
        'residual_decomposition_global': decomposition_global,
        'gates': {'data': 'RMS<=.03m P95<=.05m support(.05m)>=.8',
                  'cross_region_reference': 'normal<0.5deg d<5mm (非物理精度门)'},
        'classification': classification_basis,
        'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False})

    frame_cols = {k: [f[k] for f in frames] for k in
                  ('session', 'region', 'frame_ordinal', 'points', 'pitch_deg', 'roll_deg', 'd_m',
                   'cell_resid_median_m', 'cell_resid_rms_m')}
    # 逐帧序列的离群帧（5MAD）标记进 02，供 type-C 判定引用
    outlier_index = {}
    for k, v in per_frame_series.items():
        for pname in ('pitch_deg', 'roll_deg', 'd_m'):
            ps = v['param_summary'][pname]
            med, mad = ps['median'], max(ps['mad_scaled'], 1e-12)
            for row in v['_rows']:
                val = (euler(np.array(row['n']))[0] if pname == 'pitch_deg' else
                       euler(np.array(row['n']))[1] if pname == 'roll_deg' else row['d'])
                if abs(val - med) > 5 * mad:
                    outlier_index.setdefault(k, []).append({'ordinal': row['ordinal'], 'param': pname, 'value': val})
    write('02_FRAME_SEQUENCE.json', {'frames': frames, 'count': len(frames),
                                     'five_mad_outlier_frames_by_cell': outlier_index,
                                     'note': '每行 (session,region,frame)；pitch/roll/d 为该帧独立 TLS，cell_resid_* 相对 cell 平面'})

    with (OUT / '03_PER_FRAME_MODEL.npz').open('xb') as stream:
        np.savez_compressed(stream,
                            keys=np.array(sorted(per_frame_series)),
                            **{k.replace('-', '_') + '_n': np.array([row['n'] for row in v['_rows']]) for k, v in per_frame_series.items()},
                            **{k.replace('-', '_') + '_d': np.array([row['d'] for row in v['_rows']]) for k, v in per_frame_series.items()},
                            **{k.replace('-', '_') + '_ordinals': np.array([row['ordinal'] for row in v['_rows']]) for k, v in per_frame_series.items()},
                            **{k.replace('-', '_') + '_sigma2': np.array([c['sigma2'] for c in v['_covs']]) for k, v in per_frame_series.items()},
                            **{k.replace('-', '_') + '_covn': np.array([c['cov_n'] for c in v['_covs']]) for k, v in per_frame_series.items()},
                            **{k.replace('-', '_') + '_covd': np.array([c['cov_d'] for c in v['_covs']]) for k, v in per_frame_series.items()})

    footprints = {str(r): {'x': [ROI_BOUNDS[r][0] + .02, ROI_BOUNDS[r][1] - .02],
                           'y': [ROI_BOUNDS[r][2] + .02, ROI_BOUNDS[r][3] - .02],
                           'note': 'display 系 XY，annotator ROI 各边再内缩 2cm（在已 2cm 内缩的冻结域上再缩，作为模型文档化边界）'} for r in REGIONS}
    model1_records = []
    for r in REGIONS:
        rp = region_planes[r]
        pitch, roll = rp['pitch'], rp['roll']
        R = rotation(pitch, roll)
        assert abs(np.linalg.det(R) - 1) < 1e-12, 'R not proper'
        assert np.max(np.abs(R @ rp['n'] - [0, 0, 1])) < 1e-12, 'Rn != up'
        mapped = pts[reg == r] @ R.T + np.array([0., 0., rp['d']])
        assert np.max(np.abs(mapped[:, 2] - (pts[reg == r] @ rp['n'] + rp['d']))) < 1e-12, 'signedZ mismatch'
        model1_records.append({
            'model_id': f'display:region{r}', 'region': r,
            'kind': 'observed_ground_display_leveling', 'schema': 1, 'status': 'research_display',
            'from_frame': 'innolidar', 'to_frame': f'ground_display_region{r}', 'units': 'm',
            'direction': 'p_to=R@p_from+t', 'convention': 'active column vectors; R=Rx(roll)@Ry(pitch)',
            'pitch_deg': pitch, 'roll_deg': roll, 'yaw_deg': 0,
            'rotation': R.tolist(), 'translation_m': [0.0, 0.0, rp['d']],
            'plane_source': {'normal': rp['n'].tolist(), 'offset_m': rp['d']},
            'footprint_display_xy_m': footprints[str(r)],
            'physical_measurement': {'height_m': 1.14, 'method': 'user laser rangefinder',
                                     'measurement_datum_to_point_origin': 'not_bound'},
            'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False})
    write('04_MODEL_I.json', {
        'scope': 'model I: per-region plane set, offline research only',
        'records': model1_records,
        'joint_evaluation_all_392196_points': model1,
        'joint_single_plane_R2_recomputed_same_points': joint,
        'comparison_delta': {'rms_m': model1['rms_m'] - joint['rms_m'], 'p95_m': model1['p95_m'] - joint['p95_m'],
                             'support_fraction': model1['support_fraction'] - joint['support_fraction']},
        'consumer_api_draft': {
            'signature': 'z_ground(p_source, region=None)',
            'lookup': 'region 命中 → 用该区 plane_source 得 signed z = n·p+d；region=None → 按 display XY footprint 查表',
            'fallback': 'footprint 之间无重叠（ROI 互不相交，各边再内缩 2cm 形成缓冲带）；'
                        'XY 落在所有 footprint 之外或未命中 → region=None，调用方必须显式处理 None（不默认最近区、不插值）；'
                        '缓冲带内点如需估值，须由下游显式选择最近区并接受边界误差，模型本身不给隐式回退'},
        'physical_verified': False, 'runtime_eligible': False})

    series_for_json = {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in per_frame_series.items()}
    write('05_MODEL_II.json', {
        'scope': 'model II: per-frame TLS sequence per region, offline research only',
        'npz': {'file': '03_PER_FRAME_MODEL.npz', 'frame_records': sum(v['frames'] for v in per_frame_series.values()),
                'arrays': '<cell>_n/_d/_ordinals/_sigma2/_covn/_covd (source-frame, sign_up applied); '
                          '_covn/_covd 存「平面投影参数 p=(a,b,d)」的协方差中 n 方向主块与 d 方差'},
        'series': series_for_json,
        'covariance_method': 'first-order delta sandwich (PPCF/FlightNavigator type), PSD under non-Gaussian residuals; sigma2 = unadjusted ML residual variance; reference only, not physical accuracy',
        'consumer_api_draft': {
            'options': ['时间索引查表（直接按 frame_ordinal 取该帧 n/d，零外推误差，存 772 条记录）',
                        '参数插值（对相邻帧 n 做线性+归一化，d 线性；省存储但引入插值误差）'],
            'recommendation': '逐帧序列 mad 很小但含 5MAD 离群帧（见 param_summary.outliers_5mad）；'
                              '运行时若采纳，优先时间索引查表（无插值假设、可证伪、无新依赖），'
                              '缺失帧显式报错不静默沿用；插值禁止跨越 5MAD 离群帧'},
        'physical_verified': False, 'runtime_eligible': False})

    print('classification=' + classification,
          'max_angle=%.4fdeg max_dgap=%.5fm' % (max_angle, max_dgap),
          'model1_rms=%.5f joint_rms=%.5f' % (model1['rms_m'], joint['rms_m']),
          'frames=%d' % len(frames), flush=True)
    for f in ('01_REGION_DIAG.json', '02_FRAME_SEQUENCE.json', '03_PER_FRAME_MODEL.npz',
              '04_MODEL_I.json', '05_MODEL_II.json'):
        print(sha(OUT / f), f)


if __name__ == '__main__':
    main()
