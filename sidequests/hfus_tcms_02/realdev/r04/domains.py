"""S3 validation domains: FIT-only, prior-conditioned floor slabs in the new S3_LOCAL frame.

Selection never looks at [20,28) or [28,30); it never uses the S3 candidate residual.
`probe` prints the eligible cells; `freeze` writes the domain file, arrays and preview.
"""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X

H, CELL = 0.15, 0.4
PURITY_FLOOR, PURITY_TARGET = 0.85, 0.9
FIT_ROWS_MIN, SPACING = 60, 0.6
U_SEARCH, V_SEARCH, ANCHOR = (0.4, 2.0), (-0.2, 2.0), 0.1


def s2_domains():
    dom = C.load(C.S2 / 'audit/AUDIT_DOMAINS_V4.json')
    if C.sha(C.S2 / 'audit/domains_v4.npz') != C.FROZEN['s2_domains']:
        raise ValueError('S2 domain array drift')
    return dom


def hist_frame():
    hist = C.load(C.HIST)
    if C.sha(C.HIST) != C.FROZEN['hist_sha']:
        raise ValueError('historical transform drift')
    return np.asarray(hist['R'], dtype=float), np.asarray(hist['t'], dtype=float)


def slab_points(src, frames, T):
    """Per-frame rows inside |h_hist| <= H with their S3_LOCAL u,v,z and prior height."""
    R, t = hist_frame()
    out = []
    for fi in frames:
        p = src.frame(fi)['xyz']
        ok = X.valid_xyz(p)
        q = T.points(p, T.tag(fi, False), fi, source_validity=True)
        m = ok & (np.abs(p @ R[2] + t[2]) <= H)
        out.append(dict(fi=fi, u=q[m, 0], v=q[m, 1], z=q[m, 2], h=p[m] @ R[2] + t[2], row=np.flatnonzero(m)))
    return out


def cell_mask(d, a, b):
    return (d['u'] >= a) & (d['u'] < a + CELL) & (d['v'] >= b) & (d['v'] < b + CELL)


def exact_cell(per, a, b):
    rows = inl = 0
    counts, uu, vv = [], [], []
    for d in per:
        m = cell_mask(d, a, b)
        c = int(m.sum())
        counts.append(c)
        rows += c
        inl += int(np.sum(np.abs(d['h'][m] + 0.03) <= 0.03))
        if c:
            uu.append(d['u'][m]); vv.append(d['v'][m])
    if not rows:
        return None
    uu, vv = np.concatenate(uu), np.concatenate(vv)
    return dict(u=a, v=b, rows=rows, purity=inl / rows, per_frame=counts, fit_min=int(min(counts)),
                fit_median=int(np.median(counts)),
                spread=dict(u=float(np.percentile(uu, 95) - np.percentile(uu, 5)),
                            v=float(np.percentile(vv, 95) - np.percentile(vv, 5))))


def s2_samples_local(T):
    """Dense interior samples of every S2 rectangle, mapped historical -> S3_LOCAL."""
    dom = s2_domains()
    R, t = hist_frame()
    pts = []
    for patch in dom['patches']:
        u0, u1, v0, v1 = patch['rect_uv']
        uu = np.arange(u0, u1 + 1e-9, 0.02)
        vv = np.arange(v0, v1 + 1e-9, 0.02)
        gu, gv = np.meshgrid(uu, vv, indexing='ij')
        gu, gv = gu.ravel(), gv.ravel()
        for du in (0.0, 0.02):
            for dv in (0.0, 0.02):
                q = np.column_stack([gu + du, gv + dv, np.zeros(gu.size)])
                pts.append(T.points((q - t) @ R, T.tag(0, False), 0)[:, :2])
    return np.concatenate(pts)


def rect_gap(a, b, samples):
    """Signed clearance between the new rectangle and the S2 footprint samples."""
    inside = ((samples[:, 0] >= a) & (samples[:, 0] < a + CELL)
              & (samples[:, 1] >= b) & (samples[:, 1] < b + CELL))
    if inside.any():
        return -1.0
    dx = np.maximum(np.maximum(a - samples[:, 0], samples[:, 0] - (a + CELL)), 0)
    dy = np.maximum(np.maximum(b - samples[:, 1], samples[:, 1] - (b + CELL)), 0)
    return float(np.hypot(dx, dy).min())


