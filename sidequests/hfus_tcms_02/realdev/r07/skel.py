"""Skeletonisation measurement: occupancy grid -> thinned medial skeleton -> human topology.

The measurement is geometric only: a 5 cm occupancy grid, Zhang-Suen thinning, graph tracing,
junction classification and geodesic lengths corrected by the distance-transform radius. Nothing
here reads a label or a true length.
"""
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

CELL = 0.03
DILATE = 1          # one dilation fills 1-cell sampling holes before thinning; radius is corrected below
RIDGE = False       # False: Zhang-Suen thinning; True: distance-transform ridge (kept for comparison)
MIN_BRANCH_M = 0.10


def rasterize(uv, cell=CELL):
    lo = uv.min(axis=0) - 2 * cell
    ij = np.floor((uv - lo) / cell).astype(int)
    w = ij.max(axis=0) + 3
    g = np.zeros((w[0] + 1, w[1] + 1), dtype=bool)
    g[ij[:, 0], ij[:, 1]] = True
    return g, lo, cell


def _nbrs(g, i, j):
    return [g[i - 1, j], g[i - 1, j + 1], g[i, j + 1], g[i + 1, j + 1],
            g[i + 1, j], g[i + 1, j - 1], g[i, j - 1], g[i - 1, j - 1]]


def thin(g):
    """Zhang-Suen thinning."""
    img = g.copy()
    changed = True
    h, w = img.shape
    while changed:
        changed = False
        for step in (0, 1):
            kill = []
            for i in range(1, h - 1):
                row = img[i]
                for j in range(1, w - 1):
                    if not row[j]:
                        continue
                    P = _nbrs(img, i, j)
                    B = sum(P)
                    if B < 2 or B > 6:
                        continue
                    seq = P + [P[0]]
                    A = sum(1 for k in range(8) if not seq[k] and seq[k + 1])
                    if A != 1:
                        continue
                    if step == 0:
                        if P[0] and P[2] and P[4]:
                            continue
                        if P[2] and P[4] and P[6]:
                            continue
                    else:
                        if P[0] and P[2] and P[6]:
                            continue
                        if P[0] and P[4] and P[6]:
                            continue
                    kill.append((i, j))
            for i, j in kill:
                img[i, j] = False
            if kill:
                changed = True
    return img


def trace(skel):
    """Walk the 8-neighbour skeleton graph; returns nodes, edges (paths of pixels)."""
    pts = {(int(i), int(j)) for i, j in zip(*np.nonzero(skel))}
    def deg(p):
        i, j = p
        return sum(1 for di in (-1, 0, 1) for dj in (-1, 0, 1)
                   if (di or dj) and (i + di, j + dj) in pts)
    nodes = {p for p in pts if deg(p) != 2}
    used, edges = set(), []
    for p in sorted(nodes):
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not (di or dj):
                    continue
                q = (p[0] + di, p[1] + dj)
                if q not in pts:
                    continue
                key = (p, q)
                if key in used:
                    continue
                path = [p, q]
                used.add(key)
                used.add((q, p))
                prev, cur = p, q
                while cur not in nodes:
                    nxt = [r for r in ((cur[0] + a, cur[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1)
                                       if (a or b)) if r in pts and r != prev]
                    if not nxt:
                        break
                    nxt = nxt[0]
                    used.add((cur, nxt))
                    used.add((nxt, cur))
                    path.append(nxt)
                    prev, cur = cur, nxt
                edges.append(path)
    # isolated loops with no node
    covered = set()
    for e in edges:
        covered.update(e)
    rest = {p for p in pts if p not in covered}
    while rest:
        start = next(iter(rest))
        path, prev, cur = [start], None, start
        while True:
            rest.discard(cur)
            nxt = [r for r in ((cur[0] + a, cur[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1)
                               if (a or b)) if r in pts and r != prev and r in rest]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        edges.append(path)
    edges = [e for e in edges if len(e) >= 2]
    return pts, nodes, edges


def path_len(path, cell):
    p = np.asarray(path, dtype=float) * cell
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))) if len(p) > 1 else 0.0


def radius_at(edt, path, cell):
    r = [edt[i, j] for i, j in path]
    return float(np.median(r)) * cell if r else 0.0


def prune(edges, min_len, cell):
    """Iteratively drop short spurs (an endpoint of degree 1); keeps the real tree."""
    while True:
        deg = {}
        for e in edges:
            for p in (e[0], e[-1]):
                deg[p] = deg.get(p, 0) + 1
        keep, removed = [], 0
        for e in edges:
            if path_len(e, cell) < min_len and (deg.get(e[0], 0) == 1 or deg.get(e[-1], 0) == 1):
                removed += 1
                continue
            keep.append(e)
        if not removed:
            return keep
        edges = keep


def medial_mask(g, edt, size=3):
    """Medial-axis ridge: local maxima of the distance transform inside the shape.

    Pixel thinning of a dilated sparse raster leaves comb/lattice artefacts, so the ridge is taken
    directly from the distance transform instead.
    """
    mx = ndimage.maximum_filter(edt, size=size)
    return g & (edt >= mx - 1e-9) & (edt > 0)


def measure(uv, min_len=MIN_BRANCH_M):
    """Returns segment measurements, topology and diagnostics; empty dict when not human-shaped."""
    if len(uv) < 120:
        return {}, dict(reason='TOO_FEW_POINTS', n=len(uv))
    g, origin, cell = rasterize(uv)
    if DILATE:
        g = ndimage.binary_dilation(g, iterations=DILATE)
    edt = ndimage.distance_transform_edt(np.pad(g, 1, constant_values=False))[1:-1, 1:-1]
    edt = np.maximum(edt - DILATE, 0.0)
    sk = medial_mask(g, edt) if RIDGE else thin(g)
    pts, nodes, edges = trace(sk)
    if not edges:
        return {}, dict(reason='NO_SKELETON', n=len(uv))
    edges = prune(edges, min_len, cell)
    if not edges:
        return {}, dict(reason='EMPTY_AFTER_PRUNE', n=len(uv))
    r = [radius_at(edt, e, cell) for e in edges]
    lens = [path_len(e, cell) for e in edges]
    info = dict(n=len(uv), grid=g.shape, edges=len(edges), cell=cell,
                radii=[round(x, 3) for x in r], lengths=[round(x, 3) for x in lens],
                nodes=len(nodes))
    return dict(edges=edges, radius=r, length=lens, nodes=nodes, edt=edt, cell=cell,
                origin=origin, pts=pts), info
