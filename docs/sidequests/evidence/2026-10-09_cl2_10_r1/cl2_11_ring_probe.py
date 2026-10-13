"""CL2-11 只读描述性探针：source-ring 与 display-x（ROI2 名义 X 轴）混淆量量化。

严格描述性：不改 FIT/holdout、不重拟合、不经验候选、不改门控。
输入：原 domain.npz holdout 行绑定 + 原 bin（SHA 与冻结 report 核对）+ 原 TLS 平面。

输出 JSON：
- frame72 ROI2：每 ring 的 display-x 均值/min/max（证明 ring↔display-x 在测量学上强相关），
  含 display-x 覆盖重叠区间；
- 298 条 source 行有 ring 标签、2 条无标签（行内 padding 区）的残差对比；
- FIT 域 ROI2 全 64850 点同口径（复用 CL2-10 既有诊断的同趋势复核）。
"""
import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20')
DOMAIN = BASE / 'domain.npz'
REPORT = BASE / 'report.json'
BIN = Path(r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin')
OUT = Path(r'D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/cl2_11_ring_xy_probe.json')
EXPECTED_BIN_SHA = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'


def read_points(bin_path, rows):
    raw = np.fromfile(bin_path, dtype=np.uint8)
    n = raw.size // 28
    view = raw[:n * 28].reshape(n, 28)
    sel = view[rows]
    xyz = sel[:, 0:12].copy().view('<f4').astype(np.float64)
    rings = sel[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
    return xyz, rings, n


def sec_stats(resid, rings, n_rows):
    out = {}
    for ring in sorted(set(rings.tolist())):
        m = rings == ring
        out[int(ring)] = {
            'count': int(m.sum()),
            'signed_mean_m': float(resid[m].mean()),
        }
    return out


def main():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    assert report['source']['bin_sha256'] == EXPECTED_BIN_SHA
    tls = report['estimators']['tls']
    normal = np.array(tls['normal_source'], dtype=np.float64)
    offset = float(tls['offset_source_m'])

    with np.load(DOMAIN, allow_pickle=False) as d:
        holdout_rows = d['holdout_rows']
        holdout_regions = d['holdout_regions']
        holdout_ordinals = d['holdout_ordinals']
        fit_rows = d['source_rows']
        fit_region = d['region_codes']

    target = (holdout_regions == 2) & (holdout_ordinals == 72)
    rows = holdout_rows[target]
    xyz, rings, n_total = read_points(BIN, rows)
    resid = xyz @ normal + offset

    # R 第3行 = 负法向（display Z 向下翻转）；display x = source 坐标在 R[0] 方向投影
    R0 = np.array(tls['R'][0], dtype=np.float64)
    disp_x = xyz @ R0

    labeled = rings != 0
    out = {
        'n_rows': int(len(rows)),
        'n_ring_labeled': int(labeled.sum()),
        'n_ring_unlabeled': int((~labeled).sum()),
        'unlabeled_stats': {
            'count': int((~labeled).sum()),
            'signed_mean_m': float(resid[~labeled].mean()) if (~labeled).any() else None,
        },
        'ring_display_x': [],
        'fit_roi62k_recheck': None,
    }
    for ring in sorted(set(rings[labeled].tolist())):
        m = labeled & (rings == ring)
        out['ring_display_x'].append({
            'ring': int(ring),
            'count': int(m.sum()),
            'signed_mean_m': float(resid[m].mean()),
            'display_x_mean_m': float(disp_x[m].mean()),
            'display_x_min_m': float(disp_x[m].min()),
            'display_x_max_m': float(disp_x[m].max()),
        })

    # FIT-domain ROI2 64850 点同口径复核（对应 CL2-10 01_channel_diagnostics.json '2'）
    fit_mask = fit_region == 2
    frows = fit_rows[fit_mask]
    fxyz, frings, _ = read_points(BIN, frows)
    fresid = fxyz @ normal + offset
    fdisp = fxyz @ R0
    flab = frings != 0
    fit_out = {'n': int(len(frows)), 'n_labeled': int(flab.sum()), 'per_ring': []}
    for ring in sorted(set(frings[flab].tolist())):
        m = flab & (frings == ring)
        fit_out['per_ring'].append({
            'ring': int(ring),
            'count': int(m.sum()),
            'signed_mean_m': float(fresid[m].mean()),
            'display_x_mean_m': float(fdisp[m].mean()),
            'display_x_min_m': float(fdisp[m].min()),
            'display_x_max_m': float(fdisp[m].max()),
        })
    out['fit_roi62k_recheck'] = fit_out

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf8')
    print('WROTE', OUT)
    labeled_rings = [e for e in out['ring_display_x']]
    print('labeled rings:', len(labeled_rings))
    for e in labeled_rings:
        print(e)


if __name__ == '__main__':
    sys.exit(main())
