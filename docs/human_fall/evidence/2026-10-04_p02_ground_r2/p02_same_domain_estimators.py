# -*- coding: utf-8 -*-
"""P02-C/D/E 同点集估计器对照（一次性研究脚本，不接运行时）。

输入：annotator.html:76 当前 #3 VAL = X[1.30,1.78] Y[-0.40,0.22]（显示系），
      显示变换 R=Ry(+26°), tz=+1.340m（annotator.html:69,87 buildMatrix）。
选择规则（拟合前冻结，不按残差裁剪）：A/C 全部帧、2cm 边界内缩、
finite 且非全零源行、全高度保留；B 只作因果核验，不进拟合。
估计器（全部吃同一 float64 数组）：
  RANSAC  = 861 次三点假设全域评分（阈值 .05m、seed 20261001，引用 ground.py:307-310），
            最大支持 / 同分取全域 median 残差最小；不做 inlier 精修。
  TLS     = covariance eigh（ground_diagnostics.pca_plane 同型原语）。
  SVD     = centered thin SVD。
  统一 n 符号 n_z>=0（TLS/SVD 同型实现，不称独立物理证据）。
输出：01_SELECTION.json / 02_ESTIMATORS.json / 03_CANDIDATE.json。
拒绝覆盖既有产物；不修改任何输入/旧证据/生产文件。
"""
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
INV_PATH = os.path.join(ROOT, 'docs', 'human_fall', 'evidence',
                        '2026-10-04_p02_context_r1', '03_SESSION_INVENTORY.json')
ACC_PATH = os.path.join(ROOT, 'docs', 'human_fall', 'P02_ACCEPTANCE.md')
ANNOTATOR = os.path.join(ROOT, 'pc_apps', 'human_replay', 'annotator.html')

SESS = {'A': 'cap_20261004_202456', 'B': 'cap_20261004_203135', 'C': 'cap_20261004_203349'}

# 冻结 ROI（显示系）与 2cm 边界内缩（拟合前声明，排除边界带，非残差门）
ROI_DISPLAY = {'X': [1.30, 1.78], 'Y': [-0.40, 0.22], 'source': 'annotator.html:76 #3 VAL pick_04'}
SHRINK_M = 0.02
ROI_FIT = {'X': [1.32, 1.76], 'Y': [-0.38, 0.20]}

# 显示变换（annotator.html buildMatrix: R=Ry(+26°), 后 z += tz）
PITCH_RAD = 26.0 * math.pi / 180.0
TZ = 1.340

# RANSAC 冻结参数（ground.py CONSTRAINED_DEFAULT_SETTINGS:307-310）
RANSAC_ITERS = 861
RANSAC_SEED = 20261001
INLIER_THRESHOLD_M = 0.05

# 工程一致性参考（P02_ACCEPTANCE.md P02-D 行：2° / .03m，非物理精度）
REF_ANGLE_DEG = 2.0
REF_OFFSET_M = 0.03

# B 因果核验窗（仅诊断）
FLOOR_WINDOW = [-0.10, 0.10]
RAISED_WINDOW = [0.15, 0.35]

OUTS = ['01_SELECTION.json', '02_ESTIMATORS.json', '03_CANDIDATE.json']
for name in OUTS:
    assert not os.path.exists(os.path.join(HERE, name)), name + ' exists, refuse overwrite'

CP, SP = math.cos(PITCH_RAD), math.sin(PITCH_RAD)


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sha256_of(path_or_bytes):
    h = hashlib.sha256()
    if isinstance(path_or_bytes, (bytes, bytearray)):
        h.update(path_or_bytes)
    else:
        with open(path_or_bytes, 'rb') as f:
            for c in iter(lambda: f.read(1 << 20), b''):
                h.update(c)
    return h.hexdigest()


