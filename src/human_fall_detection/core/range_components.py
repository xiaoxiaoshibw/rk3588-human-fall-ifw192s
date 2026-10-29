"""精确8邻域深度连通；水平runs减少Python并查集开销。"""
import numpy as np
import time

from .range_denoise import depth_continuous


def label_components(frame, foreground, min_points=15, timings=None):
    if timings is not None:
        timings['source_lift_ms'] = 0.0
    mask = np.asarray(foreground)
    if mask.shape != frame.grid.shape or mask.dtype != np.bool_ or (mask & ~frame.valid).any():
        raise ValueError('foreground must select valid grid cells')
    if isinstance(min_points, bool) or not isinstance(min_points, (int, np.integer)) or min_points < 1:
        raise ValueError('min_points must be a positive integer')
    h, w = mask.shape
    cells = np.flatnonzero(mask.ravel())
    labels = np.full(mask.shape, -1, dtype=np.int32)
    if not len(cells):
        return labels, []
    depth = frame.range_m.ravel()
    starts = np.ones(len(cells), dtype=bool)
    starts[1:] = ~((cells[1:] == cells[:-1] + 1) & (cells[1:] % w != 0)
                   & depth_continuous(depth[cells[1:]], depth[cells[:-1]]))
    runs = np.cumsum(starts, dtype=np.int32) - 1
    n = int(runs[-1]) + 1
    labels.ravel()[cells] = runs
    pairs = []
    for dc in (-1, 0, 1):
        selected = (cells // w < h - 1) & (cells % w + dc >= 0) & (cells % w + dc < w)
        a = cells[selected]
        b = a + w + dc
        other = labels.ravel()[b]
        ok = (other >= 0) & depth_continuous(depth[a], depth[b])
        pairs.append(runs[selected][ok].astype(np.int64) * n + other[ok])
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for pair in np.unique(np.concatenate(pairs)).tolist():
        a, b = root(pair // n), root(pair % n)
        if a != b:
            parent[max(a, b)] = min(a, b)
    roots = np.array([root(i) for i in range(n)], dtype=np.int32)
    _, compact = np.unique(roots[runs], return_inverse=True)
    labels.ravel()[cells] = compact
    order = np.argsort(compact, kind='stable')
    boundaries = np.r_[0, np.flatnonzero(np.diff(compact[order])) + 1, len(cells)]
    lifted = time.perf_counter() if timings is not None else None
    components = []
    for cid, (begin, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        members = cells[order[begin:end]]
        rows = np.sort(frame.source_rows.ravel()[members])
        components.append(dict(component_id=cid, cells=members, source_rows=rows,
                               points=len(rows), retained=len(rows) >= min_points,
                               min_points=min_points, semantic='unknown'))
    if timings is not None:
        timings['source_lift_ms'] = (time.perf_counter()-lifted)*1000
    return labels, components


def merge_components(frame, labels, components, ground):
    """显式地面下的保守3D碎片合并；只看两格内的实测边界，不跨大孔洞猜测。"""
    if not isinstance(ground, dict):
        raise ValueError('merge needs a ground object')
    normal = np.asarray(ground.get('normal'), dtype=float)
    offset = float(ground.get('offset_m', np.nan))
    if normal.shape != (3,) or not np.isfinite(normal).all() or not np.isfinite(offset) or np.linalg.norm(normal) < 1e-9:
        raise ValueError('merge needs an explicit finite ground plane')
    norm = np.linalg.norm(normal)
    normal, offset = normal / norm, offset / norm
    seed = np.array([0., 0., 1.]) if abs(normal[2]) < .9 else np.array([0., 1., 0.])
    u = np.cross(normal, seed)
    u /= np.linalg.norm(u)
    basis = np.column_stack((u, np.cross(normal, u)))
    n = len(components)
    if not n:
        return labels.copy(), []
    minimums = {c['min_points'] for c in components}
    if len(minimums) != 1:
        raise ValueError('component minimum point settings differ')
    minimum = minimums.pop()
    parent = list(range(n))
    members = [c['source_rows'] for c in components]
    origins = [[i] for i in range(n)]
    h, w = frame.grid.shape
    cells = np.flatnonzero(labels.ravel() >= 0)
    links = {}
    depth = frame.range_m.ravel()
    for dy, dx in [(0, 1), (0, 2)] + [(dy, dx) for dy in (1, 2) for dx in range(-2, 3)]:
        inside = ((cells // w + dy < h) & (cells % w + dx >= 0) & (cells % w + dx < w))
        a, b = cells[inside], cells[inside] + dy*w + dx
        ca, cb = labels.ravel()[a], labels.ravel()[b]
        eligible = (cb >= 0) & (ca != cb)
        a, b, ca, cb = a[eligible], b[eligible], ca[eligible], cb[eligible]
        if not len(a):
            continue
        gap = np.linalg.norm(frame.xyz[frame.source_rows.ravel()[a]].astype(float)
                             - frame.xyz[frame.source_rows.ravel()[b]], axis=1)
        limit = np.maximum(.06, 1.5*.0087*np.minimum(depth[a], depth[b]))
        for left, right, distance in zip(ca[gap <= limit], cb[gap <= limit], gap[gap <= limit]):
            pair = tuple(sorted((int(left), int(right))))
            links[pair] = min(links.get(pair, np.inf), float(distance))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for (left, right), _ in sorted(links.items(), key=lambda item: (item[1], item[0])):
        a, b = root(left), root(right)
        if a == b:
            continue
        rows = np.concatenate((members[a], members[b]))
        original = origins[a] + origins[b]
        if len(rows) > 3 * max(components[i]['points'] for i in original):
            continue
        xyz = frame.xyz[rows].astype(float)
        if (xyz @ normal + offset).max() > 2.2 or np.linalg.norm(np.ptp(xyz @ basis, axis=0)) > 1.0:
            continue
        a, b = min(a, b), max(a, b)
        parent[b], members[a], origins[a] = a, rows, original
    roots = np.array([root(i) for i in range(n)])
    unique, inverse = np.unique(roots, return_inverse=True)
    merged_labels = np.full_like(labels, -1)
    merged_labels.ravel()[cells] = inverse[labels.ravel()[cells]]
    merged = []
    for cid, group in enumerate(unique):
        rows = np.sort(members[group])
        merged.append(dict(component_id=cid, source_rows=rows, points=len(rows),
                           retained=len(rows) >= minimum, min_points=minimum, semantic='unknown',
                           merged_from=sorted(origins[group])))
    return merged_labels, merged
