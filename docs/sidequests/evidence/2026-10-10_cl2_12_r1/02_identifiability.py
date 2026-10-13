"""CL2-12 STEP2: statistical identifiability experiment (M0/M1/M2/M3 + M4G/M4L).

Pre-registered (00_SCOPE_AND_ACCEPTANCE.md v1, SHA in 07 manifest). Fit on FIT domain
only (136,942 pts); holdout frames (72/144/217, 1,915 pts) used ONLY in STEP4-style
holdout evaluation inside this script's `eval_holdout` (no fitting). No leakage:
merging tables and scale selection are computed on the full FIT training set (they are
structural, not tuned on holdout); holdout metrics are reported, never minimized.

Models (all OLS on signed residual r, closed-form, SVD lstsq):
  M0: r = c
  M1: r = b_g(ring)
  M2: r = h(cell)
  M3: r = c0 + b_g(ring) + h(cell)   (one ring + one cell per dropped baseline)
  M4G: r = c0 + ax*dx + ay*dy        (global linear gradient control)
  M4L: cluster-local linear for hard-to-separate zones (diagnostic only)

Outputs: 02_IDENTIFIABILITY_RESULTS.json
"""
import json, hashlib
from collections import defaultdict
import numpy as np

DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECT_BIN = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'
WIDTHS = [0.05, 0.10, 0.15]
MIN_RING_PTS, MIN_CELL_PTS = 50, 20
# hard-cluster rule: |beta_g| or |h(cell)| > 3*MAD (see 00/P3 v2 amendment; was gap in v1)
HARD_Z = 3.0

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

xyz_fit, rings_fit = load(dom['source_rows'])
resid_fit = xyz_fit @ normal + offset
dx_fit = xyz_fit @ R0; dy_fit = xyz_fit @ R1
region_fit = dom['region_codes']; ordinal_fit = dom['frame_ordinals']

xyz_h, rings_h = load(dom['holdout_rows'])
resid_h = xyz_h @ normal + offset
dx_h = xyz_h @ R0; dy_h = xyz_h @ R1
region_h = dom['holdout_regions']; ordinal_h = dom['holdout_ordinals']

def merge_rings(rr):
    counts = defaultdict(int)
    for r in rr: counts[int(r)] += 1
    valid = sorted(r for r, c in counts.items() if c >= MIN_RING_PTS)
    out = {}
    for r in set(rr.tolist()):
        r = int(r)
        out[r] = r if counts[r] >= MIN_RING_PTS else min(valid, key=lambda v: (abs(v-r), v))
    return out

def merge_cells(xx, yy, w):
    ix = np.floor(xx / w).astype(np.int64); iy = np.floor(yy / w).astype(np.int64)
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
            if tgt is None:
                tgt = min(keep, key=lambda k: (abs(k[0]-c[0])+abs(k[1]-c[1]), k))
            mp[c] = tgt
    return mp

def design_m3(rings_m, cells_m, r_levels, c_levels):
    ridx = {r: i-1 for i, r in enumerate(r_levels)}           # first ring dropped
    cidx = {c: (len(r_levels)-1) + i-1 for i, c in enumerate(c_levels)}  # first cell dropped
    n_par = (len(r_levels) - 1) + (len(c_levels) - 1) + 1
    A = np.zeros((len(rings_m), n_par))
    A[:, -1] = 1.0
    for i, (r, c) in enumerate(zip(rings_m, cells_m)):
        if r in ridx: A[i, ridx[r]] = 1.0
        if c in cidx: A[i, cidx[c]] = 1.0
    return A, n_par

def design_m1(rings_m, r_levels):
    idx = {r: i for i, r in enumerate(r_levels)}
    A = np.zeros((len(rings_m), len(r_levels)))
    for i, r in enumerate(rings_m): A[i, idx[r]] = 1.0
    return A, len(r_levels)

def design_m2(cells_m, c_levels):
    idx = {c: i for i, c in enumerate(c_levels)}
    A = np.zeros((len(cells_m), len(c_levels)))
    for i, c in enumerate(cells_m): A[i, idx[c]] = 1.0
    return A, len(c_levels)

def design_m4g(dx, dy):
    A = np.column_stack([dx, dy, np.ones_like(dx)])
    return A, 3

