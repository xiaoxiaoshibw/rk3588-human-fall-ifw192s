"""E1 地面可观测性实测（协议 docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1/PROTOCOL_V1.json 运行前冻结）。

问题：地面点是真缺失还是没被识别；地面行径向间距；旧最大支持面入口在本段选到什么。
输出：results/E1_SUMMARY.json + E1_MASK.npz + E1_ARRAYS.npz + MANIFEST_E1.json（全部排他写）。
H_TLS_PRIOR 只是软先验/对照，不产出地面身份或物理标定结论。
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
import source_io as sio
import core.ground as g
import core.ground_diagnostics as gd

EVID = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1'
RESULTS = EVID / 'results'
SESSION = ROOT / 'data/sessions/cap_20261017_113516'
PROTOCOL = EVID / 'PROTOCOL_V1.json'

TLS_N = np.array([-0.4546594173329524, -0.02722635715441169, 0.8902491447378991])
TLS_OFFSET_MAG = 1.3566335069482636
XY, BAND, LOWBAND, NEAR, MIN_ROWS = 0.25, 0.10, 0.08, 0.30, 5
CELLS, COFF = 512, 256

NO_RETURN, OBSERVED_NON_GROUND, GROUND_INFERRED, UNKNOWN, GROUND_CONFIRMED = 0, 1, 2, 3, 4


def sha_file(p):
    import hashlib
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def flat_idx(x, y):
    ix = np.floor(x / XY).astype(np.int64) + COFF
    iy = np.floor(y / XY).astype(np.int64) + COFF
    if ((ix < 0) | (ix >= CELLS) | (iy < 0) | (iy >= CELLS)).any():
        raise ValueError('XY out of fixed grid')
    return ix * CELLS + iy


def w_peaks(w, nbins=420, lo=-4.0, hi=2.1):
    hist, edges = np.histogram(w, bins=nbins, range=(lo, hi))
    order = np.argsort(hist)[::-1]
    peaks = []
    for i in order[:5]:
        peaks.append(dict(count=int(hist[i]), center_m=round(float((edges[i] + edges[i + 1]) / 2), 4)))
    return peaks, hist, edges


def main():
    t0 = time.time()
    ses = sio.Session(SESSION)
    src_sha = ses.sha256()
    fit_fis = [fi for fi in range(len(ses.frames)) if ses.rel_s(fi) < 20.0]

    # 预扫描：确定 n·p 分布主峰与符号约定（n·p+d=0 → d=-w_peak）
    probe = np.concatenate([ses.xyz(f)[sio.validity(ses.xyz(f))[1]] for f in fit_fis[::12]])
    peaks_probe, _, _ = w_peaks(probe @ TLS_N)
    w_peak = peaks_probe[0]['center_m']
    sign_note = f'empirical band peak w=n·p={w_peak} m; H_TLS_PRIOR |offset|={TLS_OFFSET_MAG}; convention n·p+d=0 -> d={-w_peak}'

    # ---- Pass 1：XY 格结构 + TLS 带行 + 径向间距 ----
    count = np.zeros(CELLS * CELLS, np.int32)
    band_count = np.zeros(CELLS * CELLS, np.int32)
    zmin = np.full(CELLS * CELLS, np.inf)
    zmax = np.full(CELLS * CELLS, -np.inf)
    w_hist = np.zeros(420, np.int64)
    band_signed, band_r, gap_mid, gaps = [], [], [], []
    total_rows = total_valid = total_band = 0
    for fi in fit_fis:
        p = ses.xyz(fi)
        finite, valid = sio.validity(p)
        v = p[valid]
        total_rows += len(p)
        total_valid += len(v)
        w = v @ TLS_N
        h, _ = np.histogram(w, bins=420, range=(-4.0, 2.1))
        w_hist += h
        idx = flat_idx(v[:, 0], v[:, 1])
        np.add.at(count, idx, 1)
        np.minimum.at(zmin, idx, v[:, 2])
        np.maximum.at(zmax, idx, v[:, 2])
        bm = np.abs(w - w_peak) <= BAND
        np.add.at(band_count, idx[bm], 1)
        sb = w[bm] - w_peak
        band_signed.append(sb.astype(np.float32))
        rb = np.linalg.norm(v[bm], axis=1)
        band_r.append(rb.astype(np.float32))
        ab = np.degrees(np.arctan2(v[bm, 1], v[bm, 0]))
        abin = np.floor((ab + 180.0)).astype(np.int64)
        order = np.lexsort((rb, abin))
        rr, bb = rb[order], abin[order]
        same = bb[1:] == bb[:-1]
        gp = np.diff(rr)[same]
        gaps.append(gp.astype(np.float32))
        gap_mid.append(((rr[1:] + rr[:-1]) / 2)[same].astype(np.float32))

    band_signed = np.concatenate(band_signed)
    band_r = np.concatenate(band_r)
    gaps = np.concatenate(gaps)
    gap_mid = np.concatenate(gap_mid)
    total_nonvalid = total_rows - total_valid
    # ---- Pass 2：H_LOWBAND（每格最低 z 簇）----
    low_count = np.zeros(CELLS * CELLS, np.int32)
    low_signed = []
    for fi in fit_fis:
        p = ses.xyz(fi)
        _, valid = sio.validity(p)
        v = p[valid]
        idx = flat_idx(v[:, 0], v[:, 1])
        lm = v[:, 2] <= zmin[idx] + LOWBAND
        np.add.at(low_count, idx[lm], 1)
        low_signed.append((v[lm] @ TLS_N - w_peak).astype(np.float32))
    low_signed = np.concatenate(low_signed)

    # ---- 掩码五态 ----
    xs = (np.arange(CELLS) - COFF + 0.5) * XY
    gx, gy = np.meshgrid(xs, xs, indexing='ij')
    z_plane = -(w_peak + TLS_N[0] * gx + TLS_N[1] * gy) / TLS_N[2]
    gap_up = zmin.reshape(CELLS, CELLS) - z_plane
    state = np.full((CELLS, CELLS), NO_RETURN, np.uint8)
    has = count.reshape(CELLS, CELLS) > 0
    bc = band_count.reshape(CELLS, CELLS)
    state[has & (bc == 0) & (gap_up <= NEAR)] = OBSERVED_NON_GROUND
    state[has & (bc == 0) & (gap_up > NEAR)] = UNKNOWN
    state[has & (bc > 0) & (bc < MIN_ROWS)] = UNKNOWN
    state[has & (bc >= MIN_ROWS)] = GROUND_INFERRED
    # GROUND_CONFIRMED(=4) 保留为空：缺人工/AI 审核身份
    obs = np.argwhere(count.reshape(CELLS, CELLS) > 0)
    if len(obs):
        x0, x1 = int(obs[:, 0].min()), int(obs[:, 0].max())
        y0, y1 = int(obs[:, 1].min()), int(obs[:, 1].max())
        crop = dict(x0=x0, x1=x1, y0=y0, y1=y1)
        sub = state[x0:x1 + 1, y0:y1 + 1]
    else:
        crop, sub = None, None
    mask_counts = {name: int(np.count_nonzero(sub == st)) for name, st in (
        ('NO_RETURN', NO_RETURN), ('OBSERVED_NON_GROUND', OBSERVED_NON_GROUND),
        ('GROUND_INFERRED', GROUND_INFERRED), ('UNKNOWN', UNKNOWN),
        ('GROUND_CONFIRMED', GROUND_CONFIRMED))} if sub is not None else {}

    # ---- E1-C 旧入口复现（只读复用 core.ground.fit_ground_plane）----
    old_runs = []
    old_frames = [20, 100, 180]
    agg = [ses.xyz(fi)[sio.validity(ses.xyz(fi))[1]] for fi in fit_fis if fi % 5 == 0]
    agg = np.concatenate(agg)
    if len(agg) > 200000:
        agg = agg[::int(np.ceil(len(agg) / 200000))]
    cases = [(f'fi{fi}', ses.xyz(fi)[sio.validity(ses.xyz(fi))[1]]) for fi in old_frames] + [('aggregate_fit_stride', agg)]
    for name, pts in cases:
        res = g.fit_ground_plane(pts)
        entry = dict(case=name, point_count=int(len(pts)), status=res['status'], valid=bool(res['valid']),
                     reason=res['reason'], normal=res['normal'], offset_m=res['offset_m'],
                     sensor_height_m=res['sensor_height_m'],
                     tilt_deg=None if res['tilt_rad'] is None else round(float(np.degrees(res['tilt_rad'])), 4),
                     fit_inlier_count=res['fit_inlier_count'], inlier_fraction=res['inlier_fraction'],
                     fit_residual=res.get('fit_residual'), valid_region=res['valid_region'])
        if res['normal'] is not None:
            n, off = np.array(res['normal']), res['offset_m']
            thr = res['settings']['inlier_threshold_m']
            inl = pts[np.abs(pts @ n + off) <= thr]
            w_inl = inl @ TLS_N
            entry['inlier_tls_band_fraction'] = round(float(np.mean(np.abs(w_inl - w_peak) <= BAND)), 4) if len(inl) else None
            entry['inlier_z_minmax'] = [round(float(inl[:, 2].min()), 4), round(float(inl[:, 2].max()), 4)] if len(inl) else None
            ci = flat_idx(inl[:, 0], inl[:, 1])
            u, c = np.unique(ci, return_counts=True)
            top = u[np.argsort(c)[::-1][:4]]
            cells = []
            for t in top:
                m = ci == t
                cells.append(dict(xy_cell=[int(t // CELLS - COFF), int(t % CELLS - COFF)],
                                  rows=int(m.sum()), z_range=[round(float(inl[m, 2].min()), 4), round(float(inl[m, 2].max()), 4)]))
            entry['top4_support_cells'] = cells
        old_runs.append(entry)

    # ---- E1-D 数值互检（同族，不算独立证据）：同一批带行点坐标 ----
    collect = []
    for fi in fit_fis:
        p = ses.xyz(fi)
        _, valid = sio.validity(p)
        v = p[valid]
        w = v @ TLS_N
        collect.append(v[np.abs(w - w_peak) <= BAND])
        if sum(len(c) for c in collect) > 400000:
            break
    pts_sub = np.concatenate(collect)
    pts_sub = pts_sub[::max(1, len(pts_sub) // 200000)]
    signed_sub = pts_sub @ TLS_N - w_peak
    own = dict(count=int(len(pts_sub)),
               rms_m=round(float(np.sqrt(np.mean(signed_sub ** 2))), 6),
               p95_m=round(float(np.percentile(np.abs(signed_sub), 95)), 6),
               signed_median_m=round(float(np.median(signed_sub)), 6))
    gd_stats = gd.residual_stats(pts_sub, TLS_N, -w_peak)
    crosscheck = dict(own_on_band_signed_subsample=own,
                      residual_stats_on_same_points={k: gd_stats[k] for k in
                                                     ('count', 'rms_m', 'p95_m', 'signed_median_m', 'support_count', 'support_fraction')},
                      note='TLS/PCA 同族数值互检，不算两份独立证据')

    # ---- 径向间距 vs 公式 ----
    spacing_rows = []
    for lo in range(2, 8):
        m = (gap_mid >= lo) & (gap_mid < lo + 1)
        if m.any():
            med = float(np.median(gaps[m]))
        else:
            med = None
        formula = {h: round((lo + 0.5) ** 2 / h * np.radians(0.5), 4) for h in (1.10, 1.35663)}
        spacing_rows.append(dict(range_band_m=f'[{lo},{lo + 1})', samples=int(m.sum()),
                                 measured_gap_median_m=None if med is None else round(med, 4),
                                 measured_p05_p95=None if med is None else
                                 [round(float(np.percentile(gaps[m], 5)), 4), round(float(np.percentile(gaps[m], 95)), 4)],
                                 formula_gap_m=formula,
                                 formula_note='dR~(R^2+h^2)/h*dtheta at band centre, dtheta=0.5deg; h values are sensitivity assumptions, not measured height'))

    summary = dict(
        item='HFUS-GROUND-OBSERVABILITY-RD-01', measurement='E1',
        source=dict(sid='cap_20261017_113516', sha256=src_sha),
        run=dict(argv=sys.argv, wall_s=round(time.time() - t0, 2),
                 code_sha256={p.name: sha_file(p) for p in (HERE / 'source_io.py', HERE / 'e1_ground_obs.py')},
                 protocol_sha256=sha_file(PROTOCOL),
                 core_ground_sha256=sha_file(ROOT / 'src/human_fall_detection/core/ground.py'),
                 core_ground_diagnostics_sha256=sha_file(ROOT / 'src/human_fall_detection/core/ground_diagnostics.py')),
        fit=dict(frames=len(fit_fis), frame_range=[fit_fis[0], fit_fis[-1]],
                 rows=total_rows, valid_rows=total_valid, nonvalid_rows=total_nonvalid,
                 conservation_ok=bool(total_rows == total_valid + total_nonvalid)),
        band_peak=dict(sign_convention=sign_note, probe_top_peaks=peaks_probe,
                       w_peak_m=w_peak,
                       tls_prior_offset_magnitude=TLS_OFFSET_MAG,
                       interpretation='窄峰=平面相容行聚集；峰值位置与 |offset| 接近则支持旧先验平移量级，仍非本段物理标定'),
        ground_presence=dict(
            band_rows=int(len(band_signed)), band_row_fraction=round(float(len(band_signed) / max(1, total_valid)), 4),
            band_signed_stats=dict(mean_m=round(float(band_signed.mean()), 5),
                                   median_m=round(float(np.median(band_signed)), 5),
                                   rms_m=round(float(np.sqrt(np.mean(band_signed.astype(np.float64) ** 2))), 5),
                                   p95_m=round(float(np.percentile(np.abs(band_signed), 95)), 5)),
            lowband_rows=int(len(low_signed)), lowband_signed_median_m=round(float(np.median(low_signed)), 5),
            lowband_note='H_LOWBAND 最低簇与 TLS 带的 signed 中位数：接近 0 说明低点在先验平面附近；明显偏离说明低点来自家具底/墙脚等',
            mask=dict(cell_m=XY, states=mask_counts, crop_cell_indices=crop,
                      state_legend={'0': 'NO_RETURN', '1': 'OBSERVED_NON_GROUND', '2': 'GROUND_INFERRED',
                                    '3': 'UNKNOWN', '4': 'GROUND_CONFIRMED(reserved, empty)'},
                      caveats=['NO_RETURN：FIT 内无有效行；遮挡阴影与真实无面不可分（无射线模型）',
                               'GROUND_INFERRED：≥5 带行/格，几何与 H_TLS_PRIOR 相容，身份仍 UNKNOWN',
                               'OBSERVED_NON_GROUND：观测到近地带区域但与先验面不相容',
                               'UNKNOWN：点全在带上方>0.30m（家具下遮挡无法与缺失区分）或带行不足',
                               'GROUND_CONFIRMED：需审核身份，本批为空'])),
        ground_radial_spacing=spacing_rows,
        old_entry_reproduction=dict(method='core.ground.fit_ground_plane default settings, read-only',
                                    note='复现文档所述“最大支持面 + 高支持XY格”行为；不改旧门、不翻旧 FAIL',
                                    runs=old_runs),
        numeric_crosscheck=crosscheck,
    )
    sio.write_new(RESULTS / 'E1_SUMMARY.json', summary)
    sio.save_new_npz(RESULTS / 'E1_MASK.npz', state=state, count=count.reshape(CELLS, CELLS),
                     band_count=band_count.reshape(CELLS, CELLS), zmin=np.where(np.isfinite(zmin), zmin, np.nan).reshape(CELLS, CELLS))
    sio.save_new_npz(RESULTS / 'E1_ARRAYS.npz', w_hist=w_hist, band_signed=band_signed,
                     gaps=gaps, gap_mid=gap_mid, low_signed=low_signed)
    manifest = dict(item='HFUS-GROUND-OBSERVABILITY-RD-01', run='E1', argv=sys.argv,
                    exit_code=0, wall_s=round(time.time() - t0, 2),
                    source_sha256=src_sha,
                    code_sha256={p.name: sha_file(p) for p in (HERE / 'source_io.py', HERE / 'e1_ground_obs.py')},
                    protocol_sha256=sha_file(PROTOCOL),
                    outputs=['results/E1_SUMMARY.json', 'results/E1_MASK.npz', 'results/E1_ARRAYS.npz'],
                    notes=['H_TLS_PRIOR 软先验，非本段物理标定', 'GROUND_CONFIRMED 保留为空', '无 GT：只报描述统计'])
    sio.write_new(RESULTS / 'MANIFEST_E1.json', manifest)
    print('E1 done wall_s=', manifest['wall_s'], 'band_rows=', len(band_signed), 'mask=', mask_counts)


if __name__ == '__main__':
    main()
