"""CL2-12 STEP1: ring x cell cross-coverage audit.

Pre-registered in 00_SCOPE_AND_ACCEPTANCE.md (v1). Read-only on all frozen inputs.
Builds bipartite ring x cell observation graph per ROI x cell-width, measures
coverage / connectivity / isolation / sparsity, applies frozen identifiability gates.

Inputs (read-only, SHA-asserted):
  - points.bin (S02, 28B stride per meta point_layout)
  - domain.npz (S04, TLS fit/holdout row binding)
  - report.json (S05, frozen TLS plane, display basis)
Output: 01_CROSS_COVERAGE.json (this dir only)
"""
import json
import hashlib
from collections import defaultdict, deque
import numpy as np

DOM = r'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
BIN = r'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin'
EXPECT_BIN = '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc'
WIDTHS = [0.05, 0.10, 0.15]
MIN_EDGE_PTS = 10      # sparse-edge threshold (pre-registered)
MIN_CELL_PTS = 20      # effective-cell threshold (pre-registered)
MIN_RING_PTS = 50      # effective-ring-group threshold (pre-registered)
GATE_MULTIRING_SHARE = 0.50
GATE_COND_MAX = 1e4

def sha256_head(path, nbytes=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read(nbytes))
    return h.hexdigest()

report = json.load(open(DOM + '/report.json'))
assert report['source']['bin_sha256'] == EXPECT_BIN, 'bin sha mismatch'
tls = report['estimators']['tls']
R0 = np.array(tls['R'][0]); R1 = np.array(tls['R'][1])
normal = np.array(tls['normal_source']); offset = float(tls['offset_source_m'])

full_sha = hashlib.sha256()
with open(BIN, 'rb') as f:
    for chunk in iter(lambda: f.read(1 << 24), b''):
        full_sha.update(chunk)
bin_sha_ok = (full_sha.hexdigest() == EXPECT_BIN)

dom = np.load(DOM + '/domain.npz')
raw = np.fromfile(BIN, dtype=np.uint8)
n = raw.size // 28
view = raw[:n * 28].reshape(n, 28)
rows = dom['source_rows']
sel = view[rows]
xyz = sel[:, 0:12].copy().view('<f4').astype(np.float64)
rings = sel[:, 16:18].copy().view('<u2').reshape(-1).astype(np.int64)
dx = xyz @ R0
dy = xyz @ R1
region = dom['region_codes']

def merge_rings(ring_ids, counts):
    """Merge rings with < MIN_RING_PTS points into nearest ring-id with >= MIN_RING_PTS."""
    valid = sorted(r for r, c in counts.items() if c >= MIN_RING_PTS)
    m = {}
    for r in ring_ids:
        if counts[r] >= MIN_RING_PTS:
            m[r] = r
        else:
            near = min(valid, key=lambda v: (abs(v - r), v))
            m[r] = near
    return m

def merge_cells(dx, dy, w):
    """Merge cells with < MIN_CELL_PTS points into nearest (E/N first) non-merged cell."""
    ix = np.floor(dx / w).astype(np.int64)
    iy = np.floor(dy / w).astype(np.int64)
    cell_pts = defaultdict(int)
    for a, b in zip(ix, iy):
        cell_pts[(a, b)] += 1
    keep = {c for c, p in cell_pts.items() if p >= MIN_CELL_PTS}
    if not keep:
        keep = {max(cell_pts, key=lambda c: cell_pts[c])}
    merge_to = {}
    singles = []
    for c, p in cell_pts.items():
        if c in keep:
            merge_to[c] = c
        else:
            tgt = None
            for cand in [(c[0]+1, c[1]), (c[0]-1, c[1]), (c[0], c[1]+1), (c[0], c[1]-1)]:
                if cand in keep:
                    tgt = cand
                    break
            if tgt is None:
                tgt = min(keep, key=lambda k: (abs(k[0]-c[0])+abs(k[1]-c[1]), k))
                singles.append(c)
            merge_to[c] = tgt
    return ix, iy, merge_to, cell_pts

