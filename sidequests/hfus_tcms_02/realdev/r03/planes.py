"""FIT-only multi-plane proposals (C: 3D voxel moments, D: range-image bins) and patch gates."""
import numpy as np
from s2core import validity


def tls(points, weights=None):
    p = np.asarray(points, dtype=np.float64)
    if len(p) < 3:
        raise ValueError('TLS needs 3 points')
    if weights is None:
        w = np.full(len(p), 1.0 / len(p))
    else:
        w = np.asarray(weights, dtype=np.float64)
        w = w / w.sum()
    m = w @ p
    q = p - m
    cov = (q * w[:, None]).T @ q
    val, vec = np.linalg.eigh(cov)
    n = vec[:, 0]
    if n[2] < 0:
        n = -n
    d = float(-n @ m)
    res = p @ n + d
    return dict(n=n.tolist(), d=d, rms_m=float(np.sqrt(np.mean(res ** 2))),
                p95_abs_m=float(np.percentile(np.abs(res), 95)),
                median_signed_m=float(np.median(res)), count=int(len(p)),
                eigenvalues=np.sort(val)[::-1].tolist())


def voxel_cloud(source, frames, voxel=0.25, min_count=8):
    keys, rows = [], []
    for fi in frames:
        f = source.frame(fi)
        p = f['xyz']
        ok = validity(p)[1]
        pv = p[ok]
        if not len(pv):
            continue
        c = np.floor(pv / voxel).astype(np.int64)
        keys.append(((c[:, 0] + 512) << 22) | ((c[:, 1] + 512) << 11) | (c[:, 2] + 512))
        rows.append(pv)
    k = np.concatenate(keys)
    p = np.concatenate(rows)
    del keys, rows
    uk, inv = np.unique(k, return_inverse=True)
    del k
    n = len(uk)
    cnt = np.bincount(inv, minlength=n).astype(np.float64)
    s = [np.bincount(inv, weights=p[:, a], minlength=n) for a in range(3)]
    m = np.stack([s[a] / cnt for a in range(3)], axis=1)
    del s
    cov = np.empty((n, 3, 3))
    for a in range(3):
        for b in range(a, 3):
            v = np.bincount(inv, weights=p[:, a] * p[:, b], minlength=n) / cnt - m[:, a] * m[:, b]
            cov[:, a, b] = v
            cov[:, b, a] = v
    del p, inv
    val, vec = np.linalg.eigh(cov)
    planarity = (val[:, 1] - val[:, 0]) / np.maximum(val[:, 2], 1e-12)
    keep = (cnt >= min_count) & np.isfinite(m).all(axis=1)
    return dict(centers=m[keep], counts=cnt[keep], planarity=planarity[keep],
                voxel=voxel, total_voxels=int(n))


def image_cloud(image):
    occ = image['count'] > 0
    idx = np.flatnonzero(occ)
    ia = idx % image['naz']
    ie = idx // image['naz']
    az = -np.pi + (ia + 0.5) * (2 * np.pi / image['naz'])
    el = -np.pi / 2 + (ie + 0.5) * (np.pi / image['nel'])
    r = image['nearest'][idx].astype(np.float64)
    p = np.stack([r * np.cos(el) * np.cos(az), r * np.cos(el) * np.sin(az), r * np.sin(el)], axis=1)
    return p, image['count'][idx].astype(np.float64), idx


def _plane_from(points):
    a, b, c = points
    n = np.cross(b - a, c - a)
    norm = np.linalg.norm(n)
    if norm < 1e-9:
        return None
    n = n / norm
    return n, float(-n @ a)


def ransac(cloud, weights, seed, iterations, inlier_m, max_planes, min_weight):
    rng = np.random.default_rng(seed)
    cloud = np.asarray(cloud, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64).copy()
    out = []
    for _ in range(max_planes):
        live = w > 0
        if live.sum() < 3:
            break
        idx = np.flatnonzero(live)
        best = None
        for _ in range(iterations):
            pick = rng.choice(idx, 3, replace=False)
            pl = _plane_from(cloud[pick])
            if pl is None:
                continue
            n, d = pl
            inl = np.abs(cloud @ n + d) <= inlier_m
            score = w[inl].sum()
            if best is None or score > best[0]:
                best = (score, n, d, inl)
        if best is None or best[0] < min_weight:
            break
        n, d, inl = best[1], best[2], best[3]
        fit = tls(cloud[inl], w[inl])
        out.append(dict(n=fit['n'], d=fit['d'], weight=float(w[inl].sum()),
                        support=int(inl.sum()), rms_m=fit['rms_m'],
                        p95_abs_m=fit['p95_abs_m']))
        w[inl] = 0.0
    return out


def refine_on_rows(source, frames, plane, inlier_m=0.03, cap=2_000_000):
    n = np.asarray(plane['n']); d = float(plane['d'])
    parts = []
    collected = 0
    total = 0
    for fi in frames:
        p = source.frame(fi)['xyz']
        ok = validity(p)[1]
        pv = p[ok]
        m = np.abs(pv @ n + d) <= inlier_m
        total += int(m.sum())
        if collected < cap:
            q = pv[m]
            q = q[:cap - collected]
            parts.append(q)
            collected += len(q)
    pts = np.concatenate(parts) if parts else np.empty((0, 3))
    if len(pts) < 20:
        return None
    fit = tls(pts)
    fit['inlier_rows_total'] = total
    fit['refit_points'] = int(len(pts))
    fit['capped'] = total > len(pts)
    return fit


def patch_residuals(plane, source, patch_rows, frames):
    """One frame load per frame; residuals for every patch of that role."""
    n = np.asarray(plane['n']); d = float(plane['d'])
    vals = {name: [] for name in patch_rows}
    per = {name: {} for name in patch_rows}
    for fi in frames:
        p = source.frame(fi)['xyz']
        for name, table in patch_rows.items():
            rows = table.get(fi)
            if rows is None or not len(rows):
                per[name][fi] = dict(count=0)
                continue
            r = p[rows] @ n + d
            vals[name].append(r)
            per[name][fi] = dict(count=int(len(r)),
                                 rms_m=float(np.sqrt(np.mean(r ** 2))),
                                 p95_abs_m=float(np.percentile(np.abs(r), 95)),
                                 support_rate=float(np.mean(np.abs(r) <= 0.05)))
    out = {}
    for name in patch_rows:
        r = np.concatenate(vals[name]) if vals[name] else np.empty(0)
        out[name] = dict(count=int(len(r)),
                         rms_m=float(np.sqrt(np.mean(r ** 2))) if len(r) else None,
                         p95_abs_m=float(np.percentile(np.abs(r), 95)) if len(r) else None,
                         support_rate=float(np.mean(np.abs(r) <= 0.05)) if len(r) else None,
                         median_signed_m=float(np.median(r)) if len(r) else None,
                         per_frame=per[name])
    return out


def gates(stats, role, min_points=20, rms=0.03, p95=0.05, support=0.80):
    rows = []
    for name, s in stats.items():
        if not name.startswith(role):
            continue
        ok = (s['count'] >= min_points and s['rms_m'] is not None and s['rms_m'] <= rms
              and s['p95_abs_m'] is not None and s['p95_abs_m'] <= p95
              and s['support_rate'] is not None and s['support_rate'] >= support)
        rows.append(dict(patch=name, PASS=bool(ok), **{k: s[k] for k in ('count', 'rms_m', 'p95_abs_m', 'support_rate', 'median_signed_m')}))
    return rows
