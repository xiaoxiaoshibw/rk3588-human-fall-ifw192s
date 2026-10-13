"""CL2-13A author-side INDEPENDENT recompute of CL2-12 corrected numbers.

Independence claims (pre-registered 00/I131):
- Data path re-derived from raw bin + report.json (normal/offset/R0/R1), not from CL2-12 outputs.
- NEW FINDING (this round, author-side, DISCLOSED not hidden): CL2-12's corrected `design_m3`
  STILL carries a baseline-index collision. `ridx={r:i-1}` / `cidx={c:(g-1)+i-1}` mean the
  BASELINE cell maps to column `g-2` — the LAST RING dummy — so baseline-cell rows spuriously
  add the last ring's effect. (The baseline RING's ridx=-1 points to column -1 i.e. the
  intercept column, but that column is already 1.0 and A[i,-1]=1.0 is a same-value rewrite,
  so it does NOT change the design space. The only real collision is baseline-cell -> last
  ring dummy.) Verified by three independent routes in this directory:
    (1) design diff vs a correctly-built dropped-baseline design: fitted values differ by
        max 0.0816 m; (2) sigma2 inflated 142.6 -> (correct) 119.7 um^2 on ROI2/w0.05
        (equals 02 JSON exactly: 0.000142565/0.000119706); (3) QR projection residual of
        sum-to-zero coding onto CL2-12's design span = 13.3 (not same space) vs 5.5e-12
        onto the correct design.
  Effect boundary: affects ONLY groups whose baseline-cell dummy would collide — 8 of 12
  groups unchanged (sigma2 identical), ROI2 all 3 scales + ROI3/w0.15/ROI4/w0.15 changed.
  EVERY published sigma2 drop gate (>=20%) verdict is preserved with zero flips; the M3
  holdout superiority over M1/M2 and the spatial-extrapolation FAIL direction are also
  preserved (only magnitudes shift). Frame72 frozen regression uses raw bin directly and is
  UNAFFECTED. This finding does NOT repair CL2-12 in place (its seal is untouchable); it is
  registered here, independent-audited below, and must be carried into CL2-13 return.
- Morton fold: re-derived from frozen hash (ix*73856093 ^ iy*19349663), ties broken by tuple;
  fold = rank % 5. Matches CL2-12 line `sorted(set(cells), key=lambda c:(hash, c))` then i%5.
- Holdout/intercept/RMSE recomputed with independent M1/M2 level-mean encoding (no intercept),
  M3 with dropped-baseline dummies + intercept (same as corrected CL2-12).

Gates (00/A-pack): unless noted, match = |recompute - published| < 1e-6 m (or as stated).
"""
import json, hashlib, os
from collections import defaultdict
import numpy as np

E = os.path.dirname(os.path.abspath(__file__))
C12 = r'D:/Code/ldiar/docs/sidequests/evidence/2026-10-10_cl2_12_r1'
DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECT_BIN = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'
EXPECT_NPZ = '1cf1ea9c4856f2ddc36f58e23d3747bb9ecb391ac582e8dd3ebc3febd03b5c26'
EXPECT_RPT = '9101d28a50c30e0210eb7eaca2b697b486517da000c660a89b34e82177b96214'
WIDTHS = [0.05, 0.10, 0.15]
MIN_RING_PTS, MIN_CELL_PTS = 50, 20
TOL = 1e-6

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()

out = {'checks': {}, 'manifest': {}, 'tables': {}}

# ---- 1. external SHA re-verify ----
out['checks']['bin_sha_ok'] = sha(BIN) == EXPECT_BIN
out['checks']['npz_sha_ok'] = sha(DOM + '/domain.npz') == EXPECT_NPZ
out['checks']['report_sha_ok'] = sha(DOM + '/report.json') == EXPECT_RPT

report = json.load(open(DOM + '/report.json'))
assert report['source']['bin_sha256'] == EXPECT_BIN
tls = report['estimators']['tls']
R0 = np.array(tls['R'][0]); R1 = np.array(tls['R'][1])
normal = np.array(tls['normal_source']); offset = float(tls['offset_source_m'])