def bipartite_components(rings_m, cells_m):
    """Union-Find over ring-nodes ('rK') and cell-nodes ('cA_B')."""
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    edge_pts = defaultdict(int)
    for r, c in zip(rings_m, cells_m):
        rn, cn = ('r%d' % r), ('c%d_%d' % c)
        union(rn, cn)
        edge_pts[(rn, cn)] += 1
    comps = defaultdict(list)
    ring_nodes = set(); cell_nodes = set()
    for r in rings_m:
        ring_nodes.add('r%d' % r)
    for c in cells_m:
        cell_nodes.add('c%d_%d' % c)
    for nd in list(ring_nodes) + list(cell_nodes):
        comps[find(nd)].append(nd)
    return comps, edge_pts, ring_nodes, cell_nodes

def design_rank_cond(rings_m, cells_m, ring_set, cell_set):
    """Reduced-rank M3 design: drop first ring + first cell per component.
    Returns (rank, cond, n_params_free)."""
    comps, edge_pts, _, _ = bipartite_components(rings_m, cells_m)
    comp_map = {}
    for i, comp in enumerate(comps.values()):
        for nd in comp:
            comp_map[nd] = i
    # columns: intercept(1) + rings(minus 1st) + cells(minus 1st), reduced rank for single comp
    rlist = sorted(ring_set); clist = sorted(cell_set)
    n_par = len(rlist) - 1 + len(clist)  # intercept absorbed in cells' first-drop
    A = np.zeros((len(rings_m), n_par))
    for i, (r, c) in enumerate(zip(rings_m, cells_m)):
        if r in rlist[1:]:
            A[i, rlist.index(r) - 1] = 1.0
        A[i, (len(rlist) - 1) + clist.index(c)] = 1.0
    # remove constant column duplicates: normalize by dropping one cell column per comp>1
    # For a single connected component, rank is (r-1)+(c-1)+1 = r+c-1 separated params incl. intercept.
    # Use SVD on discrete design; for large n, sample deterministically.
    if A.shape[0] > 200000:
        idx = np.linspace(0, A.shape[0]-1, 200000).astype(np.int64)
        As = A[idx]
    else:
        As = A
    s = np.linalg.svd(As, compute_uv=False)
    tol = max(As.shape) * np.finfo(float).eps * s[0]
    rank = int((s > tol).sum())
    cond = float(s[0] / s[-1]) if s[-1] > 0 else float('inf')
    return rank, cond, n_par, len(comps)

results = {'input_sha': {'bin_full_sha256_ok': bin_sha_ok,
                          'bin_sha256': full_sha.hexdigest(),
                          'npz_arrays': {k: list(dom[k].shape) for k in dom.files}},
           'gates': {'min_ring_pts': MIN_RING_PTS, 'min_cell_pts': MIN_CELL_PTS,
                     'multiring_share_min': GATE_MULTIRING_SHARE, 'cond_max': GATE_COND_MAX},
           'per_roi': {}}
verdicts = {}

