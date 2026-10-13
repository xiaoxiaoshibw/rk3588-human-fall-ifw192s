"""CL2-12 STEP3+holdout: within-ring spatial gradient + 3 way grouped CV + frame72 ROI2 regression.

Pre-registered (00 v1):
- Within-ring conditional analysis answers ONLY "is per-ring constant offset sufficient (M1)?".
  It does NOT exclude or prove any physical sensor bias type (P5 boundary).
- Grouped CV (spatial 5-fold Morton cells, leave-one-ring-out, frame 5-fold) computed on FIT only,
  no leakage across folds, no holdout tuning.
- Frame72/ROI2 300-pt regression rematches frozen P95/RMS (independent recompute).

Outputs: 03_WITHIN_RING_DATA.json (numbers backing 03_WITHIN_RING_ANALYSIS.md / 04_HOLDOUT_VALIDATION.md)
"""
import json, hashlib
from collections import defaultdict
import numpy as np

DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECT_BIN = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'
WIDTHS = [0.05, 0.10, 0.15]
MIN_RING_PTS, MIN_CELL_PTS = 50, 20
P95_FROZEN = 0.050291869360  # m, frozen from CL2-10 (linear-interp quantile on |resid|)
RMS_FROZEN = 0.027417988

report = json.load(open(DOM + '/report.json'))
assert report['source']['bin_sha256'] == EXPECT_BIN
tls = report['estimators']['tls']
R0 = np.array(tls['R'][0]); R1 = np.array(tls['R'][1])
normal = np.array(tls['normal_source']); offset = float(tls['offset_source_m'])

dom = np.load(DOM + '/domain.npz')
raw = np.fromfile(BIN, dtype=np.uint8)
n = raw.size // 28
view = raw[:n * 28].reshape(n, 28)