def plane_from_ransac(pts):
    """861 次三点假设，全域评分；同分取全域 median 残差更小者；不精修。"""
    rng = np.random.RandomState(RANSAC_SEED % (2 ** 32))
    n = len(pts)
    best_count, best_median, best_n, best_d = -1, math.inf, None, None
    for _ in range(RANSAC_ITERS):
        sample = pts[rng.randint(0, n, 3)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ sample[0])
        dist = np.abs(pts @ normal + offset)
        count = int(np.count_nonzero(dist <= INLIER_THRESHOLD_M))
        if count > best_count or (count == best_count and float(np.median(dist)) < best_median):
            best_count, best_median, best_n, best_d = count, float(np.median(dist)), normal, offset
    assert best_n is not None, 'RANSAC found no valid hypothesis'
    return best_n, best_d, best_count


def plane_from_tls(pts):
    """covariance eigh（ground_diagnostics.pca_plane 同型）。"""
    centroid = pts.mean(axis=0)
    cov = np.cov((pts - centroid).T)
    w, v = np.linalg.eigh(cov)
    normal = v[:, 0]
    offset = -float(normal @ centroid)
    return normal, offset


def plane_from_svd(pts):
    """centered thin SVD（ground.py:252-255 同型）。"""
    centroid = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centroid, full_matrices=False)
    normal = vt[-1]
    offset = -float(normal @ centroid)
    return normal, offset


def sign_up(normal, offset):
    if normal[2] < 0.0:
        return -normal, -offset
    return normal, offset


def domain_stats(pts, normal, offset):
    d = pts @ normal + offset
    ad = np.abs(d)
    return {
        'rms_m': float(np.sqrt(np.mean(d ** 2))),
        'p95_abs_m': float(np.percentile(ad, 95)),
        'mad_m': float(np.median(ad)),
        'support_count_0.05m': int(np.count_nonzero(ad <= INLIER_THRESHOLD_M)),
        'support_fraction_0.05m': float(np.count_nonzero(ad <= INLIER_THRESHOLD_M) / len(pts)),
    }


def angle_deg(n1, n2):
    return math.degrees(math.acos(float(np.clip(abs(float(n1 @ n2)), -1.0, 1.0))))


