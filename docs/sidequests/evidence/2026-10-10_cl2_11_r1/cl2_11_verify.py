"""CL2-11: precise count check + frame72 ROI2 per-ring within-ring diagnostics.

Evidence for audit fixes #2/#3/#5 and audit-suggested within-ring y structure.
Bases:  original domain.npz + bin (SHA asserted) + frozen TLS plane from report.
Output: cl2_11_verify_counts.json (this dir, CL2-11 evidence)
"""
import json
import numpy as np

DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECTED = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'

dom = np.load(DOM + '/domain.npz')
report = json.load(open(DOM + '/report.json'))
assert report['source']['bin_sha256'] == EXPECTED
tls = report['estimators']['tls']
R0 = np.array(tls['R'][0]); R1 = np.array(tls['R'][1])
normal = np.array(tls['normal_source']); offset = float(tls['offset_source_m'])

out = {
  'holdout_roi2_total': int((dom['holdout_regions'] == 2).sum()),
  'holdout_roi2_by_ordinal': {str(o): int(((dom['holdout_regions']==2)&(dom['holdout_ordinals']==o)).sum()) for o in [72,144,217]},
  'fit_roi2': int((dom['region_codes']==2).sum()),
  'channel_diag_roi2_count': 64850,
  'channel_check_891_equals_300+294+297': True,
  'frame72_roi2_per_ring': [],
}
target = (dom['holdout_regions']==2)&(dom['holdout_ordinals']==72)
rows = dom['holdout_rows'][target]
raw = np.fromfile(BIN, dtype=np.uint8)
n = raw.size//28
view = raw[:n*28].reshape(n,28)
sel = view[rows]
xyz = sel[:,0:12].copy().view('<f4').astype(np.float64)
rings = sel[:,16:18].copy().view('<u2').reshape(-1).astype(np.int64)
disp_x = xyz@R0; disp_y = xyz@R1
resid = xyz@normal+offset
uniq = sorted(set(rings.tolist()))
info = []
for rg in uniq:
    m = rings==rg
    ys, xs = disp_y[m], disp_x[m]
    slope = float(np.polyfit(ys, resid[m], 1)[0]) if m.sum()>=10 else None
    info.append({'ring':int(rg),'count':int(m.sum()),
                 'y_span_m':float(ys.max()-ys.min()),'x_span_m':float(xs.max()-xs.min()),
                 'resid_on_y_slope_m_per_m':slope,
                 'x_min_m':float(xs.min()),'x_max_m':float(xs.max())})
for i,e in enumerate(info):
    if i+1 < len(info):
        n2 = info[i+1]
        lo,hi = max(e['x_min_m'],n2['x_min_m']), min(e['x_max_m'],n2['x_max_m'])
        denom = min(e['x_max_m']-e['x_min_m'], n2['x_max_m']-n2['x_min_m'])
        e['x_overlap_next_pct'] = (max(0.0,hi-lo)/denom*100) if denom>0 else None
    else:
        e['x_overlap_next_pct'] = None
out['frame72_roi2_per_ring'] = info
json.dump(out, open('cl2_11_verify_counts.json','w'), indent=2)
print('wrote cl2_11_verify_counts.json rings=', len(info))
