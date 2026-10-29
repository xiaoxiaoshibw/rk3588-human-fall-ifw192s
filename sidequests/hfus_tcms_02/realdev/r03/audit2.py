"""Audit domains v2: thin 3D slabs. Probe v1 showed full-height boxes mix walls/furniture."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, ROOT, load, sha, write, write_png, validity

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HIST = ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json'
HIST_SHA = '01662ac7df061b42353c465ad74ab5a0d1d8452ede014c09d4a3b310f26b447a'
H = 0.15
PATCHES = [
    ('FIT_A', 'fit', .40, 1.15, -.90, .00),
    ('FIT_B', 'fit', 1.25, 2.00, -.90, .00),
    ('FIT_C', 'fit', .40, 1.15, .10, 1.00),
    ('FIT_D', 'fit', 1.25, 2.00, .10, 1.00),
    ('VAL_E', 'val', .40, 1.15, 1.10, 1.95),
    ('VAL_F', 'val', 1.25, 2.00, 1.10, 1.95),
    ('VAL_G', 'val', 2.10, 2.55, -.90, 1.00),
]


def membership(p, R, t, rect, h=H):
    u0, u1, v0, v1 = rect
    ok = validity(p)[1]
    loc = p @ R.T + t
    m = ok & (loc[:, 0] >= u0) & (loc[:, 0] < u1) & (loc[:, 1] >= v0) & (loc[:, 1] < v1) & (np.abs(loc[:, 2]) <= h)
    return m, loc


if __name__ == '__main__':
    if sha(HIST) != HIST_SHA:
        raise SystemExit('historical view transform drift')
    old = load(HIST)
    R = np.asarray(old['R'], dtype=float); t = np.asarray(old['t'], dtype=float)
    src, times = load_source()
    fit = [i for i, x in enumerate(times) if x < 20.0]
    val = [i for i, x in enumerate(times) if 20.0 <= x < 28.0]
    pre = [i for i, x in enumerate(times) if 28.0 <= x < 30.0]
    frames_for = dict(fit=fit, val=val)
    stored, counts, spreads = {}, {}, {}
    for name, role, u0, u1, v0, v1 in PATCHES:
        rows_all, fi_all, uv, per_frame = [], [], [], {}
        for fi in frames_for[role]:
            f = src.frame(fi)
            m, loc = membership(f['xyz'], R, t, (u0, u1, v0, v1))
            row = np.flatnonzero(m)
            rows_all.append((row.astype('i8') + f['offset']))
            fi_all.append(np.full(len(row), fi, dtype='i4'))
            uv.append(loc[m, :2])
            per_frame[str(fi)] = int(len(row))
        stored[name] = (np.concatenate(rows_all), np.concatenate(fi_all))
        counts[name] = per_frame
        q = np.concatenate(uv)
        spreads[name] = dict(u=float(np.percentile(q[:, 0], 95) - np.percentile(q[:, 0], 5)),
                             v=float(np.percentile(q[:, 1], 95) - np.percentile(q[:, 1], 5)))
        print(name, 'rows', len(stored[name][0]), 'min', min(per_frame.values()),
              'median', int(np.median(list(per_frame.values()))))

    audit_rows = {}
    for name, role, u0, u1, v0, v1 in PATCHES:
        if role != 'val':
            continue
        rows_all, fi_all = [], []
        for fi in pre:
            f = src.frame(fi)
            m, _ = membership(f['xyz'], R, t, (u0, u1, v0, v1))
            row = np.flatnonzero(m)
            rows_all.append(row.astype('i8') + f['offset'])
            fi_all.append(np.full(len(row), fi, dtype='i4'))
        audit_rows[name] = (np.concatenate(rows_all), np.concatenate(fi_all))

    d = OUT / 'audit'
    payload = {}
    for name, role, u0, u1, v0, v1 in PATCHES:
        rows, fi = stored[name]
        payload[name + '_rows'] = rows
        payload[name + '_fi'] = fi
        payload[name + '_rect'] = np.asarray([u0, u1, v0, v1, -H, H])
    for name, (rows, fi) in audit_rows.items():
        payload[name + '_audit_rows'] = rows
        payload[name + '_audit_fi'] = fi
    with (d / 'domains_v2.npz').open('xb') as f:
        np.savez_compressed(f, **payload)
    domain_sha = sha(d / 'domains_v2.npz')

    q = np.concatenate([src.frame(fi)['xyz'][::20] for fi in fit])
    ok = validity(q)[1]
    loc = q[ok] @ R.T + t
    low = loc[(loc[:, 2] > -0.06) & (loc[:, 2] < 0.12)]
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    ax.scatter(low[:, 0], low[:, 1], s=0.3, c='0.75', alpha=0.5, linewidths=0)
    for name, role, u0, u1, v0, v1 in PATCHES:
        ax.add_patch(plt.Rectangle((u0, v0), u1 - u0, v1 - v0, fill=False,
                                   ec='tab:blue' if role == 'fit' else 'tab:red', lw=1.4))
        ax.text(u0 + 0.02, v1 - 0.12, name, fontsize=8, color='tab:blue' if role == 'fit' else 'tab:red')
    ax.set_xlim(-0.2, 3.0); ax.set_ylim(-1.3, 2.4); ax.set_aspect('equal')
    ax.set_xlabel('u (m)'); ax.set_ylabel('v (m)')
    ax.set_title('audit domains v2: thin slabs |h|<=0.15 m (frozen before S2 fit)')
    write_png(d / 'audit_domains_v2.png', fig)
    plt.close(fig)

    write(d / 'AUDIT_DOMAINS_V2.json', dict(
        item='HFUS-TCMS-02-REALDEV-02-S02', version=2, supersedes=1,
        revision_reason='probe v1 (probe_r3) showed full-height u/v boxes mix furniture/wall with floor; residual statistics were not ground statistics',
        role='FIT [0,20)s / VAL [20,28)s / prefix audit [28,30)s',
        slab=dict(half_thickness_m=H, axes='u,v in historical candidate view frame; h=n.p+d_old'),
        view_frame=dict(path=str(HIST.relative_to(ROOT)), sha=HIST_SHA, use='orientation and slab definition only; proposals fit in RAW'),
        rationale='AI visual review of visible near-range floor footprint; open floor only',
        identity='NOT_CONFIRMED; GROUND_CONFIRMED empty; slabs are audit domains, not ground truth',
        selection_bias='slab definition uses the historical prior normal/offset; VAL is spatially disjoint from FIT but NOT independent of the old prior; cannot upgrade ground identity or claim independent validation',
        patches=[dict(id=n, role=r, rect_uv=[a, b, c, e], h=[-H, H], rows=int(len(stored[n][0])),
                      frames=len(counts[n]), per_frame_min=int(min(counts[n].values())),
                      per_frame_median=int(np.median(list(counts[n].values()))), spread=spreads[n])
                 for n, r, a, b, c, e in PATCHES],
        domains_sha=domain_sha, preview='audit_domains_v2.png', preview_sha=sha(d / 'audit_domains_v2.png'),
        freeze='rows frozen before any S2 v2 proposal/fit; VAL never used for fit/ranking'))
    print('domains v2', domain_sha)