def lstsq_stats(A, y):
    xh, res, rank, s = np.linalg.lstsq(A, y, rcond=None)
    fitted = A @ xh
    rss = float(((y - fitted) ** 2).sum())
    sigma2 = rss / len(y)
    cond = float(s[0] / s[-1]) if len(s) and s[-1] > 0 else float('inf')
    return xh, rss, sigma2, rank, cond

def quant(a, qs=(0, .25, .5, .75, 1)):
    return [float(np.quantile(a, q)) for q in qs]

class Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.bool_): return bool(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return super().default(o)

def half_sample_stability(rings_m, cells_m, y, r_levels, c_levels, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    h1, h2 = idx[:len(idx)//2], idx[len(idx)//2:]
    A, _ = design_m3(rings_m, cells_m, r_levels, c_levels)
    def beta(Ax, yy):
        xh, _, _, _ = np.linalg.lstsq(Ax, yy, rcond=None)
        # beta for ring params
        nb = len(r_levels) - 1
        bs = [0.0] + list(xh[:nb])
        cs = [0.0] + list(xh[nb:nb + len(c_levels) - 1])
        return np.array(bs), np.array(cs)
    b1, c1 = beta(A[h1], y[h1]); b2, c2 = beta(A[h2], y[h2])
    rb = float(np.corrcoef(b1, b2)[0, 1]) if len(b1) > 2 else float('nan')
    rc = float(np.corrcoef(c1, c2)[0, 1]) if len(c1) > 2 else float('nan')
    return rb, rc

def morton_cells(cells):
    # deterministic Morton-ish order by integer ix,iy
    return sorted(cells, key=lambda c: (c[0] * 73856093 ^ c[1] * 19349663))

def kfold_assign(labels, k, seed=0):
    labs = sorted(set(labels))
    rng = np.random.default_rng(seed)
    rng.shuffle(labs)
    fold = {}
    for i, l in enumerate(labs): fold[l] = i % k
    return np.array([fold[l] for l in labels])

out = {'models': {}, 'beta_sign_consistency': {}, 'holdout_eval': {}, 'hard_clusters': {}}
# master verdicts per (roi,w)
verds = {}

for roi in (1, 2, 3, 4):
    m = region_fit == roi
    xx, yy, rr, res = dx_fit[m], dy_fit[m], rings_fit[m], resid_fit[m]
    ord_fit_this = ordinal_fit[m]
    ring_map = merge_rings(rr)
    rings_m = np.array([ring_map[int(r)] for r in rr], dtype=np.int64)
    mh = region_h == roi
    xxh, yyh, rrh, resh = dx_h[mh], dy_h[mh], rings_h[mh], resid_h[mh]
    ord_h_this = ordinal_h[mh]
    if len(xxh):
        rings_mh = np.array([ring_map[int(r)] if int(r) in ring_map else
                             min(ring_map.values(), key=lambda v: (abs(v-int(r)), v)) for r in rrh])
    else:
        rings_mh = np.array([], dtype=np.int64)
    betas_by_w, cells_by_w = {}, {}
    for w in WIDTHS:
        cell_map = merge_cells(xx, yy, w)
        cells_m = [cell_map[(int(np.floor(a/w)), int(np.floor(b/w)))] for a, b in zip(xx, yy)]
        r_levels = sorted(set(rings_m))
        c_levels = morton_cells(set(cells_m))
        # fit
        A0 = np.ones((len(res), 1)); m0 = lstsq_stats(A0, res)
        A1, _ = design_m1(rings_m, r_levels); m1 = lstsq_stats(A1, res)
        A2, _ = design_m2(cells_m, c_levels); m2 = lstsq_stats(A2, res)
        A3, _ = design_m3(rings_m, cells_m, r_levels, c_levels); m3 = lstsq_stats(A3, res)
        A4g, _ = design_m4g(xx, yy); m4g = lstsq_stats(A4g, res)
        key = f'ROI{roi}/w{w}'
        nb = len(r_levels) - 1
        beta = np.concatenate([[0.0], m3[0][:nb]])
        hc = np.concatenate([[0.0], m3[0][nb:nb + len(c_levels) - 1]])
        rb, rc = half_sample_stability(rings_m, cells_m, res, r_levels, c_levels)
        out['models'][key] = {
            'n_fit': int(len(res)), 'n_levels': {'ring': len(r_levels), 'cell': len(c_levels)},
            'M0': {'sigma2': m0[2], 'rank': m0[3], 'cond': m0[4]},
            'M1': {'sigma2': m1[2], 'rank': m1[3], 'cond': m1[4]},
            'M2': {'sigma2': m2[2], 'rank': m2[3], 'cond': m2[4]},
            'M3': {'sigma2': m3[2], 'rank': m3[3], 'cond': m3[4],
                   'rank_ok': m3[3] == m3[0].shape[0] if False else int(m3[3]),
                   'n_par': A3.shape[1]},
            'M4G': {'sigma2': m4g[2], 'rank': m4g[3], 'cond': m4g[4]},
            'ds2_m3_vs_m1': 1 - m3[2] / m1[2] if m1[2] > 0 else None,
            'ds2_m3_vs_m2': 1 - m3[2] / m2[2] if m2[2] > 0 else None,
            'half_sample_corr_beta': rb, 'half_sample_corr_cell': rc,
            'beta': {str(r): float(b) for r, b in zip(r_levels, beta)},
            'cell_h': {f'{c[0]}_{c[1]}': float(hv) for c, hv in zip(c_levels, hc)},
        }
        betas_by_w[w] = dict(zip(r_levels, beta))
        cells_by_w[w] = dict(zip(c_levels, hc))
        # M4L hard clusters: rings/cells whose |effect| > 3*MAD
        mad_b = np.median(np.abs(beta - np.median(beta))) + 1e-12
        mad_c = np.median(np.abs(hc - np.median(hc))) + 1e-12
        hard_rings = [r for r, b in zip(r_levels, beta) if abs(b) > HARD_Z * mad_b]
        hard_cells = [c for c, hv in zip(c_levels, hc) if abs(hv) > HARD_Z * mad_c]
        # local linear fit restricted to points in hard zones
        hard_mask = np.array([(r in hard_rings) or (c in hard_cells) for r, c in zip(rings_m, cells_m)])
        m4l = None
        if hard_mask.sum() >= 30:
            Al, _ = design_m4g(xx[hard_mask], yy[hard_mask])
            xl, _, _, _ = np.linalg.lstsq(Al, res[hard_mask], rcond=None)
            m4l = {'n': int(hard_mask.sum()), 'ax': float(xl[0]), 'ay': float(xl[1]),
                   'sigma2': float(((res[hard_mask] - Al @ xl) ** 2).mean()),
                   'hard_rings': [int(r) for r in hard_rings],
                   'hard_cells': [f'{c[0]}_{c[1]}' for c in hard_cells]}
        out['hard_clusters'][key] = m4l
    # beta sign consistency across scales (common ring levels)
    common = set(betas_by_w[0.05]) & set(betas_by_w[0.10]) & set(betas_by_w[0.15])
    if len(common) >= 2:
        signs = {r: [np.sign(betas_by_w[w][r]) for w in WIDTHS] for r in common}
        cons = float(np.mean([max(s.count(1), s.count(-1), s.count(0)) / len(s) for s in signs.values()]))
    else:
        cons = float('nan')
    out['beta_sign_consistency'][f'ROI{roi}'] = {'value': cons, 'n_common': len(common)}

# ---- Holdout evaluation (frames 72/144/217, region-matched) ----
# Audit fix (finding #1/#2 ADOPTED): carry M3 intercept; fit M1/M2 independently (not M3 slices).
# Merging maps for holdout points reuse the FIT-time map (frozen at fit time), no leakage.

def fit_all(xx, yy, rr, res, w):
    """Refit M0..M3 independently on (xx,yy,rr,res), return coef maps + intercepts + merge maps."""
    cnt = defaultdict(int)
    for r in rr: cnt[int(r)] += 1
    valid = sorted(r for r, c in cnt.items() if c >= MIN_RING_PTS)
    rmap = {int(r): (int(r) if cnt[int(r)] >= MIN_RING_PTS else
                     min(valid, key=lambda v: (abs(v-int(r)), v))) for r in set(rr.tolist())}
    rings_m = np.array([rmap[int(a)] for a in rr])
    cmp_map = merge_cells(xx, yy, w)
    cells_m = [cmp_map[(int(np.floor(a/w)), int(np.floor(b/w)))] for a, b in zip(xx, yy)]
    rl = sorted(set(rings_m)); cl = Morton_r(cells_m)
    # M1
    A1, _ = design_m1(rings_m, rl); x1, _, _, _ = np.linalg.lstsq(A1, res, rcond=None)
    m1_map = {r: float(x1[i]) for i, r in enumerate(rl)}
    # M2
    A2, _ = design_m2(cells_m, cl); x2, _, _, _ = np.linalg.lstsq(A2, res, rcond=None)
    m2_map = {c: float(x2[i]) for i, c in enumerate(cl)}
    # M3 (intercept last col)
    A3, _ = design_m3(rings_m, cells_m, rl, cl); x3, _, _, _ = np.linalg.lstsq(A3, res, rcond=None)
    nb = len(rl) - 1
    m3_b = {r: (0.0 if i == 0 else float(x3[i-1])) for i, r in enumerate(rl)}
    m3_c = {c: (0.0 if i == 0 else float(x3[nb+i-1])) for i, c in enumerate(cl)}
    m3_I = float(x3[-1])
    return dict(rl=rl, cl=cl, rmap=rmap, cmap=cmp_map, rings_m=rings_m, cells_m=cells_m,
                m1_map=m1_map, m2_map=m2_map, m3_b=m3_b, m3_c=m3_c, m3_I=m3_I)

def Morton_r(cells_m):
    return sorted(set(cells_m), key=lambda c: (c[0] * 73856093 ^ c[1] * 19349663))

for roi in (1, 2, 3, 4):
    m = region_fit == roi
    xx, yy, rr, res = dx_fit[m], dy_fit[m], rings_fit[m], resid_fit[m]
    mh = region_h == roi
    if not mh.sum():
        continue
    xxh, yyh, rrh, resh = dx_h[mh], dy_h[mh], rings_h[mh], resid_h[mh]
    for w in WIDTHS:
        F = fit_all(xx, yy, rr, res, w)
        def cell_of(a, b):
            return F['cmap'].get((int(np.floor(a/w)), int(np.floor(b/w))), None)
        def ring_of(r):
            return F['rmap'].get(int(r), min(F['rl'], key=lambda v: (abs(v-int(r)), v)))
        pred0 = np.zeros(len(resh))
        pred1 = np.array([F['m1_map'].get(ring_of(r), 0.0) for r in rrh])
        pred2 = np.array([F['m2_map'].get(cell_of(a, b), 0.0) for a, b in zip(xxh, yyh)])
        pred3 = np.array([F['m3_b'].get(ring_of(r), 0.0) + F['m3_c'].get(cell_of(a, b), 0.0)
                          for r, a, b in zip(rrh, xxh, yyh)]) + F['m3_I']
        def rmse(p): return float(np.sqrt(np.mean((resh - p) ** 2)))
        out['holdout_eval'][f'ROI{roi}/w{w}'] = {
            'n': int(mh.sum()), 'rmse_M0': rmse(pred0), 'rmse_M1': rmse(pred1),
            'rmse_M2': rmse(pred2), 'rmse_M3': rmse(pred3), 'm3_intercept_m': F['m3_I'],
            'M3_le_best_single_x1.05': bool(rmse(pred3) <= min(rmse(pred1), rmse(pred2)) * 1.05),
        }

# ---- aggregate verdict logic ----
fdf = {}
for roi in (1, 2, 3, 4):
    for w in WIDTHS:
        key = f'ROI{roi}/w{w}'
        m = out['models'][key]
        rank_ok = m['M3']['M3_rank_ok'] if False else (m['M3']['rank'] == m['M3']['n_par'])
        cond_ok = m['M3']['cond'] < 1e4
        stab_ok = m['half_sample_corr_beta'] >= 0.9 and m['half_sample_corr_cell'] >= 0.9
        ds_ok = m['ds2_m3_vs_m1'] is not None and m['ds2_m3_vs_m1'] >= 0.20 and \
                m['ds2_m3_vs_m2'] is not None and m['ds2_m3_vs_m2'] >= 0.20
        fdf[key] = {'rank_ok': rank_ok, 'cond_ok': cond_ok, 'stab_ok': stab_ok, 'ds2_ok': ds_ok}
out['model_qual'] = fdf
json.dump(out, open('02_IDENTIFIABILITY_RESULTS.json', 'w'), indent=2, cls=Enc)
print('STEP2 done; keys:', len(out['models']))
for k, v in fdf.items():
    print(k, v)
