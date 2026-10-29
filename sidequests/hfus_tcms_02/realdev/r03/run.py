"""S2 run: FIT-only distance image + C/D proposals + frozen candidates + VAL gate."""
import argparse
import json
import sys
import threading
import time
from pathlib import Path
import numpy as np
import psutil
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import ROOT, OUT, load_source, load, sha, write, validity, roles
import distance
import planes


class Rss(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak = 0
        self.stop = False

    def run(self):
        p = psutil.Process()
        while not self.stop:
            self.peak = max(self.peak, p.memory_info().rss)
            time.sleep(0.05)


def rect_mask(p, R, t, rect, h=0.15):
    u0, u1, v0, v1 = rect
    loc = p @ R.T + t
    return ((loc[:, 0] >= u0) & (loc[:, 0] < u1) & (loc[:, 1] >= v0) & (loc[:, 1] < v1)
            & (np.abs(loc[:, 2]) <= h))


def build_patches(source, dom, fit, val, pre, verify=True):
    R = np.asarray(dom['R']); t = np.asarray(dom['t'])
    out = {}
    for patch in dom['patches']:
        name, role, rect = patch['id'], patch['role'], patch['rect_uv']
        frames = fit if role == 'fit' else val
        per = {}
        for fi in frames:
            p = source.frame(fi)['xyz']
            per[fi] = np.flatnonzero(validity(p)[1] & rect_mask(p, R, t, rect)).astype(np.int32)
        if verify and int(sum(len(v) for v in per.values())) != patch['rows']:
            raise ValueError('Frozen patch row drift ' + name)
        out[name] = per
        if role == 'val':
            out[name + '_prefix'] = {}
            for fi in pre:
                p = source.frame(fi)['xyz']
                out[name + '_prefix'][fi] = np.flatnonzero(validity(p)[1] & rect_mask(p, R, t, rect)).astype(np.int32)
    return out


def frame_gate(r):
    return bool(len(r) >= 20 and np.sqrt(np.mean(r ** 2)) <= 0.03
                and np.percentile(np.abs(r), 95) <= 0.05 and np.mean(np.abs(r) <= 0.05) >= 0.80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['probe', 'full'], required=True)
    ap.add_argument('--label')
    a = ap.parse_args()
    t0 = time.time()
    rss = Rss(); rss.start()
    sample = a.mode == 'probe'
    protocol = load(OUT / 'PROTOCOL_V4.json')
    dom_meta = load(OUT / 'audit/AUDIT_DOMAINS_V4.json')
    if sha(OUT / 'audit/domains_v4.npz') != dom_meta['domains_sha']:
        raise ValueError('Audit domain drift')
    hist = load(ROOT / protocol['view_frame']['path'])
    if sha(ROOT / protocol['view_frame']['path']) != protocol['view_frame']['sha']:
        raise ValueError('View transform drift')
    dom = dict(R=np.asarray(hist['R'], dtype=float), t=np.asarray(hist['t'], dtype=float), patches=dom_meta['patches'])
    label = a.label or a.mode
    if not label.replace('_', '').isalnum():
        raise ValueError('unsafe label')
    dest = OUT / label
    dest.mkdir(exist_ok=False)
    here = Path(__file__).resolve().parent
    write(dest / 'CODE_AT_START.json', dict(argv=sys.argv, protocol_sha=sha(OUT / 'PROTOCOL_V4.json'),
        files={p.name: sha(p) for p in sorted(here.iterdir()) if p.is_file() and p.suffix in ('.py', '.js', '.html')}))
    src, times = load_source()
    fit, val, pre = roles(times)
    if sample:
        fit = fit[::4]; val = val[::4]; pre = pre[::2]
    naz, nel = (512, 256) if sample else (1024, 512)
    stored = [f for f in ([0, 100, 150, 192] if not sample else [0, 100, 192]) if f in fit]
    t1 = time.time()
    image = distance.build(src, fit, naz, nel, stored=stored)
    dstats = distance.stats(image)
    for f in ([193, 230, 270] if not sample else [193]):
        if f in val:
            im = distance.build(src, [f], naz, nel, stored=[f])
            image['per_frame'][f] = im['per_frame'][f]
    t2 = time.time()
    patches = build_patches(src, dom, fit, val, pre, verify=not sample)
    fit_p = {k: v for k, v in patches.items() if k.startswith('FIT')}
    val_p = {k: v for k, v in patches.items() if k.startswith('VAL') and not k.endswith('_prefix')}
    pre_p = {k[:-7]: v for k, v in patches.items() if k.endswith('_prefix')}
    t3 = time.time()
    vc = planes.voxel_cloud(src, fit, voxel=protocol['proposals']['c_3d']['voxel_m'],
                            min_count=protocol['proposals']['ransac']['min_voxel_support'])
    cx = planes.image_cloud(image)
    rng = np.random.default_rng(protocol['proposals']['ransac']['seed'])
    if len(cx[0]) > 120000:
        pick = rng.choice(len(cx[0]), 120000, replace=False)
        icloud, iw = cx[0][pick], cx[1][pick]
    else:
        icloud, iw = cx[0], cx[1]
    it = 120 if sample else protocol['proposals']['ransac']['iterations']
    maxp = 5 if sample else protocol['proposals']['ransac']['max_planes']
    c_planes = planes.ransac(vc['centers'], vc['counts'], protocol['proposals']['ransac']['seed'],
                             it, 0.04, maxp, 50)
    d_planes = planes.ransac(icloud, iw, protocol['proposals']['ransac']['seed'] + 1,
                             it, 0.05, maxp, 20)
    t4 = time.time()
    cap = 400000 if sample else 2000000
    refined = []
    for tag, plist in [('C3D', c_planes), ('DIMG', d_planes)]:
        for i, p in enumerate(plist):
            fitp = planes.refine_on_rows(src, fit, p, cap=cap)
            if fitp is None:
                continue
            fitp.update(id='%s_%02d' % (tag, i + 1), source=tag, proposal=p)
            refined.append(fitp)
    t5 = time.time()
    for c in refined:
        c['fit_patch'] = planes.gates(planes.patch_residuals(c, src, fit_p, fit), 'FIT')
        c['fit_pass'] = sum(x['PASS'] for x in c['fit_patch'])
        c['fit_median_support'] = float(np.median([x['support_rate'] for x in c['fit_patch']]))
        c['fit_median_rms'] = float(np.median([x['rms_m'] for x in c['fit_patch']]))
        c['rank_key'] = (-c['fit_pass'], -c['fit_median_support'], c['fit_median_rms'])
    refined.sort(key=lambda c: c['rank_key'])
    chosen = []
    for tag in ('C3D', 'DIMG'):
        best = next((c for c in refined if c['source'] == tag and c['fit_pass'] >= 2), None)
        if best:
            chosen.append(best)
    for c in refined:
        if len(chosen) >= 3:
            break
        if c not in chosen:
            chosen.append(c)
    chosen = chosen[:3]
    old_report = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/report.json')
    est = old_report['estimators']['tls']
    n_old = np.asarray(est['normal_source'], dtype=float)
    n_old = n_old / np.linalg.norm(n_old)
    old_plane = dict(n=n_old.tolist(), d=float(est['offset_source_m']), id='OLD_TLS', source='HISTORICAL_TLS')
    old_plane['fit_patch'] = planes.gates(planes.patch_residuals(old_plane, src, fit_p, fit), 'FIT')
    old_plane['fit_pass'] = sum(x['PASS'] for x in old_plane['fit_patch'])
    t6 = time.time()
    results = []
    for c in chosen + [old_plane]:
        st = planes.patch_residuals(c, src, val_p, val)
        c['val_patch'] = planes.gates(st, 'VAL')
        c['val_pass'] = sum(x['PASS'] for x in c['val_patch'])
        c['val_details'] = st
        c['status'] = ('S2_CANDIDATE_VAL_CONSISTENT' if c['fit_pass'] >= 2 and c['val_pass'] >= 2
                       else 'S2_FAIL_VAL' if c['fit_pass'] >= 2 else 'S2_FAIL_FIT')
        results.append(c)
    best = next((c for c in results if c['status'] == 'S2_CANDIDATE_VAL_CONSISTENT'), None)
    temporal = None
    if best:
        temporal = dict(id=best['id'], val={}, prefix={})
        for fi in val:
            per = {}
            p = src.frame(fi)['xyz']
            for name, table in val_p.items():
                rows = table[fi]
                if not len(rows):
                    per[name] = dict(count=0, PASS=False)
                    continue
                r = p[rows] @ np.asarray(best['n']) + best['d']
                per[name] = dict(count=int(len(r)), rms_m=float(np.sqrt(np.mean(r ** 2))),
                                 support_rate=float(np.mean(np.abs(r) <= 0.05)), PASS=frame_gate(r))
            temporal['val'][str(fi)] = per
        for fi in pre:
            per = {}
            p = src.frame(fi)['xyz']
            for name, table in pre_p.items():
                rows = table[fi]
                if not len(rows):
                    per[name] = dict(count=0, PASS=False)
                    continue
                r = p[rows] @ np.asarray(best['n']) + best['d']
                per[name] = dict(count=int(len(r)), rms_m=float(np.sqrt(np.mean(r ** 2))),
                                 support_rate=float(np.mean(np.abs(r) <= 0.05)), PASS=frame_gate(r))
            temporal['prefix'][str(fi)] = per
        temporal['val_all_pass_frames'] = int(sum(all(v['PASS'] for v in per.values()) for per in temporal['val'].values()))
        temporal['val_frames'] = len(temporal['val'])
        temporal['prefix_all_pass_frames'] = int(sum(all(v['PASS'] for v in per.values()) for per in temporal['prefix'].values()))
        temporal['prefix_frames'] = len(temporal['prefix'])
    cross = None
    cs = [c for c in results if c['source'] == 'C3D']
    ds = [c for c in results if c['source'] == 'DIMG']
    if cs and ds:
        na, nb = np.asarray(cs[0]['n']), np.asarray(ds[0]['n'])
        ang = float(np.degrees(np.arccos(np.clip(abs(na @ nb), -1, 1))))
        off = float(abs(abs(cs[0]['d']) - abs(ds[0]['d'])))
        cross = dict(normal_deg=ang, offset_m=off, conflict=bool(ang > 2.0 or off > 0.03))
    t7 = time.time()
    payload = dict(naz=image['naz'], nel=image['nel'], nearest=image['nearest'],
                   nearest_row=image['nearest_row'], count=image['count'], rmax=image['rmax'],
                   indptr=image['indptr'], rows=image['rows'])
    for k, v in image['per_frame'].items():
        payload['f%d' % k] = v
    np.savez_compressed(dest / 'DISTANCE.npz', **payload)
    write(dest / 'DISTANCE_STATS.json', dict(resolution=[naz, nel], stats=dstats,
        profile='azimuth periodic 360 deg, elevation -90..90; hole=UNKNOWN; collision=multiple observations',
        rows_accounting='every valid FIT row in CSR; per-frame stored arrays are display only'))
    write(dest / 'PROPOSALS.json', dict(
        voxel=dict(voxel_m=vc['voxel'], total_voxels=vc['total_voxels'], used=int(len(vc['centers']))),
        image=dict(occupied_bins=len(cx[0]), used_for_ransac=int(len(icloud))),
        C3D=[{k: c.get(k) for k in ('id', 'n', 'd', 'rms_m', 'p95_abs_m', 'count', 'fit_pass', 'fit_median_support', 'fit_median_rms')} | dict(fit_patch=c['fit_patch']) for c in refined if c['source'] == 'C3D'],
        DIMG=[{k: c.get(k) for k in ('id', 'n', 'd', 'rms_m', 'p95_abs_m', 'count', 'fit_pass', 'fit_median_support', 'fit_median_rms')} | dict(fit_patch=c['fit_patch']) for c in refined if c['source'] == 'DIMG'],
        note='proposals from FIT only; refined on FIT rows'))
    write(dest / 'CANDIDATES.json', [dict(id=c['id'], source=c['source'], n=c['n'], d=c['d'], rms_m=c.get('rms_m'),
        p95_abs_m=c.get('p95_abs_m'), count=c.get('count'), inlier_rows_total=c.get('inlier_rows_total'),
        refit_points=c.get('refit_points'), capped=c.get('capped'), fit_pass=c['fit_pass'],
        val_pass=c['val_pass'], status=c['status'], fit_patch=c['fit_patch'], val_patch=c['val_patch']) for c in results])
    write(dest / 'VALIDATION.json', dict(results=[dict(id=c['id'], fit_pass=c['fit_pass'], val_pass=c['val_pass'],
        status=c['status'], fit_patch=c['fit_patch'], val_patch=c['val_patch']) for c in results],
        best=best['id'] if best else None, cross_family=cross, gates=protocol['gates']))
    if temporal:
        write(dest / 'TEMPORAL.json', temporal)
    used = sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())
    rss.stop = True; rss.join()
    write(dest / 'SUMMARY.json', dict(mode=a.mode, frames_fit=len(fit), frames_val=len(val), frames_prefix=len(pre),
        distance=dstats, proposals=dict(c=len(c_planes), d=len(d_planes), refined=len(refined)),
        candidates=[dict(id=c['id'], fit_pass=c['fit_pass'], val_pass=c['val_pass'], status=c['status']) for c in results],
        best=best['id'] if best else None, cross_family=cross,
        seconds=dict(distance=t2 - t1, patches=t3 - t2, propose=t4 - t3, refine=t5 - t4,
                     evaluate=t6 - t5, validation=t7 - t6, total=time.time() - t0),
        peak_rss=int(rss.peak), output_bytes=int(used), budget=protocol['budget'],
        source_final={k: sha(ROOT / 'data/sessions/cap_20261017_113516' / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]},
        no_val_fit=True, ground_identity=False, state='CANDIDATE_PLANE_PREVIEW'))
    src.close()
    print(json.dumps(dict(best=best['id'] if best else None,
                          candidates=[(c['id'], c['fit_pass'], c['val_pass'], c['status']) for c in results])))
    print(json.dumps(dict(total=time.time() - t0, peak=rss.peak, bytes=used)))


if __name__ == '__main__':
    main()
