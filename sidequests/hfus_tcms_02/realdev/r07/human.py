"""Map a thinned skeleton graph onto the human topology and measure the observable segments.

Ordering: the two highest-degree junctions are the shoulder and hip junctions; the shortest branch
at the shoulder junction is the head, the other two are arms; the two branches at the hip junction
away from the trunk are legs. Each limb branch is split at its sharpest corner into proximal/distal.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skel as S


def _adj(edges):
    adj = {}
    for k, e in enumerate(edges):
        for p in (e[0], e[-1]):
            adj.setdefault(p, []).append(k)
    return adj


def _endpoints(adj):
    return [p for p, es in adj.items() if len(es) == 1]


def _walk(adj, edges, start_edge, start_point):
    """Follow edges from a node away from start_point; returns the path."""
    path = [start_point]
    cur_edge, cur_pt = start_edge, start_point
    seen = set()
    while True:
        e = edges[cur_edge]
        pts = e if e[0] == cur_pt else list(reversed(e))
        path += pts[1:]
        end = pts[-1]
        seen.add(cur_edge)
        nxt = [k for k in adj.get(end, []) if k != cur_edge and k not in seen]
        if not nxt:
            return path, end
        cur_edge, cur_pt = nxt[0], end


def _corner(path, cell):
    """Sharpest turning point of a branch; returns the split index."""
    if len(path) < 12:
        return None
    p = np.asarray(path, dtype=float) * cell
    n = len(p)
    k = max(4, int(0.12 * n))
    best, idx = -1.0, None
    for i in range(k, n - k):
        a = p[i] - p[i - k]
        b = p[min(n - 1, i + k)] - p[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-6 or nb < 1e-6:
            continue
        turn = float(np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1))))
        if turn > best:
            best, idx = turn, i
    if idx is None or best < 12.0:
        return None
    return idx, best


def measure_human(uv, cell=S.CELL):
    res, info = S.measure(uv)
    if not res:
        return {}, info
    edges, nodes = res['edges'], res['nodes']
    adj = _adj(edges)
    ends = _endpoints(adj)
    if len(ends) < 4:
        return {}, dict(info, reason='FEWER_THAN_4_ENDPOINTS', endpoints=len(ends))
    # junction nodes (degree >= 3) ordered by graph degree
    order = sorted(adj, key=lambda p: -len(adj[p]))
    junctions = [p for p in order if len(adj[p]) >= 3]
    if len(junctions) < 2:
        return {}, dict(info, reason='FEWER_THAN_2_JUNCTIONS', junctions=len(junctions))
    def dist(a, b):
        return float(np.linalg.norm((np.asarray(a, float) - np.asarray(b, float)) * cell))
    J1 = junctions[0]
    J2 = next((p for p in junctions[1:] if dist(p, J1) > 0.25), None)
    if J2 is None:
        return {}, dict(info, reason='JUNCTIONS_TOO_CLOSE')
    # branches at J1 (excluding the edge that leads to J2)
    def branches(j):
        out = []
        for k in adj[j]:
            e = edges[k]
            other_end = e[-1] if e[0] == j else e[0]
            path, end = _walk(adj, edges, k, j)
            out.append(dict(edge=k, path=path, end=end, length=S.path_len(path, cell),
                            radius=S.radius_at(res['edt'], path, cell)))
        return out
    b1 = branches(J1)
    b2 = branches(J2)
    # the trunk edge is the one shared by the two junctions (shortest branch at J1 that reaches J2)
    trunk_edge = None
    for b in b1:
        if b['end'] == J2 or J2 in (edges[b['edge']][0], edges[b['edge']][-1]):
            trunk_edge = b
            break
    if trunk_edge is None:
        return {}, dict(info, reason='NO_JUNCTION_EDGE')
    head_candidates = [b for b in b1 if b is not trunk_edge]
    if len(head_candidates) < 3:
        return {}, dict(info, reason='JUNCTION_BRANCHES_INSUFFICIENT', n=len(head_candidates))
    head = min(head_candidates, key=lambda b: b['length'])
    arms = [b for b in head_candidates if b is not head]
    legs = [b for b in b2 if b is not trunk_edge and b['length'] > 0.15]
    if len(legs) < 2 or len(arms) < 2:
        return {}, dict(info, reason='LIMB_COUNT', arms=len(arms), legs=len(legs))
    out = {}
    # trunk = head end -> hip junction (pelvis)
    trunk_len = trunk_edge['length'] + head['length']
    out['TRUNK'] = float(max(trunk_len - 2 * float(np.median([head['radius'], trunk_edge['radius']])), 0.05))
    arms.sort(key=lambda b: -b['length'])
    legs.sort(key=lambda b: -b['length'])
    for side, b in zip(('L', 'R'), arms):
        r = b['radius']
        c = _corner(b['path'], cell)
        if c is None:
            half = b['length'] / 2.0
            out['UPPER_ARM_' + side] = float(max(half - r, 0.03))
            out['FOREARM_' + side] = float(max(b['length'] - half - r, 0.03))
        else:
            idx, turn = c
            first = S.path_len(b['path'][:idx + 1], cell)
            second = b['length'] - first
            out['UPPER_ARM_' + side] = float(max(first - r, 0.03))
            out['FOREARM_' + side] = float(max(second - r, 0.03))
    for side, b in zip(('L', 'R'), legs):
        r = b['radius']
        c = _corner(b['path'], cell)
        if c is None:
            half = b['length'] / 2.0
            out['THIGH_' + side] = float(max(half - r, 0.03))
            out['SHIN_' + side] = float(max(b['length'] - half - r, 0.03))
        else:
            idx, turn = c
            first = S.path_len(b['path'][:idx + 1], cell)
            second = b['length'] - first
            out['THIGH_' + side] = float(max(first - r, 0.03))
            out['SHIN_' + side] = float(max(second - r, 0.03))
    # widths: distance between the two arm attachment points and the two hip attachment points
    info = dict(info, junctions=2, arms=[round(b['length'], 3) for b in arms],
                legs=[round(b['length'], 3) for b in legs], trunk_edge=round(trunk_edge['length'], 3),
                head=round(head['length'], 3))
    return out, info
