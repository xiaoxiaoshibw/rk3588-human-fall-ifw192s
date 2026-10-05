# -*- coding: utf-8 -*-
"""P02 R3 分区/逐帧地面建模。输入只有 R2 冻结 02_FROZEN_POINTS.npz；
TLS/SVD 纯函数按 AST 复用（只载定义不运行其 main）。不改 ROI/不裁尾/不调门。"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import ast
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
R2 = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_four_roi_r1'
EST = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_ground_r2'
OUT = Path(__file__).resolve().parent
NPZ_SHA256 = 'd5f29b8609525a677e1f4e25c26d134a47f0bf572c6808834ff36c5c2e436012'
ROI = {1: [1.04, 1.75, -.93, -.45], 2: [1.94, 2.40, -.94, .07],
       3: [1.32, 1.76, -.38, .20], 4: [2.64, 3.31, -.57, .19]}
INNER = {r: [x0 + .02, x1 - .02, y0 + .02, y1 - .02] for r, (x0, x1, y0, y1) in ROI.items()}
GATE = {'rms_m': .03, 'p95_m': .05, 'support_0.05m': .8}
CONSIST = {'angle_deg': .5, 'd_m': .005}  # 分区间一致性参考（非物理精度门）
STATE = {0: 'A', 2: 'C'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def stats(z):
    a = np.abs(z)
    return {'count': int(len(z)), 'rms_m': float(np.sqrt(np.mean(z * z))),
            'p95_m': float(np.percentile(a, 95)),
            'support_fraction_0.05m': float(np.mean(a <= .05))}


def quality(s):
    return ('PASS' if s['count'] >= 20 and s['rms_m'] <= GATE['rms_m']
            and s['p95_m'] <= GATE['p95_m'] and s['support_fraction_0.05m'] >= GATE['support_0.05m']
            else 'FAIL')


def pitch_roll(n):
    return (math.degrees(math.atan2(-n[0], n[2])),
            math.degrees(math.asin(float(np.clip(n[1], -1., 1.)))))


def normalize(n, d, up):
    return (n, d) if n @ up >= 0 else (-n, -d)


def series_report(values):
    v = np.asarray(values)
    diffs = np.diff(v)
    a = np.polyfit(np.arange(len(v)), v, 1)
    cusum = np.cumsum(diffs - diffs.mean())
    spread = max(3., 6. * float(np.std(diffs)))  # ponytail: 阈值CUSUM，>=3防除零；跳变多再换BOCPD
    jumps = [int(i) + 1 for i in np.where(np.abs(diffs) > 4. * np.std(diffs))[0]]
    return {'mean': float(v.mean()), 'std': float(v.std()),
            'adjacent_diff_std': float(diffs.std()), 'linear_trend_per_frame': float(a[0]),
            'trend_total': float(a[0] * (len(v) - 1)),
            'cusum_range': float(cusum.max() - cusum.min()), 'cusum_jump_threshold': spread,
            'cusum_detected_jumps': int(bool((cusum.max() - cusum.min()) > spread)),
            'simple_threshold_jump_frames': jumps}


def main():
    for name in ['01_BASELINE.json', '02_REGIONAL_DIAGNOSTICS.json', '03_MODEL1_REGIONAL.json',
                 '04_MODEL2_PER_FRAME.json', '05_MODEL2_PER_FRAME.npz',
                 '06_RESIDUAL_SEQUENCES.npz', '07_REPORT.md', '08_MANIFEST.json']:
        assert not (OUT / name).exists(), 'immutable output exists: ' + name
    assert sha(R2 / '02_FROZEN_POINTS.npz') == NPZ_SHA256, 'frozen NPZ drift'
    r2 = json.loads((R2 / '03_RESULTS.json').read_text(encoding='utf-8'))
    sel = json.loads((R2 / '02_SELECTION.json').read_text(encoding='utf-8'))
    up = np.array(r2['estimators']['tls']['rotation']) @ np.array(r2['estimators']['tls']['normal_source'])
    assert np.max(np.abs(up - [0, 0, 1])) < 1e-12  # Rn=up 复核
    frozen = np.load(R2 / '02_FROZEN_POINTS.npz')
    points, rr = frozen['source'], frozen['source_rows']
    cc, rg, ff = frozen['session_code'], frozen['region_code'], frozen['frame_ordinal']
    assert len(points) == 392196 and hashlib.sha256(points.tobytes()).hexdigest() == sel['point_sha256']
    assert hashlib.sha256(rr.tobytes()).hexdigest() == sel['row_sha256']
    assert set(np.unique(cc)) == {0, 2} and set(np.unique(rg)) == {1, 2, 3, 4}
    for c in [0, 2]:  # 行号只在 session 内唯一（R2 同口径）
        assert len(np.unique(rr[cc == c])) == int((cc == c).sum()), 'duplicate source rows in session ' + STATE[c]

    # AST 复用 R2 已审 pure 函数，只载定义
    tree = ast.parse((EST / 'p02_same_domain_estimators.py').read_text(encoding='utf-8'))
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'plane_from_tls']
    assert len(defs) == 1
    ns = {'np': np, 'math': math}
    exec(compile(ast.Module(body=defs, type_ignores=[]), 'reused_tls', 'exec'), ns)
    fit = ns['plane_from_tls']

    regions = sorted(ROI)
    planes = {}
    for r in regions:
        n, d = normalize(*fit(points[rg == r]), up)
        planes[r] = (n, d)
    baseline_n = np.array(r2['estimators']['tls']['normal_source'])
    baseline_d = float(r2['estimators']['tls']['d_source_m'])

    # ── 3.1a 成对一致性矩阵（6 对，全点互预测）──────────────────────────
    pairs = []
    for i, a in enumerate(regions):
        for b in regions[i + 1:]:
            na, da = planes[a]
            nb, db = planes[b]
            angle = math.degrees(math.acos(float(np.clip(abs(na @ nb), -1., 1.))))
            entry = {'pair': [a, b], 'normal_angle_deg': angle, 'd_diff_m': abs(float(da - db)),
                     'angle_within_ref': angle <= CONSIST['angle_deg'],
                     'd_within_ref': abs(float(da - db)) <= CONSIST['d_m']}
            for (src, dst) in [(a, b), (b, a)]:
                ns_, ds_ = planes[src]
                z = points @ ns_ + ds_
                s = stats(z[rg == dst])
                entry['plane%d_predicts_region%d' % (src, dst)] = {**s, 'quality': quality(s)}
            pairs.append(entry)
    pairwise_gate_all = all(e['angle_within_ref'] and e['d_within_ref'] for e in pairs)

    # ── 3.1b 8 个 region×session 平面 + 逐帧残差序列（193×4 全列）──────────
    eight = []
    res_slices = []
    offset = 0
    seq = []  # 逐帧全点残差序列（float32 存盘）
    for c in [0, 2]:
        for r in regions:
            mask = (cc == c) & (rg == r)
            n, d = normalize(*fit(points[mask]), up)
            p_, r_ = pitch_roll(n)
            idx = np.where(mask)[0]
            frames = sorted(set(ff[idx].tolist()))
            entry = {'session': STATE[c], 'region': r, 'frames': len(frames),
                     'normal_source': n.tolist(), 'd_source_m': float(d),
                     'pitch_deg': p_, 'roll_deg': r_,
                     'points': int(mask.sum())}
            # 逐帧：TLS 序列 + 残差序列（全列）
            fs, fn_, fd_, fp_, fr_ = [], [], [], [], []
            frame_pitch, frame_roll = [], []
            for f in frames:
                fm = idx[ff[idx] == f]
                nff, dff = normalize(*fit(points[fm]), up)
                pff, rff = pitch_roll(nff)
                z = points[fm] @ n + d
                seq.append(z.astype(np.float32))
                res_slices.append({'session': STATE[c], 'region': r, 'frame_ordinal': int(f),
                                   'slice': [offset, offset + len(z)]})
                offset += len(z)
                fs.append(int(f)); fn_.append(dff); fp_.append(pff); fr_.append(rff)
                frame_pitch.append(pff); frame_roll.append(rff)
            entry['per_frame_tls'] = {'pitch_std_deg': float(np.std(frame_pitch)),
                                      'roll_std_deg': float(np.std(frame_roll)),
                                      'd_std_m': float(np.std(fn_))}
            entry['per_frame_series'] = {'frames': fs, 'pitch_deg': fp_, 'roll_deg': fr_, 'd_m': fn_}
            eight.append(entry)
    seq_all = np.concatenate(seq)
    assert offset == len(points) == len(seq_all)

    # ── 3.1c 残差分解：全残差 = 结构项 + 慢变项 + 真噪声 ─────────────────
    med_frames = seq_all[rr]          # 帧 median（结构项）
    noise = seq_all - med_frames      # 真噪声项
    drift = med_frames.copy()         # 慢变项 = med_frames − E[med|region,session]
    grand_med = {}
    for c in [0, 2]:
        for r in regions:
            sel_ = (cc[rr] == c) & (rg[rr] == r)
            grand_med[(c, r)] = float(np.median(med_frames[sel_]))
            drift[sel_] = med_frames[sel_] - grand_med[(c, r)]
    assert np.max(np.abs(seq_all - (drift + grand_med_arr(cc[rr], rg[rr], grand_med) + noise))) < 1e-5
    check = drift + grand_med_arr(cc[rr], rg[rr], grand_med) + noise
    assert np.max(np.abs(seq_all - check)) < 1e-5
    sigma2 = {'total': float(np.var(seq_all)),
              'structure': float(np.var(seq_all)),  # 下方覆盖
              'drift': float(np.var(drift)), 'noise': float(np.var(noise)),
              'offset': float(np.mean(seq_all) ** 2)}
    mean_structure = float(np.mean(seq_all))
    sigma2['structure'] = float(np.var(seq_all) - np.var(noise) - np.var(drift))
    share = {k: v / sigma2['total'] for k, v in sigma2.items() if k != 'total'}

    # ── 3.1d 类型判定 ────────────────────────────────────────────────────
    max_angle = max(e['normal_angle_deg'] for e in pairs)
    max_ddiff = max(e['d_diff_m'] for e in pairs)
    max_pitch_std = max(e['per_frame_tls']['pitch_std_deg'] for e in eight)
    max_roll_std = max(e['per_frame_tls']['roll_std_deg'] for e in eight)
    max_d_std = max(e['per_frame_tls']['d_std_m'] for e in eight)
    if max_angle < .5 and max_ddiff < .005:
        cls = 'A'
    elif max_pitch_std < .05 and max_roll_std < .05 and max_d_std < .005:
        cls = 'B'
    else:
        cls = 'C'
    cls_basis = {'max_pairwise_normal_angle_deg': max_angle, 'max_pairwise_d_diff_m': max_ddiff,
                 'max_per_frame_pitch_std_deg': max_pitch_std, 'max_per_frame_roll_std_deg': max_roll_std,
                 'max_per_frame_d_std_m': max_d_std,
                 'classification': cls,
                 'rule': 'A: angle<0.5deg 且 d<5mm；否则 B: 分区差异越界但区内逐帧 std<0.05deg/<5mm；否则 C'}

    write('02_REGIONAL_DIAGNOSTICS.json',
          {'scope': '3.1 分区诊断；输入只有 R2 冻结 NPZ；门同 R2；FAIL 保留',
           'frozen_input_sha256': NPZ_SHA256, 'gates': GATE, 'consistency_reference': CONSIST,
           'per_region_planes': {str(r): {'normal_source': planes[r][0].tolist(),
                                          'd_source_m': float(planes[r][1]),
                                          'pitch_deg': pitch_roll(planes[r][0])[0],
                                          'roll_deg': pitch_roll(planes[r][0])[1],
                                          'points': int((rg == r).sum()),
                                          'vs_joint_single_plane': {
                                              'normal_angle_deg': math.degrees(math.acos(float(np.clip(abs(planes[r][0] @ baseline_n), -1., 1.)))),
                                              'd_diff_m': abs(float(planes[r][1] - baseline_d))}}
                                 for r in regions},
           'pairwise_6': pairs, 'pairwise_consistency_all_within_ref': pairwise_gate_all,
           'eight_region_session_planes': eight,
           'residual_slices': res_slices,
           'decomposition': {'identity': 'residual = drift + grand_mean_structure + noise (frame-median basis, exact)',
                             'grand_mean_structure_by_session_region': {STATE[c] + str(r): grand_med[(c, r)]
                                                                         for c in [0, 2] for r in regions},
                             'variances_m2': sigma2, 'share_of_total': share},
           'classification': cls_basis})

    # ── 3.2 模型 I：分区平面集 ───────────────────────────────────────────
    z1 = np.empty(len(points))
    for r in regions:
        z1[rg == r] = points[rg == r] @ planes[r][0] + planes[r][1]
    m1 = stats(z1)
    m1['quality'] = quality(m1)
    m1_per = {str(r): stats(z1[rg == r]) for r in regions}
    for s in m1_per.values():
        s['quality'] = quality(s)
    z0 = points @ baseline_n + baseline_d
    m0 = stats(z0)
    model1 = {'status': 'research_display', 'physical_verified': False, 'extrinsics_verified': False,
              'runtime_eligible': False, 'frame': 'source frame, same convention as R2 01_DISPLAY_MODEL',
              'planes': [{'region': r, 'normal_source': planes[r][0].tolist(), 'd_source_m': float(planes[r][1]),
                          'footprint_display_xy_inner_m': INNER[r], 'footprint_rule': 'annotator ROI 内缩 2cm',
                          'points': int((rg == r).sum())} for r in regions],
              'joint_evaluation': {'model1_regional_all_points': m1, 'per_region': m1_per,
                                   'r2_single_plane_all_points': {**m0, 'quality': quality(m0)},
                                   'comparison': 'same 392196 frozen points; regional planes vs R2 joint single TLS plane'},
              'consumer_interface_draft': {
                  'signature': 'z_ground(p_source, region) = p @ planes[region].n + planes[region].d',
                  'lookup': 'region 由 annotator ROI 内缩 2cm 的显示系 XY footprint 判定（与 R2 冻结同源）',
                  'fallback_rules': ['footprint 互不重叠（2cm 内缩带即隔离带），不存在重叠命中',
                                     '未命中任何 footprint：无回退平面，报 ground_unavailable；'
                                     '不允许静默退回单平面（那会把未标定区域标成已标定）',
                                     '点恰在隔离带：按未命中处理'],
                  'note': '回退规则是草案；实施另开工单，本轮不接运行时'}}
    write('03_MODEL1_REGIONAL.json', model1)

    # ── 3.2 模型 II：逐帧 TLS 序列（193×4，SVD 参数协方差）────────────────
    rec_n = np.zeros((193, 4, 3)); rec_d = np.zeros((193, 4))
    rec_cov = np.zeros((193, 4, 3, 3)); rec_var = np.zeros((193, 4, 3)); rec_rms = np.zeros((193, 4))
    rec_pts = np.zeros((193, 4), dtype=np.int64)
    frame_keys = []
    row = 0
    for c in [0, 2]:
        for f in range(91 if c == 0 else 102):
            for j, r in enumerate(regions):
                m = (cc == c) & (rg == r) & (ff == f)
                pts = points[m]
                cen = pts.mean(axis=0)
                _, sv, vt = np.linalg.svd(pts - cen, full_matrices=False)
                n, d = normalize(vt[-1], -float(vt[-1] @ cen), up)
                z = pts @ n + d
                var_n = float(np.sum(z * z)) / (len(pts) - 3)
                V = vt.T
                cov = var_n * V @ np.diag(1. / sv ** 2) @ V.T
                rec_n[row, j], rec_d[row, j] = n, d
                rec_cov[row, j] = cov; rec_var[row, j] = np.diag(cov)
                rec_rms[row, j] = float(np.sqrt(np.mean(z * z)))
                rec_pts[row, j] = len(pts)
            frame_keys.append({'session': STATE[c], 'frame_ordinal': f})
            row += 1
    assert row == 193
    var_stats = {k: {'min': float(rec_var[:, :, i].min()), 'max': float(rec_var[:, :, i].max()),
                     'median': float(np.median(rec_var[:, :, i]))}
                 for i, k in enumerate(['nx', 'ny', 'nz'])}
    time_var = {}
    for j, r in enumerate(regions):
        p_, r_ = zip(*[pitch_roll(rec_n[row, j]) for row in range(193)])
        time_var['region%d' % r] = {'pitch_deg': series_report(p_), 'roll_deg': series_report(r_),
                                    'd_m': series_report(rec_d[:, j])}
    with (OUT / '05_MODEL2_PER_FRAME.npz').open('xb') as stream:
        np.savez_compressed(stream, frame_keys=np.array([(k['session'], k['frame_ordinal']) for k in frame_keys],
                                                        dtype=[('session', 'U1'), ('ordinal', '<i4')]),
                            region_codes=np.array(regions, dtype=np.uint8),
                            normal_source=rec_n, d_source_m=rec_d,
                            param_covariance=rec_cov, param_variance=rec_var,
                            rms_m=rec_rms, point_count=rec_pts)
    write('04_MODEL2_PER_FRAME.json',
          {'status': 'research_display', 'physical_verified': False, 'extrinsics_verified': False,
           'runtime_eligible': False,
           'layout': 'rows=A0..A90,C0..C101 全 193 帧；cols=region 1..4；frame_keys/region_codes 在 NPZ',
           'param_variance_summary': var_stats,
           'time_variability_per_region': time_var,
           'consumer_interface_draft': {
               'options': ['时间索引查表：按 (session, ordinal) 精确取该行；简单、无插值误差，'
                           '但逐帧参数含噪声（见 param_variance），相邻帧差分 std 即抖动用限',
                           '参数插值：平滑抖动，但跳变点处会把两个真实平面混合成不存在的中间平面'],
               'draft_choice': '查表为主；仅在确认无跳变（CUSUM 全 0）且噪声主导时允许短时滑动平均，'
                               '插值跨越 CUSUM 跳变点明确禁止',
               'note': '草案；实施另开工单'}})

    with (OUT / '06_RESIDUAL_SEQUENCES.npz').open('xb') as stream:
        np.savez_compressed(stream, residual_m=seq_all,
                            slice_table=np.array([(s['session'], s['region'], s['frame_ordinal'],
                                                   s['slice'][0], s['slice'][1]) for s in res_slices],
                                                 dtype=[('session', 'U1'), ('region', '<u1'),
                                                        ('ordinal', '<i4'), ('lo', '<i8'), ('hi', '<i8')]))

    # ── 自检 + 回算精度 ──────────────────────────────────────────────────
    zr = np.load(OUT / '06_RESIDUAL_SEQUENCES.npz')['residual_m']
    assert np.max(np.abs(zr.astype(np.float64) - seq_all)) < 1e-6
    r2_per_frame = r2['per_frame_TLS']
    mine = {(s['session'], s['region'], f): None for s in eight for f in s['per_frame_series']['frames']}
    mae = []
    r2_idx = {(f['state'], f['ordinal']): (f['pitch_deg'], f['roll_deg'], f['source_d_m']) for f in r2_per_frame}
    for s in eight:
        for k, f in enumerate(s['per_frame_series']['frames']):
            p0, r0, d0 = r2_idx[(s['session'], f)]
            mae.append(max(abs(s['per_frame_series']['pitch_deg'][k] - p0),
                           abs(s['per_frame_series']['roll_deg'][k] - r0)))
    print('max |R3 union-fit vs R2 per-frame TLS| deg = %.3e' % max(mae))
    print('classification = %s; pairwise_ref_all=%s' % (cls, pairwise_gate_all))
    print('decomposition share: %s' % json.dumps(share))
    print('model1 joint rms=%.6f p95=%.6f vs single rms=%.6f p95=%.6f'
          % (m1['rms_m'], m1['p95_m'], m0['rms_m'], m0['p95_m']))
    return 0


def grand_med_arr(cc_, rg_, gm):
    out = np.empty(len(cc_))
    for (c, r), v in gm.items():
        out[(cc_ == c) & (rg_ == r)] = v
    return out


if __name__ == '__main__':
    raise SystemExit(main())
