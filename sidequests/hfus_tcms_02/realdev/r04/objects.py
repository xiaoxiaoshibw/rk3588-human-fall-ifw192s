"""T6: one-frame consistency of points, M0, candidates and boxes; velocity/covariance NOT_RUN.

Real frozen assets carry no velocity or full covariance, so those two transforms stay NOT_RUN and
are only exercised through the synthetic adapter, which is recorded separately.
"""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X

SAMPLE_FRAMES = [0, 192, 193, 270, 271, 300, 430, 439, 520, 750, 779]


def frame_of_global(offsets, g):
    i = np.searchsorted(offsets, g, side='right') - 1
    return int(i), int(g - offsets[i])


if __name__ == '__main__':
    protocol = C.load(C.OUT / 'PROTOCOL_V2.json')
    art = C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json')
    T = X.Transform(art)
    run = C.OUT / 'RUN'
    recs = [json.loads(l) for l in (run / 'frames.jsonl').read_text(encoding='utf8').splitlines()]
    if len(recs) != 780:
        raise SystemExit('frame log incomplete')
    src, times = C.load_source()
    offsets = np.array([f['offset_points'] for f in src.frames], dtype='i8')
    out = dict(item=C.ITEM, transform_id=T.id, coordinate_version=T.version, frames=len(recs), checks={})
    try:
        bad = [r['fi'] for r in recs if r['transform_id'] != T.id or r['coordinate_version'] != T.version]
        out['checks']['all_records_same_transform'] = dict(PASS=not bad, offenders=bad[:10])
        out['checks']['no_raw_coordinate_records'] = dict(
            PASS=all(r['coordinate_version'] != 'RAW/innolidar' for r in recs),
            note='online_state RAW means "before M0", the coordinate version is still S3_LOCAL')
        out['checks']['single_map_id'] = dict(
            PASS=len({r['map_id'] for r in recs if r['map_id']}) == 1,
            map_ids=sorted({r['map_id'] for r in recs if r['map_id']}))
        out['checks']['no_reset'] = dict(PASS=not any(r['reset'] for r in recs),
                                         resets=[r['fi'] for r in recs if r['reset']])
        out['checks']['identity_not_reused'] = dict(
            PASS=all(r['track']['state'] == 'UNCONFIRMED' and r['track']['rows'] == 0 for r in recs),
            note='new coordinate version: identity cleared, no S1/S2 confirmation reused, track never created')
        m = np.load(C.OUT / 'M0/primary/map/surfaces.npz')
        centers, minimum, maximum = m['centers'], m['minimum'], m['maximum']
        support, indptr = m['support_global'], m['indptr']
        rng = np.random.default_rng(17)
        pick = rng.choice(len(centers), size=200, replace=False)
        err = []
        for s in pick:
            rows = support[indptr[s]:indptr[s + 1]]
            pts = np.empty((len(rows), 3))
            for k, g in enumerate(rows):
                fi, row = frame_of_global(offsets, g)
                p = src.frame(fi)['xyz'][row]
                pts[k] = T.points(p[None, :], T.tag(fi, False), fi, source_validity=True)[0]
            err.append(float(np.abs(pts.mean(0) - centers[s]).max()))
            if not (np.all(pts.min(0) >= minimum[s] - 1e-9) and np.all(pts.max(0) <= maximum[s] + 1e-9)):
                raise ValueError('support points outside the frozen surface AABB')
        out['checks']['m0_centers_from_local_support_rows'] = dict(
            PASS=bool(max(err) <= 1e-9), surfaces_checked=len(pick), max_abs_error_m=float(max(err)),
            note='surface centroid equals the mean of its local support rows')
        n_surf = len(centers)
        total_rows = int(offsets[-1] + src.frames[-1]['count_points'])
        ok_ids = bool((indptr[0] == 0) and (np.diff(indptr) >= 0).all()
                      and len(indptr) == n_surf + 1 and indptr[-1] == len(support)
                      and (support >= 0).all() and (support < total_rows).all())
        out['checks']['support_csr_in_range'] = dict(
            PASS=ok_ids, support_rows=int(len(support)), surfaces=int(n_surf),
            indptr_len=int(len(indptr)), indptr_last=int(indptr[-1]), total_source_rows=total_rows,
            note='support_global holds global source rows; indptr indexes them per surface')
        sample = {}
        for fi in SAMPLE_FRAMES:
            r = recs[fi]
            f = src.frame(fi)
            local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
            z = np.load(run / 'frames' / ('%04d.npz' % fi))
            ledger = z['current']
            valid = (ledger['flags'] & 1) != 0
            if int(valid.sum()) != r['valid']:
                raise ValueError('valid count mismatch at fi %d' % fi)
            inv = ~valid
            same = np.array_equal(local[inv].view('u8'), f['xyz'][inv].view('u8'))
            cand = ledger['candidate']
            cid = np.unique(cand[cand >= 0])
            ext = []
            for c in cid:
                rows = np.flatnonzero(cand == c)
                ext.append(float(np.ptp(local[rows], axis=0).max()))
            sample[str(fi)] = dict(rows=int(len(ledger)), valid=int(valid.sum()), candidates=int(len(cid)),
                                   max_candidate_extent_m=float(max(ext)) if ext else None,
                                   invalid_rows_keep_raw_xyz=bool(same),
                                   surfaces_in_range=bool((ledger['surface'] < n_surf).all()))
            if not same:
                raise ValueError('invalid rows were altered at fi %d' % fi)
            if ext and max(ext) > 2.4 + 1e-9:
                raise ValueError('candidate extent exceeds the registered 2.4 m limit')
        out['checks']['ledger_rows'] = dict(PASS=True, per_frame=sample)
        # synthetic adapter: velocity R-only, covariance R Sigma R.T, 8-corner OBB, hard rejects
        vel = np.array([0.3, -0.2, 0.1])
        assert np.allclose(T.vectors(vel), T.R @ vel)
        assert not np.allclose(T.vectors(vel), T.R @ vel + T.t)
        cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.09, 0.0], [0.0, 0.0, 0.16]])
        assert np.allclose(T.covariance(cov), T.R @ cov @ T.R.T)
        lo, hi = np.array([1.0, 0.5, -0.1]), np.array([1.4, 0.9, 0.2])
        corners = T.box(lo, hi, 0)
        direct = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        assert np.allclose(corners, direct @ T.R.T + T.t)
        assert corners.shape == (8, 3)
        rejected = {}
        for name, fn in [
                ('second_transform', lambda: T.points(np.zeros((1, 3)), T.tag(0, True), 0)),
                ('wrong_frame', lambda: T.points(np.zeros((1, 3)), {'fi': 0, 'frame': 'RAW', 'transform_id': None,
                                                                   'coordinate_version': 'S3_LOCAL/other'}, 0)),
                ('nonfinite_object', lambda: T.points(np.array([[np.nan, 0.0, 0.0]]), T.tag(0, False), 0))]:
            try:
                fn()
                rejected[name] = 'NOT_REJECTED'
            except ValueError as e:
                rejected[name] = str(e)
        obj = T.object(dict(fi=0, frame='RAW', transform_id=None, coordinate_version='RAW/innolidar',
                            center=[1.2, 0.7, 0.1], min=[1.0, 0.5, -0.1], max=[1.4, 0.9, 0.2],
                            velocity=[0.3, -0.2, 0.1], covariance=cov.tolist(), version='synthetic',
                            identity_source='SYNTHETIC'), 0)
        out['synthetic_adapter'] = dict(
            PASS=bool(not any(v == 'NOT_REJECTED' for v in rejected.values())),
            velocity_uses_rotation_only=bool(np.allclose(T.vectors(vel), T.R @ vel)),
            covariance_rotated=bool(np.allclose(T.covariance(cov), T.R @ cov @ T.R.T)),
            box_corners=8, box_is_axis_aligned_in_local=True, rejects=rejected,
            object_fields=dict(frame=obj['frame'], transform_id=obj['transform_id'],
                               coordinate_version=obj['coordinate_version'],
                               identity_valid_for_coordinate_version=obj['identity_valid_for_coordinate_version'],
                               human_confirmation=obj['human_confirmation'],
                               has_obb_corners=len(obj['obb_corners'])), note='synthetic only; never a measured value')
        frozen_assets = C.R01_RUN / 'main'
        sample_record = json.loads((frozen_assets / '0430.json').read_text(encoding='utf8'))
        keys = set(sample_record['track']) | set(sample_record['candidates'][0] if sample_record['candidates'] else {})
        out['real_frozen_assets'] = dict(
            velocity_field='velocity' in keys, covariance_field='covariance' in keys,
            status='NOT_RUN', reason='the frozen REALDEV assets carry no velocity/full covariance fields; '
                                     'no measured values are fabricated',
            checked_record=str(frozen_assets / '0430.json'), fields=sorted(keys))
        out['PASS'] = bool(all(v['PASS'] for k, v in out['checks'].items() if isinstance(v, dict) and 'PASS' in v)
                           and out['synthetic_adapter']['PASS']
                           and out['checks']['ledger_rows']['PASS'])
        C.write(C.OUT / 'OBJECTS_CHECK.json', out)
        print(json.dumps(dict(PASS=out['PASS'], checks={k: (v.get('PASS') if isinstance(v, dict) else None)
                                                         for k, v in out['checks'].items()},
                              synthetic=out['synthetic_adapter']['PASS'],
                              real=out['real_frozen_assets']['status']), ensure_ascii=False))
    finally:
        src.close()