def candidates(src, fit, T, samples):
    per = slab_points(src, fit, T)
    out = []
    for a in np.arange(U_SEARCH[0], U_SEARCH[1] + 1e-9, ANCHOR):
        for b in np.arange(V_SEARCH[0], V_SEARCH[1] + 1e-9, ANCHOR):
            gap = rect_gap(a, b, samples)
            if gap < 0:
                continue
            c = exact_cell(per, round(a, 3), round(b, 3))
            if c is None or c['fit_min'] < FIT_ROWS_MIN or c['purity'] < PURITY_FLOOR:
                continue
            c['s2_gap_m'] = gap
            out.append(c)
    out.sort(key=lambda c: (-c['purity'], -c['fit_min'], c['u'], c['v']))
    return out, per


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    protocol = C.load(C.OUT / 'PROTOCOL_V2.json')
    T = X.Transform(C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json'))
    src, times = C.load_source()
    fit, val, pre = C.roles(times)
    try:
        samples = s2_samples_local(T)
        cells, per = candidates(src, fit, T, samples)
        if step == 'probe':
            print('eligible cells', len(cells), 's2 samples', len(samples))
            for c in cells[:25]:
                print('u=%.1f v=%.1f purity=%.4f fitmin=%4d gap=%.3f spread=%.3f/%.3f'
                      % (c['u'], c['v'], c['purity'], c['fit_min'], c['s2_gap_m'], c['spread']['u'], c['spread']['v']))
            raise SystemExit(0)
        chosen = []
        for c in cells:
            center = np.array([c['u'] + CELL / 2, c['v'] + CELL / 2])
            if all(np.linalg.norm(center - np.array([o['u'] + CELL / 2, o['v'] + CELL / 2])) >= SPACING
                   for o in chosen):
                chosen.append(c)
            if len(chosen) == 3:
                break
        if len(chosen) < 3:
            raise SystemExit('fewer than 3 eligible cells after spacing: %d' % len(chosen))
        names = ['S3V_H', 'S3V_I', 'S3V_J']
        stored, meta, axis_data = {}, [], {}
        for name, c in zip(names, chosen):
            for role, frames in (('val', val), ('prefix', pre)):
                rows, fis, local, pts = [], [], [], []
                for fi in frames:
                    p = src.frame(fi)['xyz']
                    q = T.points(p, T.tag(fi, False), fi, source_validity=True)
                    ok = X.valid_xyz(q)
                    m = (ok & (q[:, 0] >= c['u']) & (q[:, 0] < c['u'] + CELL)
                         & (q[:, 1] >= c['v']) & (q[:, 1] < c['v'] + CELL) & (np.abs(q[:, 2]) <= H))
                    row = np.flatnonzero(m)
                    offset = int(src.frames[fi]['offset_points'])
                    rows.append((row + offset).astype('i8'))
                    local.append(row.astype('i8'))
                    fis.append(np.full(len(row), fi, dtype='i4'))
                    pts.append(q[m])
                rows, local = np.concatenate(rows), np.concatenate(local)
                fis, pts = np.concatenate(fis), np.concatenate(pts)
                stored['%s_%s_rows' % (name, role)] = rows
                stored['%s_%s_local_rows' % (name, role)] = local
                stored['%s_%s_fi' % (name, role)] = fis
                counts = [int((fis == fi).sum()) for fi in frames]
                axis_data['%s_%s_counts' % (name, role)] = np.asarray(counts, dtype='i4')
                axis_data['%s_%s_frames' % (name, role)] = np.asarray(frames, dtype='i4')
                if role == 'val':
                    meta.append(dict(id=name, role='val_validation',
                                     rect_uv=[c['u'], c['u'] + CELL, c['v'], c['v'] + CELL], h=[-H, H],
                                     rows=int(len(rows)), frames=len(frames),
                                     per_frame_min=int(min(counts)), per_frame_median=int(np.median(counts)),
                                     per_frame_max=int(max(counts)), purity=c['purity'],
                                     purity_target_met=bool(c['purity'] >= PURITY_TARGET),
                                     fit_min_rows=c['fit_min'], fit_median_rows=c['fit_median'],
                                     s2_gap_m=c['s2_gap_m'], spread=c['spread'],
                                     center_uv=[c['u'] + CELL / 2, c['v'] + CELL / 2],
                                     source_rows_sha=C.digest(sorted(int(x) for x in rows))))
                else:
                    meta[-1].update(prefix_rows=int(len(rows)), prefix_frames=len(frames),
                                    prefix_per_frame_min=int(min(counts)))
            stored['%s_rect' % name] = np.asarray([c['u'], c['u'] + CELL, c['v'], c['v'] + CELL, -H, H])
        s2npz = np.load(C.S2 / 'audit/domains_v4.npz')
        s2_sets = {k: set(s2npz[k].tolist()) for k in s2npz.files if 'rows' in k}
        overlap = {}
        for name in names:
            for role in ('val', 'prefix'):
                key = '%s_%s_rows' % (name, role)
                mine = set(stored[key].tolist())
                overlap[key] = {k: len(mine & v) for k, v in s2_sets.items() if mine & v}
        if any(overlap.values()):
            raise SystemExit('row overlap with S2 patches: ' + str(overlap))
        npz_path = C.OUT / 'DOMAINS/domains_s3.npz'
        if npz_path.exists():
            old = np.load(npz_path)
            for key, value in stored.items():
                if not np.array_equal(old[key], value):
                    raise SystemExit('existing frozen domain array differs from recomputation: ' + key)
            dom_sha = C.sha(npz_path)
        else:
            C.save_array(npz_path, **stored, **axis_data)
            dom_sha = C.sha(npz_path)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        R, t = hist_frame()
        fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
        allu = np.concatenate([d['u'] for d in per])
        allv = np.concatenate([d['v'] for d in per])
        allh = np.concatenate([d['h'] for d in per])
        pick = slice(None, None, 11)
        sc = ax.scatter(allu[pick], allv[pick], s=0.5, c=np.abs(allh[pick] + 0.03), cmap='viridis_r',
                        vmin=0, vmax=0.15, alpha=0.8, linewidths=0)
        fig.colorbar(sc, ax=ax, label='|h_hist + 3 cm| (m)')
        for patch in s2_domains()['patches']:
            u0, u1, v0, v1 = patch['rect_uv']
            q = np.column_stack([np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]]),
                                 np.zeros(4)])
            q = (q - t) @ R
            q = T.points(q, T.tag(0, False), 0)
            ax.add_patch(plt.Polygon(q[:, :2], closed=True, fill=False, ec='tab:blue', lw=1.0))
            ax.text(q[0, 0] + 0.02, q[0, 1] - 0.07, patch['id'], fontsize=7, color='tab:blue')
        for name, c in zip(names, chosen):
            ax.add_patch(plt.Rectangle((c['u'], c['v']), CELL, CELL, fill=False, ec='red', lw=1.8))
            ax.text(c['u'] + 0.02, c['v'] + CELL - 0.08, '%s %.3f' % (name, c['purity']),
                    fontsize=9, color='red')
        ax.set_xlim(0.3, 2.5)
        ax.set_ylim(-0.3, 2.1)
        ax.set_aspect('equal')
        ax.set_xlabel('u (m, S3_LOCAL)')
        ax.set_ylabel('v (m, S3_LOCAL)')
        ax.set_title('FIT prior-conditioned floor slabs: S2 patches (blue) and new S3 domains (red)')
        C.write_png(C.OUT / 'DOMAINS/s3_domains.png', fig)
        plt.close(fig)
        C.write(C.OUT / 'DOMAINS/S3_DOMAINS.json', dict(
            item=C.ITEM, version=1, role='S3 new spatial domains; [20,28) validation and [28,30) prefix audit',
            transform_id=T.id, coordinate_version=T.version, protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'),
            cell_m=[CELL, CELL], slab_half_thickness_m=H,
            slab_axes='S3_LOCAL u,v; membership |z_local| <= 0.15',
            selection_data='FIT [0,20) valid rows only; no [20,28)/[28,30) row used to choose or move a patch',
            selection_bias='prior-conditioned selection (the historical TLS plane defines the purity metric); '
                           'not independent ground truth; the S3 candidate residual never screened points',
            purity_metric='exact fraction with |h_hist+0.03|<=0.03 among rows with |h_hist|<=0.15 in the cell',
            search=dict(u=list(U_SEARCH), v=list(V_SEARCH), anchor_m=ANCHOR, eligible_cells=len(cells)),
            rule=protocol['domains']['selection_rule'],
            thresholds=dict(purity_floor=PURITY_FLOOR, purity_target=PURITY_TARGET,
                            fit_rows_per_cell_min=FIT_ROWS_MIN, pairwise_center_min_m=SPACING, s2_clearance_m=0.0),
            patches=meta, domains_sha=dom_sha, preview='s3_domains.png',
            preview_sha=C.sha(C.OUT / 'DOMAINS/s3_domains.png'),
            s2_row_overlap=overlap,
            eligible_top=[dict(u=c['u'], v=c['v'], purity=round(c['purity'], 4), fit_min=c['fit_min'],
                               gap=round(c['s2_gap_m'], 4)) for c in cells[:20]],
            freeze='written and hashed before the M0 rebuild and before the 780-frame application-chain run',
            note='S2 occupies the whole >0.9 purity core; three non-overlapping cells exist and the third is '
                 'just below the 0.9 target, disclosed here and never used to move a gate'))
        print(json.dumps(dict(domains_sha=dom_sha,
                              patches=[(m['id'], m['rect_uv'], m['rows'], m['per_frame_min'],
                                        round(m['purity'], 4), m['s2_gap_m']) for m in meta]), ensure_ascii=False))
    finally:
        src.close()
