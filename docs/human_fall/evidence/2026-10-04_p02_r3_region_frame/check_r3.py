"""P02 R3 独立数值核验：读已生成 JSON/NPZ，核验 forward/inverse/proper R/Rn=up/数值门。"""
import json
import math
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
NPZ = (OUT / '..' / '2026-10-04_p02_four_roi_r1' / '02_FROZEN_POINTS.npz').resolve()


def load(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def rot(pitch, roll):
    p, r = math.radians(pitch), math.radians(roll)
    cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cp, 0, sp], [sr*sp, cr, -sr*cp], [-cr*sp, sr, cr*cp]])


def main():
    z = np.load(NPZ)
    pts, reg = z['source'], z['region_code']
    diag, m1 = load('01_REGION_DIAG.json'), load('04_MODEL_I.json')
    checks = {}
    # 01 分区平面：正交/数值重算
    for rec in m1['records']:
        r = rec['region']
        n = np.array(rec['plane_source']['normal']); d = rec['plane_source']['offset_m']
        R = np.array(rec['rotation'])
        q = pts[reg == r]
        signed = q @ n + d
        mapped = q @ R.T + np.array(rec['translation_m'])
        checks[f'region{r}_proper_R'] = abs(np.linalg.det(R) - 1) < 1e-12
        checks[f'region{r}_Rn_up'] = float(np.max(np.abs(R @ n - [0, 0, 1]))) < 1e-12
        checks[f'region{r}_signedZ'] = float(np.max(np.abs(mapped[:, 2] - signed))) < 1e-12
        inv = (mapped - np.array(rec['translation_m'])) @ R
        checks[f'region{r}_inverse'] = float(np.max(np.abs(inv - q))) < 1e-12
        checks[f'region{r}_unit_n'] = abs(np.linalg.norm(n) - 1) < 1e-12
        # 独立重算该 ROI TLS（SVD 同型）
        c = q.mean(axis=0); _, _, vt = np.linalg.svd(q - c, full_matrices=False)
        nn = vt[-1]; dd = -float(nn @ c)
        if nn @ n < 0:
            nn, dd = -nn, -dd
        checks[f'region{r}_n_recompute'] = float(np.max(np.abs(nn - n))) < 1e-9
        checks[f'region{r}_d_recompute'] = abs(dd - d) < 1e-9
    # 门：分区联合评估 vs 数据门
    j = m1['joint_evaluation_all_392196_points']
    checks['model1_data_gate'] = (j['rms_m'] <= .03 and j['p95_m'] <= .05
                                  and j['support_fraction'] >= .8 and j['count'] >= 20)
    # 02：77 帧行数 + pitch/roll/d 与 npz 记录一致
    fs = load('02_FRAME_SEQUENCE.json')
    checks['frame_rows_772'] = fs['count'] == 772 and len(fs['frames']) == 772
    # 05/NPZ：与 02 行数值一致
    per = np.load(OUT / '03_PER_FRAME_MODEL.npz', allow_pickle=False)
    keys = [k for k in per['keys']]
    total = sum(len(per[k + '_ordinals']) for k in keys)
    checks['npz_records_772'] = total == 772
    for k in keys:
        sess, region = k[0], int(k[1])
        rows = sorted((f for f in fs['frames'] if f['session'] == sess and f['region'] == region),
                      key=lambda f: f['frame_ordinal'])
        ns, ds = per[k + '_n'], per[k + '_d']
        ords = per[k + '_ordinals']
        for f, n, d, o in zip(rows, ns, ds, ords):
            assert f['frame_ordinal'] == int(o)
            p_re = math.degrees(math.atan2(-n[0], n[2])); r_re = math.degrees(math.asin(float(n[1])))
            assert abs(p_re - f['pitch_deg']) < 1e-9 and abs(r_re - f['roll_deg']) < 1e-9
            assert abs(float(d) - f['d_m']) < 1e-12
            assert abs(np.linalg.norm(n) - 1) < 1e-12
        # 协方差半正定（量级极小，用相对 Frobenius 容差）
        for cov_n in per[k + '_covn']:
            ev = np.linalg.eigvalsh(cov_n)
            assert ev.min() >= -1e-12 * max(1e-30, float(np.linalg.norm(cov_n)))
        assert np.all(per[k + '_covd'] >= 0) and np.all(per[k + '_sigma2'] > 0)
    checks['npz_matches_json_and_cov_psd'] = True
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'checks': {k: (v if isinstance(v, bool) else str(v)) for k, v in checks.items()}}, indent=1, ensure_ascii=False))
    assert ok


if __name__ == '__main__':
    main()