dom = np.load(DOM + '/domain.npz')
raw = np.fromfile(BIN, dtype=np.uint8)
view = raw[:(raw.size // 28) * 28].reshape(-1, 28)

def load(rows):
    sel = view[rows]
    xyz = sel[:, 0:12].copy().view('<f4').astype(np.float64)
    rings = sel[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
    return xyz, rings

xyz_f, rings_f = load(dom['source_rows'])
resid_f = xyz_f @ normal + offset
dx_f, dy_f = xyz_f @ R0, xyz_f @ R1
region_f, ord_f = dom['region_codes'], dom['frame_ordinals']
xyz_h, rings_h = load(dom['holdout_rows'])
resid_h = xyz_h @ normal + offset
dx_h, dy_h = xyz_h @ R0, xyz_h @ R1
region_h, ord_h = dom['holdout_regions'], dom['holdout_ordinals']

# ---- 2. frozen regression frame72 ROI2 ----
m72 = (region_h == 2) & (ord_h == 72)
r72 = resid_h[m72]
rms72 = float(np.sqrt(np.mean(r72 ** 2)))
p95_72 = float(np.quantile(np.abs(r72), 0.95, method='linear'))
out['checks']['frozen_regression'] = {
    'n': int(m72.sum()), 'rms_m': rms72, 'p95_abs_m': p95_72,
    'rms_frozen_m': 0.027417988, 'p95_frozen_m': 0.05029186936,
    'rms_diff': abs(rms72 - 0.027417988), 'p95_diff': abs(p95_72 - 0.05029186936),
    'rms_match': abs(rms72 - 0.027417988) < 1e-9, 'p95_match': abs(p95_72 - 0.05029186936) < 1e-9}

# ---- 3. manifest re-verify (CL2-12) ----
man = json.load(open(C12 + '/07_EVIDENCE_MANIFEST.json'))
mism = []
for fn, expect in man['files'].items():
    p = os.path.join(C12, fn)
    if not os.path.isfile(p): mism.append((fn, 'MISSING')); continue
    if sha(p) != expect: mism.append((fn, 'SHA_DIFF'))
out['checks']['cl2_12_manifest_mismatch'] = mism
out['checks']['cl2_12_manifest_ok'] = (len(mism) == 0)

# ---- shared grouping (re-implemented; must match frozen CL2-12 rules) ----
def merge_rings(rr):
    cnt = defaultdict(int)
    for r in rr: cnt[int(r)] += 1
    valid = sorted(r for r, c in cnt.items() if c >= MIN_RING_PTS)
    return {int(r): (int(r) if cnt[int(r)] >= MIN_RING_PTS else
                     min(valid, key=lambda v: (abs(v - int(r)), v))) for r in set(rr.tolist())}

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

MORT = lambda c: (c[0] * 73856093 ^ c[1] * 19349663)
def morton_levels(cells_m):
    return sorted(set(cells_m), key=lambda c: (MORT(c), c))

# ---- independent design builders ----
def design_m1_mean(rings_m, rl):     # per-level mean encoding (no intercept)
    A = np.zeros((len(rings_m), len(rl)))
    idx = {r: i for i, r in enumerate(rl)}
    for i, r in enumerate(rings_m): A[i, idx[r]] = 1.0
    return A

def design_m2_mean(cells_m, cl):
    A = np.zeros((len(cells_m), len(cl)))
    idx = {c: i for i, c in enumerate(cl)}
    for i, c in enumerate(cells_m): A[i, idx[c]] = 1.0
    return A

def design_m3_db(rings_m, cells_m, rl, cl):  # dropped-baseline + intercept; faithfully copies
    # BUGGED CL2-12 design (audit §3.1 ADOPT: reproduces published bug, not a fix)
    nb, nc = len(rl) - 1, len(cl) - 1
    A = np.zeros((len(rings_m), nb + nc + 1)); A[:, -1] = 1.0
    ri = {r: i - 1 for i, r in enumerate(rl)}
    ci = {c: nb + i - 1 for i, c in enumerate(cl)}
    for i, (r, c) in enumerate(zip(rings_m, cells_m)):
        if r in ri: A[i, ri[r]] = 1.0
        if c in ci: A[i, ci[c]] = 1.0
    return A

def design_m3_s2z(rings_m, cells_m, rl, cl):  # sum-to-zero contrast parametrization
    g, c = len(rl), len(cl)
    Hr = np.eye(g)[:, :g - 1]; Hr[g - 1, :] = -1.0
    Hc = np.eye(c)[:, :c - 1]; Hc[c - 1, :] = -1.0
    ri = {r: i for i, r in enumerate(rl)}
    ci = {cc: i for i, cc in enumerate(cl)}
    A = np.zeros((len(rings_m), (g - 1) + (c - 1) + 1)); A[:, -1] = 1.0
    for i, (r, cc) in enumerate(zip(rings_m, cells_m)):
        A[i, :g - 1] += Hr[ri[r]]
        A[i, g - 1:g - 1 + c - 1] += Hc[ci[cc]]
    return A

def ols_svd(A, y):
    return np.linalg.lstsq(A, y, rcond=None)

# ---- 4. main loops: fit + holdout + identity + spatial CV ----
res2 = json.load(open(C12 + '/02_IDENTIFIABILITY_RESULTS.json'))
res3 = json.load(open(C12 + '/03_WITHIN_RING_DATA.json'))

hold_keys = list(res2['holdout_eval'].keys())
recompute_hold = {}
summ_tbl = []
for roi in (1, 2, 3, 4):
    m = region_f == roi
    xx, yy, rr, res = dx_f[m], dy_f[m], rings_f[m], resid_f[m]
    oo = ord_f[m]
    rmap = merge_rings(rr)
    rings_m = np.array([rmap[int(a)] for a in rr], dtype=np.int64)
    mh = region_h == roi
    for w in WIDTHS:
        cmap = merge_cells(xx, yy, w)
        cells_m = [cmap[(int(np.floor(a / w)), int(np.floor(b / w)))] for a, b in zip(xx, yy)]
        rl = sorted(set(rings_m.tolist()))
        cl = morton_levels(cells_m)
        # independent M3 fit (dropped-baseline)
        A3 = design_m3_db(rings_m, cells_m, rl, cl)
        x3, *_ = ols_svd(A3, res)
        nb = len(rl) - 1
        beta = {r: (0.0 if i == 0 else float(x3[i - 1])) for i, r in enumerate(rl)}
        hc = {c: (0.0 if i == 0 else float(x3[nb + i - 1])) for i, c in enumerate(cl)}
        I_solver = float(x3[-1])
        # first-principles order identity (tolerance-limited, see header)
        n_r = defaultdict(int); n_c = defaultdict(int)
        for r in rings_m: n_r[int(r)] += 1
        for c in cells_m: n_c[c] += 1
        mB = sum(beta[g] * n_r[g] for g in rl) / len(res)
        mH = sum(hc[c] * n_c[c] for c in cl) / len(res)
        I_ident = float(res.mean() - mB - mH)
        # sharp independent check: sum-to-zero reparametrization spans the same column space
        # as dropped-baseline. The two are teorically identical; numerically the redundant
        # sv of the joint matrix is f64-partition noise. Noise magnitude here is ~1e-12..-13
        # while the smallest real singular value is O(1-10) — a ~12-order gap. A fixed
        # absolute tolerance must clear the noise floor but stay far below real signal:
        # 1e-8 is contaminated by worst-case 2.9e-12 noise? No — 2.9e-12 < 1e-8, so the
        # noise sv IS below 1e-8 and correctly excluded; but M3 cond ~149 inflates the noise
        # from 1e-13 to ~3e-12, still < 1e-8. Use 1e-6 (100x above observed max noise 2.9e-12,
        # 6 orders below smallest real 6.05) for robust margin across all 12 groups.
        A3s = design_m3_s2z(rings_m, cells_m, rl, cl)
        # Column-space equivalence via ORTHOGONAL PROJECTION residual (robust — no rank
        # tolerance needed): project every s2z column onto span(A3); if the two span the same
        # space the residual is f64 noise (~1e-12). A real dimensional mismatch would leave a
        # column with residual O(column norm) ~ O(1).
        Q_db, _ = np.linalg.qr(A3)
        proj_residual = float(np.linalg.norm(A3s - Q_db @ (Q_db.T @ A3s), axis=0).max())
        # also record joint singular spectrum for the report (gap visualization)
        joint_sv = np.linalg.svd(np.hstack([A3, A3s]), compute_uv=False)
        real_sv = joint_sv[joint_sv > 1e-6]
        noise_max = float(joint_sv[joint_sv <= 1e-6].max()) if (joint_sv <= 1e-6).any() else 0.0
        smallest_real = float(real_sv.min())
        colspace_same = (proj_residual < 1e-6)
        pred_equiv = None
        # holdout
        keyw = f'ROI{roi}/w{w:g}'.replace('0.0', '0.0')  # normalize below
        # build both possible key spellings for published lookup
        kk1, kk2 = f'ROI{roi}/w{w}', f'ROI{roi}/w{w:g}'
        pub = res2['holdout_eval'].get(kk1) or res2['holdout_eval'].get(kk2)
        hrow = {}
        if mh.sum():
            xxh, yyh, rrh, resh = dx_h[mh], dy_h[mh], rings_h[mh], resid_h[mh]
            def ring_of(r):
                return rmap.get(int(r), min(rmap.values(), key=lambda v: (abs(v - int(r)), v)))
            def cell_of(a, b):
                return cmap.get((int(np.floor(a / w)), int(np.floor(b / w))), None)
            # independent M1/M2 fits (level-mean encoding, no intercept)
            A1 = design_m1_mean(rings_m, rl); x1, *_ = ols_svd(A1, res)
            A2 = design_m2_mean(cells_m, cl); x2, *_ = ols_svd(A2, res)
            m1_map = {r: float(x1[i]) for i, r in enumerate(rl)}
            m2_map = {c: float(x2[i]) for i, c in enumerate(cl)}
            pred1 = np.array([m1_map.get(ring_of(r), 0.0) for r in rrh])
            pred2 = np.array([m2_map.get(c, 0.0) if (c := cell_of(a, b)) is not None else 0.0
                              for a, b in zip(xxh, yyh)])
            pred3 = np.array([beta.get(ring_of(r), 0.0) + (hc.get(c, 0.0) if (c := cell_of(a, b)) is not None else 0.0)
                              for r, a, b in zip(rrh, xxh, yyh)]) + I_solver
            rm = lambda p: float(np.sqrt(np.mean((resh - p) ** 2)))
            hrow = {'n': int(mh.sum()), 'rmse_M0': rm(np.zeros(len(resh))), 'rmse_M1': rm(pred1),
                    'rmse_M2': rm(pred2), 'rmse_M3': rm(pred3), 'm3_intercept_m': I_solver,
                    'intercept_order_residual': abs(I_solver - I_ident),
                    'intercept_order_ok': abs(I_solver - I_ident) < 1e-3,
                    'm3_proj_residual_max': proj_residual,
                    'm3_n_par': int(A3.shape[1]),
                    'm3_joint_sv_smallest_real': smallest_real,
                    'm3_joint_sv_max_noise': noise_max,
                    'm3_colspace_same': colspace_same,
                    'x1_05_pass': bool(rm(pred3) <= min(rm(pred1), rm(pred2)) * 1.05)}
            # match to published corrected values
            for kk in ('M0', 'M1', 'M2', 'M3'):
                pub_v = pub['rmse_' + kk]
                hrow['diff_' + kk] = abs(hrow['rmse_' + kk] - pub_v)
                hrow['match_' + kk] = hrow['diff_' + kk] < TOL
            hrow['diff_I'] = abs(hrow['m3_intercept_m'] - pub['m3_intercept_m'])
            hrow['match_I'] = hrow['diff_I'] < 1e-9
            hrow['match_pass_flag'] = (hrow['x1_05_pass'] == bool(pub['M3_le_best_single_x1.05']))
        recompute_hold[f'ROI{roi}/w{w:g}'] = hrow
        summ_tbl.append([f'ROI{roi}/w{w:g}', hrow.get('rmse_M1'), hrow.get('rmse_M2'),
                         hrow.get('rmse_M3'), I_solver, I_ident])
out['tables']['holdout_recompute'] = recompute_hold

# ---- 5. spatial Morton 5-fold CV (independent re-derivation) ----
recompute_cv = {}
for roi in (1, 2, 3, 4):
    m = region_f == roi
    xx, yy, rr, res, oo = dx_f[m], dy_f[m], rings_f[m], resid_f[m], ord_f[m]
    rmap = merge_rings(rr)
    rings_m = np.array([rmap[int(a)] for a in rr], dtype=np.int64)
    for w in WIDTHS:
        cmap = merge_cells(xx, yy, w)
        cells_m = [cmap[(int(np.floor(a / w)), int(np.floor(b / w)))] for a, b in zip(xx, yy)]
        rl = sorted(set(rings_m.tolist())); cl = sorted(set(cells_m))
        clabs = sorted(set(cells_m), key=lambda c: (MORT(c), c))
        cf = {c: i % 5 for i, c in enumerate(clabs)}
        fold = np.array([cf[c] for c in cells_m])
        rec = {mn: [] for mn in ('M0', 'M1', 'M2', 'M3')}
        for L in range(5):
            te = fold == L; tr = ~te
            if te.sum() == 0 or tr.sum() < 100: continue
            cm_tr = [cells_m[i] for i in np.where(tr)[0]]
            cm_te = [cells_m[i] for i in np.where(te)[0]]
            r_levels = sorted(set(rings_m.tolist())); c_levels = sorted(set(cells_m))
            # M0
            A = np.ones((tr.sum(), 1)); xh, *_ = ols_svd(A, res[tr])
            rec['M0'].append(float(np.mean((res[te] - xh[0]) ** 2)))
            # M1
            A = design_m1_mean(rings_m[tr], r_levels); xh, *_ = ols_svd(A, res[tr])
            mm = {r: xh[i] for i, r in enumerate(r_levels)}
            pred = np.array([mm.get(int(r), 0.0) for r in rings_m[te]])
            rec['M1'].append(float(np.mean((res[te] - pred) ** 2)))
            # M2
            A = design_m2_mean(cm_tr, c_levels); xh, *_ = ols_svd(A, res[tr])
            mm = {c: xh[i] for i, c in enumerate(c_levels)}
            pred = np.array([mm.get(c, 0.0) for c in cm_te])
            rec['M2'].append(float(np.mean((res[te] - pred) ** 2)))
            # M3 (dropped-baseline + intercept)
            A = design_m3_db(rings_m[tr], cm_tr, r_levels, c_levels); xh, *_ = ols_svd(A, res[tr])
            nb = len(r_levels) - 1
            bm = {r: (0.0 if i == 0 else xh[i - 1]) for i, r in enumerate(r_levels)}
            cm = {c: (0.0 if i == 0 else xh[nb + i - 1]) for i, c in enumerate(c_levels)}
            Ic = float(xh[-1])
            pred = np.array([bm.get(int(r), 0.0) + cm.get(c, 0.0) for r, c in zip(rings_m[te], cm_te)]) + Ic
            rec['M3'].append(float(np.mean((res[te] - pred) ** 2)))
        row = {mn: float(np.sqrt(np.mean(v))) for mn, v in rec.items()}
        pub = res3['cv'][f'ROI{roi}/w{w:g}']['spatial5']
        row['match_M1'] = abs(row['M1'] - pub['M1']) < TOL
        row['match_M2'] = abs(row['M2'] - pub['M2']) < TOL
        row['match_M3'] = abs(row['M3'] - pub['M3']) < TOL
        row['pub_M1'], row['pub_M2'], row['pub_M3'] = pub['M1'], pub['M2'], pub['M3']
        recompute_cv[f'ROI{roi}/w{w:g}'] = row
out['tables']['spatial_cv_recompute'] = recompute_cv

# ---- 6. auxiliary: beta/dx & h/dx correlations (ROI2/w0.05) ----
roi, w = 2, 0.05
m = region_f == roi
xx, yy, rr, res = dx_f[m], dy_f[m], rings_f[m], resid_f[m]
rmap = merge_rings(rr); rings_m = np.array([rmap[int(a)] for a in rr], dtype=np.int64)
cmap = merge_cells(xx, yy, w)
cells_m = [cmap[(int(np.floor(a / w)), int(np.floor(b / w)))] for a, b in zip(xx, yy)]
rl = sorted(set(rings_m.tolist())); cl = morton_levels(cells_m)
A3 = design_m3_db(rings_m, cells_m, rl, cl); x3, *_ = ols_svd(A3, res)
nb = len(rl) - 1
beta = {r: (0.0 if i == 0 else float(x3[i - 1])) for i, r in enumerate(rl)}
hc = {c: (0.0 if i == 0 else float(x3[nb + i - 1])) for i, c in enumerate(cl)}
# ring index vs beta correlation
bv = np.array([beta[r] for r in rl]); ri = np.array(rl, dtype=float)
corr_beta_ring = float(np.corrcoef(bv, ri)[0, 1])
# cell dx index vs h
hv = np.array([hc[c] for c in cl]); cx = np.array([c[0] for c in cl], dtype=float)
corr_h_dx = float(np.corrcoef(hv, cx)[0, 1])
out['tables']['confound'] = {'corr_beta_vs_ringidx': corr_beta_ring, 'corr_h_vs_celldx': corr_h_dx}

# ---- aggregate verdicts ----
chk = out['checks']
fr = chk['frozen_regression']
hold_ok = all(all(v.get('match_' + kk, True) for kk in ('M0', 'M1', 'M2', 'M3', 'I', 'pass_flag'))
              for v in recompute_hold.values() if v)
cv_ok = all(v['match_M1'] and v['match_M2'] and v['match_M3'] for v in recompute_cv.values())
ident_colspace_ok = all(v.get('m3_colspace_same', True) for v in recompute_hold.values() if v)
out['verdicts'] = {
    'frozen_regression': 'VERIFIED' if (fr['rms_match'] and fr['p95_match']) else 'MISMATCH',
    'cl2_12_manifest': 'VERIFIED' if chk['cl2_12_manifest_ok'] else 'MISMATCH',
    'external_sha': 'VERIFIED' if (chk['bin_sha_ok'] and chk['npz_sha_ok'] and chk['report_sha_ok']) else 'MISMATCH',
    'holdout_numerics': 'VERIFIED' if hold_ok else 'MISMATCH',
    'intercept_pred_equiv_colspace': 'VERIFIED' if ident_colspace_ok else 'MISMATCH',
    'spatial_cv': 'VERIFIED' if cv_ok else 'MISMATCH',
}
json.dump(out, open(os.path.join(E, '02_RECOMPUTE_RESULTS.json'), 'w'), indent=2, default=str)
print('RECOMPUTE DONE')
for k, v in out['verdicts'].items(): print(f'{k}: {v}')
print('hold sample ROI2/w0.05:', json.dumps(recompute_hold.get('ROI2/w0.05'), default=str)[:300])
print('cv sample ROI2/w0.05:', json.dumps({k: v for k, v in recompute_cv['ROI2/w0.05'].items() if not k.startswith('match')}, default=str))
print('proj residual ROI2/w0.05:', recompute_hold['ROI2/w0.05']['m3_proj_residual_max'],
      'n_par:', recompute_hold['ROI2/w0.05']['m3_n_par'],
      'sv smallest real:', recompute_hold['ROI2/w0.05']['m3_joint_sv_smallest_real'],
      'sv max noise:', recompute_hold['ROI2/w0.05']['m3_joint_sv_max_noise'])
print('confound:', out['tables']['confound'])