def load(rows_arr):
    sel = view[rows_arr]
    xyz = sel[:, 0:12].copy().view('<f4').astype(np.float64)
    rings = sel[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
    return xyz, rings

xyz_f, rings_f = load(dom['source_rows'])
resid_f = xyz_f @ normal + offset
dx_f = xyz_f @ R0; dy_f = xyz_f @ R1
region_f = dom['region_codes']; ord_f = dom['frame_ordinals']
xyz_h, rings_h = load(dom['holdout_rows'])
resid_h = xyz_h @ normal + offset
region_h = dom['holdout_regions']; ord_h = dom['holdout_ordinals']

def merge_rings(rr):
    cnt = defaultdict(int)
    for r in rr: cnt[int(r)] += 1
    valid = sorted(r for r, c in cnt.items() if c >= MIN_RING_PTS)
    return {int(r): (int(r) if cnt[int(r)] >= MIN_RING_PTS else min(valid, key=lambda v: (abs(v-int(r)), v)))
            for r in set(rr.tolist())}

def merge_cells(xx, yy, w):
    ix = np.floor(xx/w).astype(np.int64); iy = np.floor(yy/w).astype(np.int64)
    pts = defaultdict(int)
    for a, b in zip(ix, iy): pts[(int(a), int(b))] += 1
    keep = {c for c, p in pts.items() if p >= MIN_CELL_PTS}
    if not keep: keep = {max(pts, key=lambda c: pts[c])}
    mp = {}
    for c in pts:
        if c in keep: mp[c] = c
        else:
            tgt = None
            for cand in [(c[0]+1, c[1]), (c[0]-1, c[1]), (c[0], c[1]+1), (c[0], c[1]-1)]:
                if cand in keep: tgt = cand; break
            if tgt is None: tgt = min(keep, key=lambda k: (abs(k[0]-c[0])+abs(k[1]-c[1]), k))
            mp[c] = tgt
    return mp

def design(rings_m, cells_m, r_levels, c_levels, model):
    if model == 'M0':
        return np.ones((len(rings_m), 1))
    if model == 'M1':
        idx = {r: i for i, r in enumerate(r_levels)}
        A = np.zeros((len(rings_m), len(r_levels)))
        for i, r in enumerate(rings_m): A[i, idx[r]] = 1.
        return A
    if model == 'M2':
        idx = {c: i for i, c in enumerate(c_levels)}
        A = np.zeros((len(cells_m), len(c_levels)))
        for i, c in enumerate(cells_m): A[i, idx[c]] = 1.
        return A
    if model == 'M3':
        n_par = (len(r_levels)-1) + (len(c_levels)-1) + 1
        A = np.zeros((len(rings_m), n_par)); A[:, -1] = 1.
        ri = {r: i-1 for i, r in enumerate(r_levels)}
        ci = {c: (len(r_levels)-1)+i-1 for i, c in enumerate(c_levels)}
        for i, (r, c) in enumerate(zip(rings_m, cells_m)):
            if r in ri: A[i, ri[r]] = 1.
            if c in ci: A[i, ci[c]] = 1.
        return A

def predict(model, xh, rings_q, cells_q, dxq, dyq, r_levels, c_levels, w):
    if model == 'M0': return np.full(len(rings_q), xh[0])
    if model == 'M1':
        m = {r: xh[i] for i, r in enumerate(r_levels)}
        return np.array([m.get(int(r), 0.0) for r in rings_q])
    if model == 'M2':
        m = {c: xh[i] for i, c in enumerate(c_levels)}
        return np.array([m.get(c, 0.0) for c in cells_q])
    if model == 'M3':
        nb = len(r_levels)-1
        bm = {r: (0.0 if i == 0 else xh[i-1]) for i, r in enumerate(r_levels)}
        cm = {c: (0.0 if i == 0 else xh[nb+i-1]) for i, c in enumerate(c_levels)}
        intercept = float(xh[-1])  # audit fix: carry intercept in prediction (was dropped)
        return np.array([bm.get(int(r), 0.0)+cm.get(c, 0.0) for r, c in zip(rings_q, cells_q)]) + intercept

out = {'within_ring': {}, 'cv': {}, 'regression': {}}

# ---------- Within-ring conditional analysis (FIT domain) ----------
for roi in (1, 2, 3, 4):
    m = region_f == roi
    xx, yy, rr, res = dx_f[m], dy_f[m], rings_f[m], resid_f[m]
    ring_map = merge_rings(rr)
    recs = []
    for r in sorted(set(ring_map.values())):
        sel = np.array([ring_map[int(a)] == r for a in rr])
        if sel.sum() < 30: continue
        sx, sy, sr = xx[sel], yy[sel], res[sel]
        def slope(a, b):
            if np.std(a) < 1e-9: return None
            return float(np.polyfit(a, b, 1)[0])
        full_y, full_x = slope(sy, sr), slope(sx, sr)
        # 5% top-trim robust variant
        q = np.quantile(np.abs(sr - np.median(sr)), 0.95)
        keep = np.abs(sr - np.median(sr)) <= q
        trim_y = slope(sy[keep], sr[keep]); trim_x = slope(sx[keep], sr[keep])
        recs.append({'ring': int(r), 'n': int(sel.sum()),
                     'dx_span': float(sx.max()-sx.min()), 'dy_span': float(sy.max()-sy.min()),
                     'slope_resid_on_dy': full_y, 'slope_resid_on_dx': full_x,
                     'trim5_slope_resid_on_dy': trim_y, 'trim5_slope_resid_on_dx': trim_x,
                     'resid_mean': float(sr.mean()), 'resid_std': float(sr.std(ddof=1))})
    # scale sensitivity: slope distribution per scale's within-ring cell means
    scale_sens = {}
    for w in WIDTHS:
        cmp_map = merge_cells(xx, yy, w)
        slopes = []
        for r in sorted(set(ring_map.values())):
            sel = np.array([ring_map[int(a)] == r for a in rr])
            if sel.sum() < 30: continue
            sx, sy, sr = xx[sel], yy[sel], res[sel]
            if np.std(sy) > 1e-9:
                slopes.append(float(np.polyfit(sy, sr, 1)[0]))
        if slopes:
            scale_sens['%0.2f' % w] = {
                'n_slopes': len(slopes),
                'pos_frac': float(np.mean([s > 0 for s in slopes])),
                'quantiles': [float(np.quantile(slopes, q)) for q in (0, .25, .5, .75, 1)]}
    # overlap-zone neighboring-ring residual diff (same dx band, adjacent ring groups)
    bands = []
    rl = sorted(set(ring_map.values()))
    for i in range(len(rl)-1):
        a, b = rl[i], rl[i+1]
        sa = np.array([ring_map[int(v)] == a for v in rr])
        sb = np.array([ring_map[int(v)] == b for v in rr])
        lo = max(xx[sa].min(), xx[sb].min()); hi = min(xx[sa].max(), xx[sb].max())
        if hi <= lo: continue
        oa = sa & (xx >= lo) & (xx <= hi); ob = sb & (xx >= lo) & (xx <= hi)
        if oa.sum() < 10 or ob.sum() < 10: continue
        bands.append({'ring_pair': [int(a), int(b)], 'dx_band': [float(lo), float(hi)],
                      'n': [int(oa.sum()), int(ob.sum())],
                      'resid_mean_diff_m': float(res[oa].mean() - res[ob].mean())})
    out['within_ring'][f'ROI{roi}'] = {'per_ring': recs, 'scale_sensitivity': scale_sens,
                                       'overlap_neighbor_diff': bands}

# ---------- Grouped cross-validation (FIT domain only) ----------
rng = np.random.default_rng(20261012)
for roi in (1, 2, 3, 4):
    m = region_f == roi
    xx, yy, rr, res, oo = dx_f[m], dy_f[m], rings_f[m], resid_f[m], ord_f[m]
    ring_map = merge_rings(rr)
    rings_m = np.array([ring_map[int(a)] for a in rr])
    for w in WIDTHS:
        cmp_map = merge_cells(xx, yy, w)
        cells_m = [cmp_map[(int(np.floor(a/w)), int(np.floor(b/w)))] for a, b in zip(xx, yy)]
        r_levels = sorted(set(rings_m)); c_levels = sorted(set(cells_m))
        # fold assignments (audit fix: spatial folds by pre-registered Morton order, not shuffle)
        clabs = sorted(set(cells_m), key=lambda c: (c[0] * 73856093 ^ c[1] * 19349663, c))
        cf = {c: i % 5 for i, c in enumerate(clabs)}
        spatial_fold = np.array([cf[c] for c in cells_m])
        ords = sorted(set(oo.tolist()))
        of = {o: i % 5 for i, o in enumerate(ords)}
        frame_fold = np.array([of[int(o)] for o in oo])
        ring_fold_labels = r_levels
        schemes = {'spatial5': ('fold', spatial_fold, sorted(set(spatial_fold.tolist()))),
                   'frame5': ('fold', frame_fold, sorted(set(frame_fold.tolist()))),
                   'loro': ('ring', rings_m, ring_fold_labels)}
        res_rec = {}
        for name, (kind, labels, lev) in schemes.items():
            rec = {mn: [] for mn in ('M0', 'M1', 'M2', 'M3')}
            for L in lev:
                te = labels == L if kind == 'fold' else rings_m == L
                tr = ~te
                if te.sum() == 0 or tr.sum() < 100: continue
                for mn in ('M0', 'M1', 'M2', 'M3'):
                    if mn == 'M3' and kind == 'ring':
                        continue  # M3 under LORO not meaningful for held ring (no training obs)
                    # for LORO with M1: held ring has no train obs -> skip too
                    if kind == 'ring' and mn == 'M1':
                        continue
                    A = design(rings_m[tr], [c for i, c in enumerate(cells_m) if tr[i]], r_levels, c_levels, mn)
                    xh, _, _, _ = np.linalg.lstsq(A, res[tr], rcond=None)
                    pred = predict(mn, xh, rings_m[te], [cells_m[i] for i in np.where(te)[0]],
                                   xx[te], yy[te], r_levels, c_levels, w)
                    rec[mn].append(float(np.mean((res[te]-pred)**2)))
            res_rec[name] = {mn: (float(np.sqrt(np.mean(v))) if v else None) for mn, v in rec.items()}
        out['cv'][f'ROI{roi}/w{w}'] = res_rec

# ---------- Frozen regression: frame72 ROI2 ----------
m72 = (region_h == 2) & (ord_h == 72)
r72 = resid_h[m72]
abs72 = np.abs(r72)
p95 = float(np.quantile(abs72, 0.95, method='linear'))
rms = float(np.sqrt(np.mean(r72**2)))
out['regression']['frame72_ROI2'] = {
    'n': int(m72.sum()), 'rms_m': rms, 'p95_abs_m': p95,
    'rms_frozen_m': RMS_FROZEN, 'p95_frozen_m': P95_FROZEN,
    'rms_match': abs(rms - RMS_FROZEN) < 1e-9, 'p95_match_1e-9': abs(p95 - P95_FROZEN) < 1e-9,
    'p95_match_5e-7': abs(p95 - P95_FROZEN) < 5e-7}
json.dump(out, open('03_WITHIN_RING_DATA.json', 'w'), indent=2,
          default=lambda o: int(o) if isinstance(o, np.integer) else
          (float(o) if isinstance(o, np.floating) else (bool(o) if isinstance(o, np.bool_) else o)))
print('regression:', out['regression']['frame72_ROI2'])
