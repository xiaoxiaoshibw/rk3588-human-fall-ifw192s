"""CL2-13 minimal self-contained verification for the auditor.

Runs the 5 review-named recompute targets + F-AUTHOR-1 (the design-bug claim) with
NO dependency on 02_independent_recompute.py — everything is re-derived here from raw
bin + report.json so the auditor is running code they can read end-to-end in one screen.

Run: python -I 03_verify_minimal.py
"""
import json, hashlib
from collections import defaultdict
import numpy as np

DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECT_BIN = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()

print('== 1. asset SHA ==')
print('bin sha ok:', sha(BIN) == EXPECT_BIN)
print('npz sha ok:', sha(DOM + '/domain.npz') == '1cf1ea9c4856f2ddc36f58e23d3747bb9ecb391ac582e8dd3ebc3febd03b5c26')
print('report ok :', sha(DOM + '/report.json') == '9101d28a50c30e0210eb7eaca2b697b486517da000c660a89b34e82177b96214')

report = json.load(open(DOM + '/report.json'))
tls = report['estimators']['tls']
normal = np.array(tls['normal_source']); offset = float(tls['offset_source_m'])
dom = np.load(DOM + '/domain.npz')
raw = np.fromfile(BIN, dtype=np.uint8)
view = raw[:(raw.size // 28) * 28].reshape(-1, 28)

print('\n== 2. frozen regression frame72 ROI2 ==')
selh = view[dom['holdout_rows']]
xyh = selh[:, 0:12].copy().view('<f4').astype(np.float64)
resh = xyh @ normal + offset
region_h = dom['holdout_regions']; ord_h = dom['holdout_ordinals']
m72 = (region_h == 2) & (ord_h == 72)
r72 = resh[m72]
rms = float(np.sqrt(np.mean(r72 ** 2)))
p95 = float(np.quantile(np.abs(r72), 0.95, method='linear'))
print(f'n={m72.sum()} rms={rms} (frozen 0.027417988, diff={abs(rms-0.027417988):.3e})')
print(f'p95={p95} (frozen 0.050291869360, diff={abs(p95-0.050291869360):.3e})')

print('\n== 3. F-AUTHOR-1 design-bug reproduction ==')
R0 = np.array(tls['R'][0]); R1 = np.array(tls['R'][1])
sel = view[dom['source_rows']]
xyz = sel[:, 0:12].copy().view('<f4').astype(np.float64)
rings = sel[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
resid = xyz @ normal + offset
dx, dy = xyz @ R0, xyz @ R1
region = dom['region_codes']

def merge_rings(rr):
    cnt = defaultdict(int)
    for r in rr: cnt[int(r)] += 1
    valid = sorted(r for r, c in cnt.items() if c >= 50)
    return {int(r): (int(r) if cnt[int(r)] >= 50 else
            min(valid, key=lambda v: (abs(v - int(r)), v))) for r in set(rr.tolist())}

def merge_cells(xx, yy, w):
    ix = np.floor(xx / w).astype(np.int64); iy = np.floor(yy / w).astype(np.int64)
    pts = defaultdict(int)
    for a, b in zip(ix, iy): pts[(int(a), int(b))] += 1
    keep = {c for c, p in pts.items() if p >= 20} or {max(pts, key=lambda c: pts[c])}
    mp = {}
    for c in pts:
        if c in keep: mp[c] = c
        else:
            tgt = next((k for k in [(c[0]+1,c[1]),(c[0]-1,c[1]),(c[0],c[1]+1),(c[0],c[1]-1)] if k in keep), None)
            mp[c] = tgt if tgt is not None else min(keep, key=lambda k: (abs(k[0]-c[0])+abs(k[1]-c[1]), k))
    return mp

MORT = lambda c: (c[0] * 73856093 ^ c[1] * 19349663)

# == CL2-12 02_identifiability.py design_m3 VERBATIM (baseline-cell collides onto last ring dummy) ==
def design_m3_cl2(rings_m, cells_m, r_levels, c_levels):
    ridx = {r: i - 1 for i, r in enumerate(r_levels)}
    cidx = {c: (len(r_levels) - 1) + i - 1 for i, c in enumerate(c_levels)}
    n_par = (len(r_levels) - 1) + (len(c_levels) - 1) + 1
    A = np.zeros((len(rings_m), n_par)); A[:, -1] = 1.0
    for i, (r, c) in enumerate(zip(rings_m, cells_m)):
        if r in ridx: A[i, ridx[r]] = 1.0
        if c in cidx: A[i, cidx[c]] = 1.0
    return A

# == behaviorally-correct dropped-baseline (baseline cell -> NO column) ==
def design_m3_ok(rings_m, cells_m, r_levels, c_levels):
    nb = len(r_levels) - 1
    A = np.zeros((len(rings_m), nb + len(c_levels) - 1 + 1)); A[:, -1] = 1.0
    ri = {r: i - 1 for i, r in enumerate(r_levels)}
    ci = {c: nb + i - 1 for i, c in enumerate(c_levels)}
    for i, (r, c) in enumerate(zip(rings_m, cells_m)):
        if ri[r] >= 0: A[i, ri[r]] = 1.0
        if ci[c] >= nb: A[i, ci[c]] = 1.0
    return A

# == sum-to-zero contrast design (parametrization-independence cross-check) ==
def design_m3_s2z(rings_m, cells_m, r_levels, c_levels):
    g, c = len(r_levels), len(c_levels)
    Hr = np.eye(g)[:, :g - 1]; Hr[g - 1, :] = -1.0
    Hc = np.eye(c)[:, :c - 1]; Hc[c - 1, :] = -1.0
    ri = {r: i for i, r in enumerate(r_levels)}; ci = {cc: i for i, cc in enumerate(c_levels)}
    A = np.zeros((len(rings_m), (g - 1) + (c - 1) + 1)); A[:, -1] = 1.0
    for i, (r, cc) in enumerate(zip(rings_m, cells_m)):
        A[i, :g - 1] += Hr[ri[r]]; A[i, g - 1:g - 1 + c - 1] += Hc[ci[cc]]
    return A

roi2 = region == 2
xx, yy, rr, res = dx[roi2], dy[roi2], rings[roi2], resid[roi2]
rmap = merge_rings(rr); rings_m = np.array([rmap[int(a)] for a in rr], dtype=np.int64)
cmap = merge_cells(xx, yy, 0.05)
cells_m = [cmap[(int(np.floor(a / 0.05)), int(np.floor(b / 0.05)))] for a, b in zip(xx, yy)]
rl = sorted(set(rings_m.tolist()))
cl = sorted(set(cells_m), key=lambda c: (MORT(c), c))
print(f'ROI2/w0.05: n={len(res)}, g={len(rl)}, c={len(cl)}, baseline cell={cl[0]}')

A_cl2 = design_m3_cl2(rings_m, cells_m, rl, cl)
x_cl2, *_ = np.linalg.lstsq(A_cl2, res, rcond=None)
A_ok = design_m3_ok(rings_m, cells_m, rl, cl)
x_ok, *_ = np.linalg.lstsq(A_ok, res, rcond=None)
s_cl2 = float(np.mean((res - A_cl2 @ x_cl2) ** 2))
s_ok = float(np.mean((res - A_ok @ x_ok) ** 2))
print(f'sigma2 (CL2-12 design, bugged): {s_cl2*1e6:.2f} um^2   (published 142.56)')
print(f'sigma2 (correct design)      : {s_ok*1e6:.2f} um^2   (author claim 119.71)')
print(f'fitted values between two models max|diff| = {np.max(np.abs(A_cl2@x_cl2 - A_ok@x_ok)):.4f} m')
print(f'intercept (CL2-12 bugged): {x_cl2[-1]*1000:.1f} mm   (correct): {x_ok[-1]*1000:.1f} mm')

# where does baseline cell put its dummy?
cidx = {c: (len(rl) - 1) + i - 1 for i, c in enumerate(cl)}
print(f'baseline cell {cl[0]} maps to column index {cidx[cl[0]]} (0..{A_cl2.shape[1]-1}); '
      f'last ring dummy column is {len(rl)-2}  -> COLLIDES' if cidx[cl[0]] == len(rl) - 2 else '')

print('\n== 4. M1/M2 independence + frame holdout (ROI2/w0.05) ==')
# independent M1 (per-ring level means, no intercept) and M2 (per-cell level means, no intercept)
def fit_m1(rings_m, rl, res):
    A = np.zeros((len(rings_m), len(rl)))
    idx = {r: i for i, r in enumerate(rl)}
    for i, r in enumerate(rings_m): A[i, idx[r]] = 1.0
    x, *_ = np.linalg.lstsq(A, res, rcond=None)
    return {r: float(x[i]) for i, r in enumerate(rl)}
def fit_m2(cells_m, cl, res):
    A = np.zeros((len(cells_m), len(cl)))
    idx = {c: i for i, c in enumerate(cl)}
    for i, c in enumerate(cells_m): A[i, idx[c]] = 1.0
    x, *_ = np.linalg.lstsq(A, res, rcond=None)
    return {c: float(x[i]) for i, c in enumerate(cl)}
m1_map = fit_m1(rings_m, rl, res); m2_map = fit_m2(cells_m, cl, res)
mh2 = region_h == 2
xxh, yyh, rrh, rh = xyh @ R0, xyh @ R1, None, None
xyhh = xyh
# need holdout dx dy: recompute from holdout xyz
selh2 = view[dom['holdout_rows']]
xyh2 = selh2[:, 0:12].copy().view('<f4').astype(np.float64)
ringh = selh2[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
resh2 = xyh2 @ normal + offset
dxh = xyh2 @ R0; dyh = xyh2 @ R1
m2mask = (region_h == 2)
xx2, yy2, rr2, rh2 = dxh[m2mask], dyh[m2mask], ringh[m2mask], resh2[m2mask]
def ring_of(r):
    return rmap.get(int(r), min(rmap.values(), key=lambda v: (abs(v - int(r)), v)))
def cell_of(a, b):
    return cmap.get((int(np.floor(a / 0.05)), int(np.floor(b / 0.05))), None)
p1 = np.array([m1_map.get(ring_of(r), 0.0) for r in rr2])
p2 = np.array([m2_map.get(c, 0.0) if (c := cell_of(a, b)) is not None else 0.0 for a, b in zip(xx2, yy2)])
rm = lambda p: float(np.sqrt(np.mean((rh2 - p) ** 2)))
print(f'holdout M1 RMSE={rm(p1)*1000:.2f} mm (published 17.58);  M2 RMSE={rm(p2)*1000:.2f} mm (published 16.21)')

print('\n== 5. spatial Morton CV (ROI2/w0.05; M1 independent; M3 with bugged design as published) ==')
clabs = sorted(set(cells_m), key=lambda c: (MORT(c), c))
cf = {c: i % 5 for i, c in enumerate(clabs)}
fold = np.array([cf[c] for c in cells_m])
rl_full = sorted(set(rings_m.tolist())); cl_full = sorted(set(cells_m))
def fit_pred_space(tr, te):
    # M1
    Am1 = np.zeros((tr.sum(), len(rl_full)))
    idr = {r: i for i, r in enumerate(rl_full)}
    for i, r in enumerate(rings_m[tr]): Am1[i, idr[r]] = 1.0
    xm1, *_ = np.linalg.lstsq(Am1, res[tr], rcond=None)
    mm1 = {r: float(xm1[i]) for i, r in enumerate(rl_full)}
    p1 = np.array([mm1.get(int(r), 0.0) for r in rings_m[te]])
    # M3 bugged (CL2-12 publish semantics)
    cm_tr = [cells_m[i] for i in np.where(tr)[0]]
    cm_te = [cells_m[i] for i in np.where(te)[0]]
    # CL2-12 03_within_ring.py uses r_levels=sorted, c_levels=sorted(set) (NOT morton) for the
    # CV design; morton hash only selects the FOLD assignment. Match that exactly.
    cl_list = sorted(set(cells_m))
    A3 = design_m3_cl2(rings_m[tr], cm_tr, rl_full, cl_list)
    x3, *_ = np.linalg.lstsq(A3, res[tr], rcond=None)
    nb = len(rl_full) - 1
    bm = {r: (0.0 if i == 0 else x3[i - 1]) for i, r in enumerate(rl_full)}
    cm = {c: (0.0 if i == 0 else x3[nb + i - 1]) for i, c in enumerate(cl_list)}
    Ic = float(x3[-1])
    p3 = np.array([bm.get(int(r), 0.0) + cm.get(c, 0.0) for r, c in zip(rings_m[te], cm_te)]) + Ic
    return p1, p3
e1, e3 = [], []
for L in range(5):
    te = fold == L; tr = ~te
    if te.sum() == 0 or tr.sum() < 100: continue
    p1, p3 = fit_pred_space(tr, te)
    e1.append(np.mean((res[te] - p1) ** 2)); e3.append(np.mean((res[te] - p3) ** 2))
print(f'spatial5 M1 RMSE={np.sqrt(np.mean(e1))*1000:.2f} mm (published 18.22);  M3 RMSE={np.sqrt(np.mean(e3))*1000:.2f} mm (published 111.62, bugged design)')

print('\n== 6. confound correlations under the CORRECT design (for honest bookkeeping) ==')
nb = len(rl) - 1
beta_ok = {r: (0.0 if i == 0 else float(x_ok[i - 1])) for i, r in enumerate(rl)}
h_ok = {c: (0.0 if i == 0 else float(x_ok[nb + i - 1])) for i, c in enumerate(cl)}
bv = np.array([beta_ok[r] for r in rl]); riv = np.array(rl, dtype=float)
hv = np.array([h_ok[c] for c in cl]); civ = np.array([c[0] for c in cl], dtype=float)
print(f'correct-design corr(beta, ring_idx)={np.corrcoef(bv, riv)[0,1]:.4f} (bugged-design was 0.994)')
print(f'correct-design corr(h, cell_dx)   ={np.corrcoef(hv, civ)[0,1]:.4f} (bugged-design was -0.919)')

print('\n== 7. cross-checks the AUDITOR flagged as unsupported (ADOPT: landed in script) ==')
A_s2z = design_m3_s2z(rings_m, cells_m, rl, cl)
Q_ok, _ = np.linalg.qr(A_ok)
proj_res_correct = float(np.linalg.norm(A_s2z - Q_ok @ (Q_ok.T @ A_s2z), axis=0).max())
Q_cl2, _ = np.linalg.qr(A_cl2)
proj_res_bugged = float(np.linalg.norm(A_s2z - Q_cl2 @ (Q_cl2.T @ A_s2z), axis=0).max())
print(f's2z col projection residual onto CORRECT span: {proj_res_correct:.3e} (same-space -> ~1e-12)')
print(f's2z col projection residual onto BUGGED  span: {proj_res_bugged:.3e} (not same space -> O(1))')

beta_full = {r: (0.0 if i == 0 else float(x_ok[i - 1])) for i, r in enumerate(rl)}
h_full = {c: (0.0 if i == 0 else float(x_ok[nb + i - 1])) for i, c in enumerate(cl)}
p3_ok = np.array([beta_full.get(ring_of(r), 0.0) +
                  (h_full.get(c, 0.0) if (c := cell_of(a, b)) is not None else 0.0)
                  for r, a, b in zip(rr2, xx2, yy2)]) + float(x_ok[-1])
print(f'correct-design frame-holdout M3 RMSE (ROI2/w0.05) = {rm(p3_ok)*1000:.2f} mm '
      f'(bugged-design published 12.09; M1=17.58, M2=16.21 -> x1.05 gate passes either way)')

res2j = json.load(open(r'D:/Code/ldiar/docs/sidequests/evidence/2026-10-10_cl2_12_r1/02_IDENTIFIABILITY_RESULTS.json'))
he = res2j['holdout_eval']
n_pass = sum(1 for v in he.values() if v['M3_le_best_single_x1.05'])
print(f'x1.05 PASS count from CL2-12 bugged holdout_eval: {n_pass}/12 '
      f'(CL2-12 04/Final text says "8/12 FAIL" = 4 PASS; actual JSON is {12-n_pass} FAIL)')

print('\nVERIFICATION SCRIPT DONE. Compare against published numbers in 02/03 JSON.')