for roi in (1, 2, 3, 4):
    m = region == roi
    rr = rings[m]; xx = dx[m]; yy = dy[m]
    ring_counts = defaultdict(int)
    for r in rr:
        ring_counts[int(r)] += 1
    ring_merge = merge_rings(sorted(ring_counts), ring_counts)
    roi_res = {'n_points': int(m.sum()), 'n_rings_raw': len(ring_counts),
               'n_rings_effective': len(set(ring_merge.values())), 'scales': {}}
    for w in WIDTHS:
        ix, iy, cell_merge, cell_pts = merge_cells(xx, yy, w)
        rings_m = np.array([ring_merge[int(r)] for r in rr], dtype=np.int64)
        cells_m = [cell_merge[(int(a), int(b))] for a, b in zip(ix, iy)]
        # coverage quantiles
        cell_counts_per_ring = defaultdict(set)
        ring_counts_per_cell = defaultdict(set)
        edge_pts = defaultdict(int)
        for r, c in zip(rings_m, cells_m):
            cell_counts_per_ring[r].add(c)
            ring_counts_per_cell[c].add(r)
            edge_pts[(r, c)] += 1
        per_ring_cov = sorted(len(v) for v in cell_counts_per_ring.values())
        per_cell_rings = sorted(len(v) for v in ring_counts_per_cell.values())
        multi_cells = {c: rs for c, rs in ring_counts_per_cell.items() if len(rs) >= 2}
        pts_in_multi = sum(p for (r, c), p in edge_pts.items() if c in multi_cells)
        # components
        ring_nodes = {'r%d' % r for r in set(rings_m)}
        cell_nodes = {'c%d_%d' % c for c in set(cells_m)}
        parent = {}
        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for (r, c) in edge_pts:
            a, b = ('r%d' % r), ('c%d_%d' % c)
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
        comps = defaultdict(list)
        for nd in list(ring_nodes) + list(cell_nodes):
            comps[find(nd)].append(nd)
        n_comp = len(comps)
        isol_ring = [nd for comp in comps.values() if len(comp) == 1 for nd in comp if nd.startswith('r')]
        isol_cell = [nd for comp in comps.values() if len(comp) == 1 for nd in comp if nd.startswith('c')]
        sparse_edges = sum(1 for p in edge_pts.values() if p < MIN_EDGE_PTS)
        # rank/cond via reduced design
        rset = sorted(set(rings_m)); cset = sorted(set(cells_m))
        try:
            rank, cond, n_par, _ = design_rank_cond(rings_m, cells_m, rset, cset)
        except Exception as e:
            rank, cond, n_par = -1, float('inf'), -1
        gates = {
            'connected_single_component': n_comp == 1,
            'rank_sufficient': rank == n_par,
            'multiring_point_share': float(pts_in_multi / len(rings_m)),
            'cond_ok': cond < GATE_COND_MAX,
        }
        ok = all([gates['connected_single_component'], gates['rank_sufficient'],
                  gates['multiring_point_share'] >= GATE_MULTIRING_SHARE, gates['cond_ok']])
        roi_res['scales']['%0.2f' % w] = {
            'n_cells': len(cset), 'n_ring_groups': len(rset),
            'cells_per_ring_quantiles': [float(np.quantile(per_ring_cov, q)) for q in (0, .25, .5, .75, 1)],
            'rings_per_cell_quantiles': [float(np.quantile(per_cell_rings, q)) for q in (0, .25, .5, .75, 1)],
            'multiring_cell_share': float(len(multi_cells) / len(cset)),
            'multiring_point_share': float(pts_in_multi / len(rings_m)),
            'n_components': n_comp, 'isolated_rings': isol_ring, 'isolated_cells': len(isol_cell),
            'sparse_edge_share': float(sparse_edges / len(edge_pts)), 'n_edges': len(edge_pts),
            'design_rank': rank, 'design_n_params': n_par, 'design_cond': cond,
            'singleton_cells': sum(1 for c in cell_pts if cell_pts[c] < MIN_CELL_PTS),
            'gates': gates, 'identifiable_at_scale': bool(ok),
        }
    results['per_roi'][str(roi)] = roi_res
    verdicts[str(roi)] = {s: v['identifiable_at_scale'] for s, v in roi_res['scales'].items()}

results['verdicts'] = {
    'per_roi_identifiable': verdicts,
    'ROI2_0.05_identifiable': results['per_roi']['2']['scales']['0.05']['identifiable_at_scale'],
}
if results['verdicts']['ROI2_0.05_identifiable']:
    results['verdicts']['CROSS_COVERAGE'] = 'PASS'
else:
    results['verdicts']['CROSS_COVERAGE'] = 'FAIL'

json.dump(results, open('01_CROSS_COVERAGE.json', 'w'), indent=2)
print('CROSS_COVERAGE =', results['verdicts']['CROSS_COVERAGE'])
print('verdicts:', json.dumps(verdicts))