def main():
    baseline = load_json(os.path.join(HERE, '00_BASELINE.json'))
    inv = {s['session']: s for s in load_json(INV_PATH)}
    base_files = {os.path.normcase(k): v for k, v in baseline['files'].items()}

    # ── 输入 SHA 复核（与 00 基线逐个一致，不隐式 fallback）──────────────
    sha_check = {}
    for label in ('A', 'B', 'C'):
        sdir = inv[SESS[label]]['path']
        for name in ('meta.json', 'points.bin'):
            p = os.path.join(sdir, name)
            cur = sha256_of(p)
            exp = base_files[os.path.normcase(os.path.abspath(p))]['sha256']
            assert cur == exp, 'input drift: ' + p
            sha_check[p] = cur

    # ── 选择与冻结 ────────────────────────────────────────────────────────
    selection = {
        'roi_definition': ROI_DISPLAY,
        'roi_fit_shrunk': ROI_FIT, 'shrink_m': SHRINK_M,
        'display_transform': {'R': 'Ry(+26deg)', 'tz_m': TZ,
                              'matrix_rowmajor': [[CP, 0, SP, 0], [0, 1, 0, 0], [-SP, 0, CP, TZ], [0, 0, 0, 1]],
                              'source': 'annotator.html:69,87,94-106 buildMatrix'},
        'annotator_sha256': base_files[os.path.normcase(os.path.abspath(ANNOTATOR))]['sha256'],
        'rules': ['A/C all frames 0..N-1', 'finite & nonzero source rows',
                  'full-height kept, no fit-Z/residual gate', 'B excluded from fitting'],
    }
    selected = {}   # label -> (xyz_display_float64, row_index_float64)
    causal_diag = {}
    for label in ('A', 'B', 'C'):
        sdir = inv[SESS[label]]['path']
        meta = load_json(os.path.join(sdir, 'meta.json'))
        assert meta['point_stride_bytes'] == 28 and meta['sensor']['frame_id'] == 'innolidar'
        raw = np.memmap(os.path.join(sdir, 'points.bin'), dtype=np.uint8, mode='r')
        assert len(raw) == meta['total_points'] * 28
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        keep_pts, keep_rows = [], []
        floor_counts, raised_counts = [], []
        for ordinal, fr in enumerate(meta['frames']):
            lo = fr['offset_points']; hi = lo + fr['count_points']
            pts = xyz[lo:hi].astype(np.float64)
            rows = np.arange(lo, hi, dtype=np.int64)
            ok = np.isfinite(pts).all(axis=1) & np.any(pts != 0.0, axis=1)
            pts, rows = pts[ok], rows[ok]
            x = CP * pts[:, 0] + SP * pts[:, 2]
            y = pts[:, 1]
            z = -SP * pts[:, 0] + CP * pts[:, 2] + TZ
            in_roi = ((x >= ROI_FIT['X'][0]) & (x <= ROI_FIT['X'][1]) &
                      (y >= ROI_FIT['Y'][0]) & (y <= ROI_FIT['Y'][1]))
            if label in ('A', 'C'):
                keep_pts.append(np.column_stack([x[in_roi], y[in_roi], z[in_roi]]))
                keep_rows.append(rows[in_roi])
            floor_counts.append(int(np.count_nonzero(in_roi & (z >= FLOOR_WINDOW[0]) & (z <= FLOOR_WINDOW[1]))))
            raised_counts.append(int(np.count_nonzero(in_roi & (z >= RAISED_WINDOW[0]) & (z <= RAISED_WINDOW[1]))))
        causal_diag[label] = {
            'floor_window_median_per_frame': float(np.median(floor_counts)),
            'raised_window_median_per_frame': float(np.median(raised_counts)),
            'frames': len(meta['frames']),
        }
        if label in ('A', 'C'):
            selected[label] = (np.vstack(keep_pts), np.concatenate(keep_rows))
            selection[label] = {
                'session': SESS[label], 'frames_used': len(meta['frames']),
                'ordinal_range': [0, len(meta['frames']) - 1],
                'points_selected': int(len(selected[label][0])),
                'row_index_sha256': sha256_of(selected[label][1].tobytes()),
                'points_xyz_display_sha256': sha256_of(selected[label][0].tobytes()),
                'z_range_m': [float(selected[label][0][:, 2].min()), float(selected[label][0][:, 2].max())],
            }
        else:
            selection[label] = {'session': SESS[label], 'role': 'causal check only, excluded from fitting',
                                'frames': len(meta['frames'])}

    # ── 联合同点集（A91 帧 + C102 帧，行序固定：A 帧序→行序，C 帧序→行序）──
    joint = np.vstack([selected['A'][0], selected['C'][0]]).astype(np.float64)
    joint_rows = np.concatenate([selected['A'][1], selected['C'][1]])
    joint_info = {
        'points_total': int(len(joint)),
        'points_sha256': sha256_of(joint.tobytes()),
        'row_index_sha256': sha256_of(joint_rows.tobytes()),
        'order': 'A frames 0..90 then C frames 0..101, in-frame row order',
    }

    # ── 三估计器同域拟合 ──────────────────────────────────────────────────
    results = {}
    for name, fn in (('ransac', None), ('tls', plane_from_tls), ('svd', plane_from_svd)):
        if name == 'ransac':
            n_vec, d_off, support = plane_from_ransac(joint)
        else:
            n_vec, d_off = fn(joint)
            support = None
        n_vec, d_off = sign_up(n_vec, d_off)
        entry = {'normal': [float(v) for v in n_vec], 'offset_m': float(d_off),
                 'n_z': float(n_vec[2])}
        entry.update(domain_stats(joint, n_vec, d_off))
        if support is not None:
            entry['ransac_hypothesis_support'] = support
        results[name] = entry

    # ── pairwise 一致性 ──────────────────────────────────────────────────
    names = ['ransac', 'tls', 'svd']
    pairs = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = results[names[i]], results[names[j]]
            key = names[i] + '_vs_' + names[j]
            pairs[key] = {
                'angle_deg': angle_deg(np.array(a['normal']), np.array(b['normal'])),
                'delta_d_m': abs(a['offset_m'] - b['offset_m']),
                'angle_within_2deg_ref': angle_deg(np.array(a['normal']), np.array(b['normal'])) <= REF_ANGLE_DEG,
                'offset_within_0.03m_ref': abs(a['offset_m'] - b['offset_m']) <= REF_OFFSET_M,
            }
    consensus_pass = all(p['angle_within_2deg_ref'] and p['offset_within_0.03m_ref'] for p in pairs.values())

    # ── 逐帧 TLS spread（A/C 分别，同 ROI 规则；姿态在拟合系解算，与 candidate 同系）──
    per_frame = {}
    for label in ('A', 'C'):
        sdir = inv[SESS[label]]['path']
        meta = load_json(os.path.join(sdir, 'meta.json'))
        raw = np.memmap(os.path.join(sdir, 'points.bin'), dtype=np.uint8, mode='r')
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        rows_pitch, rows_roll, rows_d = [], [], []
        for ordinal, fr in enumerate(meta['frames']):
            lo = fr['offset_points']; hi = lo + fr['count_points']
            pts = xyz[lo:hi].astype(np.float64)
            ok = np.isfinite(pts).all(axis=1) & np.any(pts != 0.0, axis=1)
            pts = pts[ok]
            x = CP * pts[:, 0] + SP * pts[:, 2]
            y = pts[:, 1]
            z = -SP * pts[:, 0] + CP * pts[:, 2] + TZ
            in_roi = ((x >= ROI_FIT['X'][0]) & (x <= ROI_FIT['X'][1]) &
                      (y >= ROI_FIT['Y'][0]) & (y <= ROI_FIT['Y'][1]))
            fp = np.column_stack([x[in_roi], y[in_roi], z[in_roi]])
            assert len(fp) >= 10, 'frame %d of %s has only %d ROI points' % (ordinal, label, len(fp))
            n_vec, d_off = sign_up(*plane_from_tls(fp))
            rows_pitch.append(math.degrees(math.atan2(-n_vec[0], n_vec[2])))
            rows_roll.append(math.degrees(math.asin(float(np.clip(n_vec[1], -1.0, 1.0)))))
            rows_d.append(d_off)
        per_frame[label] = {
            'pitch_deg': {'min': float(min(rows_pitch)), 'max': float(max(rows_pitch)),
                          'std': float(np.std(rows_pitch)), 'mean': float(np.mean(rows_pitch))},
            'roll_deg': {'min': float(min(rows_roll)), 'max': float(max(rows_roll)),
                         'std': float(np.std(rows_roll)), 'mean': float(np.mean(rows_roll))},
            'offset_m': {'min': float(min(rows_d)), 'max': float(max(rows_d)),
                         'std': float(np.std(rows_d)), 'mean': float(np.mean(rows_d))},
            'frames': len(rows_pitch),
        }
    state_spread = {
        'pitch_deg_mean_abs_A_minus_C': abs(per_frame['A']['pitch_deg']['mean'] - per_frame['C']['pitch_deg']['mean']),
        'roll_deg_mean_abs_A_minus_C': abs(per_frame['A']['roll_deg']['mean'] - per_frame['C']['roll_deg']['mean']),
        'offset_m_mean_abs_A_minus_C': abs(per_frame['A']['offset_m']['mean'] - per_frame['C']['offset_m']['mean']),
    }

    # ── 输出 01/02 ────────────────────────────────────────────────────────
    sel_doc = dict(selection)
    sel_doc['joint'] = joint_info
    sel_doc['causal_check_B_vs_AC'] = causal_diag
    sel_doc['input_sha_check'] = sha_check
    with open(os.path.join(HERE, '01_SELECTION.json'), 'w', encoding='utf-8') as f:
        json.dump(sel_doc, f, ensure_ascii=False, indent=1)

    est_doc = {
        'input_joint_points_sha256': joint_info['points_sha256'],
        'frozen_constants': {'ransac_iterations': RANSAC_ITERS, 'seed': RANSAC_SEED,
                             'inlier_threshold_m': INLIER_THRESHOLD_M,
                             'source': 'ground.py CONSTRAINED_DEFAULT_SETTINGS:307-310'},
        'estimators': results,
        'pairwise': pairs,
        'engineering_reference': {'angle_deg': REF_ANGLE_DEG, 'offset_m': REF_OFFSET_M,
                                  'meaning': '一致性参考，非物理精度声明'},
        'consensus_within_reference': consensus_pass,
        'per_frame_tls': per_frame,
        'state_spread_A_vs_C': state_spread,
        'notes': ['TLS 与 SVD 为同一正交最小二乘问题的两种数值实现，不构成独立物理证据',
                  '193 帧为已曝光训练/稳定性域，非未见 holdout',
                  '无 offset gate、无 inlier 精修、无点 cap、三法同一 float64 输入'],
    }
    with open(os.path.join(HERE, '02_ESTIMATORS.json'), 'w', encoding='utf-8') as f:
        json.dump(est_doc, f, ensure_ascii=False, indent=1)

    # ── 03 research candidate（仅 consensus PASS 时生成）───────────────────
    if not consensus_pass:
        print('CONSENSUS FAIL — E NOT_RUN, 03 not emitted')
        return 1

    tls_n = np.array(results['tls']['normal']); tls_d = results['tls']['offset_m']
    # 几何契约（ground frame）：pitch=atan2(-nx,nz)、roll=asin(ny)、tz=d 是
    # 把"该平面"在数学世界系（Z 向上）转平的外参，不是雷达安装角。
    # 拟合域在显示系，直接对显示系法向解姿态即可——Rn≈[0,0,1] 与
    # groundZ=n·p+d 恰好在同一坐标系闭合；不乘 R_disp（那会把 annotator 的
    # 名义 26° 安装配平重新叠加进结果，把研究候选错标成安装测量）。
    n_fit = tls_n
    pitch = math.atan2(-n_fit[0], n_fit[2])
    roll = math.asin(float(np.clip(n_fit[1], -1.0, 1.0)))
    tz = tls_d
    Rx = np.array([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
    Ry = np.array([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
    R = Rx @ Ry
    det = float(np.linalg.det(R))
    orth = float(np.abs(R @ R.T - np.eye(3)).max())
    Rn = R @ n_fit
    z_ground = (R @ joint.T).T[:, 2] + tz  # = n_fit·p + d（理论恒等，实算验证）

    cand = {
        'kind': 'research_candidate', 'runtime_eligible': False,
        'frame': 'annotator display frame (Ry(+26°), tz=+1.340 已施加的数学世界系)；'
                 'pitch/roll/tz 是"把该平面在此系转平"的外参，不是雷达安装角',
        'pose': {'pitch_deg': float(math.degrees(pitch)), 'roll_deg': float(math.degrees(roll)),
                 'tz_m': float(tz), 'yaw': 0.0, 'tx': 0.0, 'ty': 0.0},
        'R_rowmajor': [[float(v) for v in row] for row in R],
        't': [0.0, 0.0, float(tz)],
        'normal_fit_frame': [float(v) for v in n_fit], 'offset_fit_frame_m': float(tls_d),
        'checks': {
            'det_R_minus_1': det - 1.0,
            'orthogonality_max_abs_err': orth,
            'R_times_normal': [float(v) for v in Rn],
            'ground_z_signed_residual_rms_m': float(np.sqrt(np.mean(z_ground ** 2))),
            'ground_z_signed_residual_p95_abs_m': float(np.percentile(np.abs(z_ground), 95)),
            'ground_z_signed_residual_mad_m': float(np.median(np.abs(z_ground))),
        },
        'per_frame_tls': per_frame,
        'state_spread_A_vs_C': state_spread,
        'limits': ['消费级 iPhone 水平 anchor（P02-B）不提供精确倾角误差界；不声称物理精度',
                   '未做 d/nz 或 refit-RMS 外参优化（明确禁止项）',
                   'ROI 只覆盖通道地面一条 0.46×0.58m 区域；roll≈-5.9° 与 pitch≈1.9° 是'
                   '该局部区域在显示系的几何姿态，可能反映真实局部坡度/不平，'
                   '不能与 iPhone 水平 anchor 直接对齐（不同位置、不同量具）',
                   'research candidate，不接运行时/正式外参'],
    }
    with open(os.path.join(HERE, '03_CANDIDATE.json'), 'w', encoding='utf-8') as f:
        json.dump(cand, f, ensure_ascii=False, indent=1)
    print('OK: consensus PASS, 01/02/03 emitted; joint', joint_info['points_total'], 'points')
    return 0


if __name__ == '__main__':
    sys.exit(main())
