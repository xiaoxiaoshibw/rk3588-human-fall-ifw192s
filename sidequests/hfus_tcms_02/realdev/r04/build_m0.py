"""T3: rebuild M0 in S3_LOCAL from FIT rows only, using r01 FrozenMap semantics verbatim.

Primary build keeps r01's frozen map protocol (0.05 m voxel, tau 0.08, 20 observations,
5 frames, >= 1.0 s span). The plan text names 0.13 m, which is r01's component voxel, so a
0.13 m sensitivity build is reported side by side and is never used by the application chain.
"""
import json
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X

FIT_VALID_ROWS_S2 = 7181833  # S2 REPORT section 2: FIT [0,20)s valid rows


def r01_map_protocol(tau=0.08, voxel=0.05, max_surfaces=750000):
    return dict(version='S3/RD-PROTOCOL/1 (r01 FrozenMap semantics)', source_kind='REAL_DEVELOPMENT', role='B',
                independent_test=False, mode='DIAGNOSTIC', coordinate=None,
                split=dict(build=[0.0, 20.0], temporal_validation=[20.0, 28.0], audit=[28.0, 30.0]),
                qualification=dict(min_surface_observations=20, min_surface_distinct_frames=5,
                                   min_surface_time_span_s=1.0, layout_consistent=None,
                                   rule='r01 numeric M0 eligibility only; no layout evidence claimed in S3'),
                map=dict(voxel_m=voxel, tau=tau, max_surfaces=max_surfaces,
                         finite_support='observed voxel AABB + finite nearest-centroid tau; no infinite plane'),
                ground_audit=None,
                budget=dict(peak_rss_bytes=2147483648, full_wall_seconds=2400),
                seed=17, physical_ground_conclusion=False)


def frame(local_xyz, raw_meta, T, fi, times):
    return dict(sid=raw_meta['sid'], fi=fi, offset=raw_meta['offset'], source_sha256=raw_meta['source_sha256'],
                coordinate_version=T.version, kind=raw_meta['kind'], time_ns=raw_meta['time_ns'],
                relative_s=times[fi], xyz=local_xyz)


def build(src, times, T, fit, dest, tau, voxel, max_surfaces):
    pipe = C.r01_pipeline()
    protocol = r01_map_protocol(tau, voxel, max_surfaces)
    protocol['coordinate'] = T.version
    dest.mkdir(parents=True, exist_ok=False)
    frozen = pipe.FrozenMap(dest, src.binding, T.version, protocol)
    rows = []
    t0 = time.perf_counter()
    for fi in fit:
        f = src.frame(fi)
        local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
        _, valid = pipe.validity(f['xyz'])
        frozen.add(frame(local, f, T, fi, times))
        rows.append(dict(fi=fi, rows=int(len(local)), valid=int(valid.sum()), time_ns=f['time_ns']))
    frozen.freeze()
    frozen.bind_exact_time(src.stamps)
    elapsed = time.perf_counter() - t0
    map_id = frozen.map_id
    fits = dict(total_rows=sum(r['rows'] for r in rows), fit_valid_rows=sum(r['valid'] for r in rows),
                build_frames=len(rows), support_rows=int(len(frozen.support_global)),
                surfaces=frozen.n, eligible_surfaces=int(frozen.eligible.sum()),
                voxel_m=voxel, tau_m=tau, map_id=map_id, coordinate=T.version,
                seconds=elapsed, first_fi=rows[0]['fi'], last_fi=rows[-1]['fi'])
    if fits['support_rows'] != fits['fit_valid_rows']:
        raise ValueError('M0 support rows != FIT valid rows: %r' % fits)
    if fits['fit_valid_rows'] != FIT_VALID_ROWS_S2:
        raise ValueError('M0 FIT valid rows differ from the S2 FIT denominator')
    for a in frozen.arrays.values():
        a.setflags(write=False)
    return frozen, fits


if __name__ == '__main__':
    protocol = C.load(C.OUT / 'PROTOCOL_V2.json')
    dom = C.load(C.OUT / 'DOMAINS/S3_DOMAINS.json')
    if C.sha(C.OUT / 'DOMAINS/domains_s3.npz') != dom['domains_sha']:
        raise SystemExit('DOMAIN ARRAY DRIFT')
    T = X.Transform(C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json'))
    if dom['transform_id'] != T.id:
        raise SystemExit('DOMAIN/TRANSFORM MISMATCH')
    src, times = C.load_source()
    fit, val, pre = C.roles(times)
    try:
        primary, pstats = build(src, times, T, fit, C.OUT / 'M0/primary',
                                 protocol['m0']['primary']['tau_m'], protocol['m0']['primary']['voxel_m'],
                                 protocol['m0']['primary']['max_surfaces'])
        sens, sstats = build(src, times, T, fit, C.OUT / 'M0/sensitivity_0p13', 0.08, 0.13,
                             protocol['m0']['primary']['max_surfaces'])
        r01 = C.load(C.R01_RUN / 'map/MAP.json')
        r01_surfaces = np.load(C.R01_RUN / 'map/surfaces.npz')
        comparison = dict(
            r01_raw=dict(map_id=r01['map_id'], voxel_m=r01['protocol']['map']['voxel_m'],
                         surfaces=r01['surfaces'], eligible_surfaces=r01['eligible_surfaces'],
                         coordinate=r01['coordinate']),
            s3_local=dict(map_id=pstats['map_id'], voxel_m=pstats['voxel_m'],
                          surfaces=pstats['surfaces'], eligible_surfaces=pstats['eligible_surfaces'],
                          coordinate=pstats['coordinate']),
            surface_ratio=pstats['surfaces'] / r01['surfaces'],
            eligible_ratio=pstats['eligible_surfaces'] / r01['eligible_surfaces'],
            r01_supports_finite=int(np.isfinite(r01_surfaces['centers']).all()),
            statement='representation difference only (new coordinate version); never equivalence')
        C.write(C.OUT / 'M0/M0.json', dict(
            item=C.ITEM, transform_id=T.id, coordinate_version=T.version,
            domains_sha=dom['domains_sha'], protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'),
            rows_rule='FIT [0,20) valid rows only; VAL/prefix/action rows never enter the map',
            primary=pstats, sensitivity=sstats, comparison=comparison,
            carry=dict(frame='S3_LOCAL', transform_id=T.id, coordinate_version=T.version,
                       map_id=pstats['map_id'], support_csr='support_global + indptr, every FIT valid row',
                       per_frame_support='M0/primary/map/support_%04d.npz'),
            build_end_fi=fit[-1], available_after_fi=fit[-1] + 1,
            eligible_rule=dict(min_surface_observations=20, min_surface_distinct_frames=5,
                               min_surface_time_span_s=1.0),
            anomaly_checks=dict(support_rows_equal_fit_valid_rows=True,
                                fit_valid_rows_match_s2_ftr=bool(pstats['fit_valid_rows'] == FIT_VALID_ROWS_S2)),
            state='CANDIDATE_PLANE_PREVIEW'))
        print(json.dumps(dict(primary=pstats, sensitivity=sstats, comparison=comparison), ensure_ascii=False))
        del primary, sens
    finally:
        src.close()
