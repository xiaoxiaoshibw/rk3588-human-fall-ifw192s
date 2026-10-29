"""S3 transform artifact: C3D_03 (n,d) -> one-shot S3_LOCAL levelling, with hard rejects."""
import copy
import itertools
import json
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C

RAW_VERSION = C.RAW
LOCAL_FRAME = 'candidate_local'


def valid_xyz(p):
    p = np.asarray(p)
    return np.isfinite(p).all(axis=-1) & np.any(p != 0, axis=-1)


def build(n, d, ref, candidate_id, source_sha, s2_basis, protocol_sha):
    n = np.asarray(n, dtype=float)
    if n.shape != (3,) or not np.isfinite(n).all() or not np.isfinite(d):
        raise ValueError('Nonfinite plane')
    norm = np.linalg.norm(n)
    if norm < 1e-12:
        raise ValueError('Degenerate normal')
    n, d = n / norm, float(d) / norm
    ref = np.asarray(ref, dtype=float)
    if ref.shape != (3,) or not np.isfinite(ref).all() or np.linalg.norm(ref) < 1e-12:
        raise ValueError('Invalid reference axis')
    projection = ref - np.dot(ref, n) * n
    if np.linalg.norm(projection) < 1e-8:
        raise ValueError('Reference axis degeneracy; v1 has no registered fallback axis')
    u = projection / np.linalg.norm(projection)
    v = np.cross(n, u)
    R = np.vstack([u, v, n])
    t = np.array([0.0, 0.0, d])
    if not np.allclose(R @ R.T, np.eye(3), atol=1e-10, rtol=0) or abs(np.linalg.det(R) - 1.0) > 1e-10:
        raise ValueError('Constructed basis is not a proper rotation')
    artifact = dict(
        item=C.ITEM, kind='s3_local_levelling_transform', schema=1, units='m',
        from_frame=RAW_VERSION, to_frame=LOCAL_FRAME,
        coordinate_version=None, transform_id=None,
        candidate_id=candidate_id, plane=dict(normal=n.tolist(), d_m=d, form='n.p + d = 0'),
        basis=dict(ref_axis=ref.tolist(),
                   ref_axis_source='historical TLS R first row (read-only seed, no fit)',
                   u=u.tolist(), v=v.tolist(), n=n.tolist(),
                   construction='u = normalize(ref - (ref.n) n); v = n x u; R = [u; v; n]; t = (0, 0, d)'),
        R=R.tolist(), t=t.tolist(),
        math=dict(column='p_local = R @ p_raw + t', row='p_raw @ R.T + t',
                  z_local='n.p + d', rotation_atol=1e-10, det_tolerance=1e-10,
                  roundtrip_float64_m='max(1e-8, 1e-12*||p||)', display_float32_m='max(1e-5, 1e-6*||p||)',
                  reference_projection_min=1e-8, fallback_axis=None),
        source_sha256=dict(source_sha), s2_basis=dict(s2_basis), protocol_sha=protocol_sha,
        constructed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        qualification=dict(identity_confirmed=False, geometry_validated_local=False,
                           physical_verified=False, runtime_eligible=False),
        state='CANDIDATE_PLANE_PREVIEW', mode='OFFLINE_REVIEW',
        rejections=['wrong direction', 'reflection', 'non-orthogonal', 'wrong frame/version',
                    'second transform of levelled coordinates', 'version mixing',
                    'reference axis projection < 1e-8 (no automatic alternative)'])
    artifact['transform_id'] = C.digest(dict(artifact, transform_id=None, coordinate_version=None))
    artifact['coordinate_version'] = 'S3_LOCAL/' + artifact['transform_id']
    return artifact


class Transform:
    """Strict one-shot adapter; every object it emits carries frame/version/transform_id."""

    def __init__(self, artifact):
        a = copy.deepcopy(artifact)
        self.artifact = a
        self.R = np.asarray(a['R'], dtype=float)
        self.t = np.asarray(a['t'], dtype=float)
        self.id = a['transform_id']
        self.version = a['coordinate_version']
        self.frame = a['to_frame']
        self.raw_version = a['from_frame']
        if (a['from_frame'] != RAW_VERSION or a['to_frame'] != LOCAL_FRAME or a['units'] != 'm'
                or not self.id or not self.version.startswith('S3_LOCAL/')):
            raise ValueError('Wrong transform direction/units/version')
        if (self.R.shape != (3, 3) or self.t.shape != (3,) or not np.isfinite(self.R).all()
                or not np.isfinite(self.t).all()
                or not np.allclose(self.R @ self.R.T, np.eye(3), atol=1e-10, rtol=0)
                or abs(np.linalg.det(self.R) - 1.0) > 1e-10):
            raise ValueError('Nonfinite, reflection or nonorthogonal transform')
        n = np.asarray(a['plane']['normal'], dtype=float)
        if not np.allclose(self.R[2], n, atol=1e-12, rtol=0) or abs(self.t[2] - a['plane']['d_m']) > 1e-12:
            raise ValueError('Plane/transform direction mismatch')
        if any(a['qualification'][k] for k in ('identity_confirmed', 'physical_verified', 'runtime_eligible')):
            raise ValueError('Candidate cannot gain identity/physical/runtime qualification')
        if self.version != 'S3_LOCAL/' + self.id:
            raise ValueError('Version/id mismatch')

    def tag(self, fi, local=True):
        return dict(fi=fi, frame=LOCAL_FRAME if local else 'RAW',
                    transform_id=self.id if local else None,
                    coordinate_version=self.version if local else self.raw_version)

    def require_raw(self, tag, fi):
        if tag != self.tag(fi, False):
            raise ValueError('Wrong frame/version/fi or repeated transform')

    def points(self, xyz, tag, fi, source_validity=False):
        """Invalid/zero rows keep their original values (never transformed)."""
        self.require_raw(tag, fi)
        p = np.asarray(xyz, dtype=float)
        if p.shape[-1:] != (3,):
            raise ValueError('Expected XYZ')
        out = p.copy()
        if source_validity:
            mask = valid_xyz(p)
            out[mask] = p[mask] @ self.R.T + self.t
        else:
            if not np.isfinite(p).all():
                raise ValueError('Nonfinite object coordinate')
            out = p @ self.R.T + self.t
        return out

    def inverse(self, xyz):
        return (np.asarray(xyz) - self.t) @ self.R

    def vectors(self, v):
        a = np.asarray(v, dtype=float)
        if a.shape[-1:] != (3,) or not np.isfinite(a).all():
            raise ValueError('Invalid direction/velocity')
        return a @ self.R.T

    def covariance(self, sigma):
        s = np.asarray(sigma, dtype=float)
        if s.shape[-2:] != (3, 3) or not np.isfinite(s).all():
            raise ValueError('Invalid covariance')
        return self.R @ s @ self.R.T

    def box(self, lo, hi, fi):
        lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
        if lo.shape != (3,) or hi.shape != (3,) or np.any(lo > hi):
            raise ValueError('Invalid box')
        corners = np.array(list(itertools.product(*zip(lo, hi))))
        return self.points(corners, self.tag(fi, False), fi)

    def object(self, obj, fi):
        self.require_raw({k: obj[k] for k in self.tag(fi, False)}, fi)
        out = copy.deepcopy(obj)
        for key in ['center', 'position', 'predicted_center']:
            if out.get(key) is not None:
                out[key] = self.points(out[key], self.tag(fi, False), fi).tolist()
        for key in ['velocity', 'direction']:
            if out.get(key) is not None:
                out[key] = self.vectors(out[key]).tolist()
        if out.get('covariance') is not None:
            out['covariance'] = self.covariance(out['covariance']).tolist()
        if 'min' in out or 'max' in out:
            out['obb_corners'] = self.box(out.pop('min'), out.pop('max'), fi).tolist()
        out.update(self.tag(fi))
        if out.get('version'):
            out['historical_version'] = out['version']
            out['version'] = out['version'] + '/' + self.id
        if 'identity_source' in out:
            out['historical_identity_source'] = out.pop('identity_source')
        out.update(identity_valid_for_coordinate_version=False, human_confirmation=False)
        return out


def check_points(T, raw, local):
    mask = valid_xyz(raw)
    p, q = raw[mask], local[mask]
    if not len(p):
        raise ValueError('No valid points to check')
    e64 = np.linalg.norm(T.inverse(q) - p, axis=1)
    e32 = np.linalg.norm(q.astype('f4').astype(float) - q, axis=1)
    norm = np.linalg.norm(p, axis=1)
    tol64 = np.maximum(1e-8, 1e-12 * norm)
    tol32 = np.maximum(1e-5, 1e-6 * norm)
    plane = p @ T.R[2] + T.t[2]
    same_invalid = np.array_equal(raw[~mask].view('u8'), local[~mask].view('u8'))
    result = dict(valid=int(mask.sum()), invalid=int((~mask).sum()),
                  roundtrip_max_m=float(e64.max(initial=0)),
                  display_float32_max_m=float(e32.max(initial=0)),
                  z_equation_max_m=float(np.abs(q[:, 2] - plane).max(initial=0)),
                  z_gt_1e12=int(np.sum(np.abs(q[:, 2] - plane) > 1e-12)),
                  invalid_bytes_identical=bool(same_invalid),
                  roundtrip_over_tol=int(np.sum(e64 > tol64)),
                  display_over_tol=int(np.sum(e32 > tol32)),
                  plane_points_z_max_m=float(np.abs(q[np.abs(plane) <= 1e-6][:, 2]).max(initial=0)))
    if (result['roundtrip_over_tol'] or result['display_over_tol'] or result['z_gt_1e12']
            or not same_invalid or result['plane_points_z_max_m'] > 1e-6):
        raise ValueError('Coordinate conservation/tolerance failure ' + repr(result))
    return result


if __name__ == '__main__':
    protocol = C.load(C.OUT / 'PROTOCOL_V1.json')
    cand = C.load(C.OUT / 'CANDIDATE_FREEZE.json')['chosen']
    hist = C.load(C.HIST)
    step = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if step == 'build':
        artifact = build(cand['n'], cand['d'], np.asarray(hist['R'], dtype=float)[0], cand['id'],
                         C.FROZEN, dict(seal=C.FROZEN['s2_seal'], report=C.FROZEN['s2_report'],
                                        candidates=C.FROZEN['s2_candidates'],
                                        domains=C.FROZEN['s2_domains'],
                                        protocol=C.FROZEN['s2_protocol'],
                                        role='candidate parameters only; no S3 fit'),
                         C.sha(C.OUT / 'PROTOCOL_V1.json'))
        C.write(C.OUT / 'TRANSFORM/TRANSFORM_S3.json', artifact)
        print(json.dumps(dict(transform_id=artifact['transform_id'], version=artifact['coordinate_version'])))
        raise SystemExit(0)
    artifact = C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json')
    frozen_id = artifact['transform_id']
    if C.digest(dict(artifact, transform_id=None, coordinate_version=None)) != frozen_id:
        raise SystemExit('ARTIFACT SELF-HASH MISMATCH')
    expected = build(cand['n'], cand['d'], np.asarray(hist['R'], dtype=float)[0], cand['id'],
                     C.FROZEN, artifact['s2_basis'], artifact['protocol_sha'])
    for key in ('R', 't', 'plane', 'basis', 'from_frame', 'to_frame', 'units', 'candidate_id'):
        if expected[key] != artifact[key]:
            raise SystemExit('ARTIFACT DRIFT vs C3D_03 math: ' + key)
    T = Transform(artifact)
    src, times = C.load_source()
    checks, per_frame = {}, {}
    try:
        for fi in [0, 96, 192, 193, 270, 289, 400, 560, 779]:
            f = src.frame(fi)
            local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
            r = check_points(T, f['xyz'], local)
            r['fi'] = fi
            r['rows'] = int(len(f['xyz']))
            r['relative_s'] = times[fi]
            per_frame[str(fi)] = r
        allv = [T.points(src.frame(fi)['xyz'], T.tag(fi, False), fi, source_validity=True) for fi in (0, 779)]
        for i, fi in enumerate((0, 779)):
            per_frame[str(fi)]['z_abs_p50_m'] = float(np.median(np.abs(allv[i][valid_xyz(allv[i])][:, 2])))
        checks['orthonormal_max_abs'] = float(np.abs(T.R @ T.R.T - np.eye(3)).max())
        checks['det'] = float(np.linalg.det(T.R))
        checks['reference_projection'] = float(np.linalg.norm(
            np.asarray(hist['R'], dtype=float)[0] - np.dot(np.asarray(hist['R'], dtype=float)[0], T.R[2]) * T.R[2]))
        checks['normal_vs_historical_deg'] = float(np.degrees(np.arccos(np.clip(
            abs(T.R[2] @ np.asarray(hist['R'], dtype=float)[2]), -1, 1))))
        checks['dx_from_historical_m'] = float(abs(T.t[2] - np.asarray(hist['t'])[2]))
        checks['plane_d_m'] = float(T.t[2])
        rejections = {}
        try:
            T.points(np.zeros((2, 3)), T.tag(1, True), 1)
            rejections['second_transform'] = 'NOT_REJECTED'
        except ValueError as e:
            rejections['second_transform'] = str(e)
        for name, broken in [('reflection', dict(artifact, R=(np.diag([1.0, 1.0, -1.0]) @ T.R).tolist())),
                             ('nonorthogonal', dict(artifact, R=(T.R * 1.01).tolist()))]:
            try:
                Transform(broken)
                rejections[name] = 'NOT_REJECTED'
            except ValueError as e:
                rejections[name] = str(e)
        try:
            build([0.0, 0.0, 1.0], 1.0, [0.0, 0.0, 1.0], 'SYN', C.FROZEN, {}, 'x')
            rejections['degenerate_reference'] = 'NOT_REJECTED'
        except ValueError as e:
            rejections['degenerate_reference'] = str(e)
        try:
            bad = dict(artifact, from_frame='ground_offline_display', to_frame=LOCAL_FRAME)
            bad['transform_id'] = C.digest(dict(bad, transform_id=None, coordinate_version=None))
            bad['coordinate_version'] = 'S3_LOCAL/' + bad['transform_id']
            Transform(bad)
            rejections['wrong_direction'] = 'NOT_REJECTED'
        except ValueError as e:
            rejections['wrong_direction'] = str(e)
        checks['rejections'] = rejections
        result = dict(
            item=C.ITEM, transform_id=T.id, coordinate_version=T.version,
            artifact_sha=C.sha(C.OUT / 'TRANSFORM/TRANSFORM_S3.json'),
            checks=checks, per_frame=per_frame, tolerances=protocol['transform']['checks'],
            frames_checked=[0, 96, 192, 193, 270, 289, 400, 560, 779],
            invalid_rows='kept at original XYZ values; raw 28B bytes never rewritten',
            PASS=bool(not any(v == 'NOT_REJECTED' for v in rejections.values())))
        frozen = C.OUT / 'TRANSFORM/TRANSFORM_CHECK.json'
        if frozen.exists():
            old = C.load(frozen)
            same = (old['checks'] == checks and old['per_frame'] == per_frame
                    and old['transform_id'] == T.id and old['artifact_sha'] == result['artifact_sha'])
            C.write(C.OUT / 'TRANSFORM/TRANSFORM_RECHECK.json', dict(
                result, frozen_check_sha=C.sha(frozen), matches_frozen_check=bool(same),
                note='independent recomputation of the frozen transform check'))
            if not same:
                raise SystemExit('RECHECK DIFFERS FROM THE FROZEN TRANSFORM CHECK')
        else:
            C.write(frozen, result)
        print(json.dumps(dict(transform_id=T.id, version=T.version,
                              normal_deg=checks['normal_vs_historical_deg'], dd=checks['dx_from_historical_m'],
                              max64=max(v['roundtrip_max_m'] for v in per_frame.values()),
                              max32=max(v['display_float32_max_m'] for v in per_frame.values()),
                              rejections=rejections), ensure_ascii=False))
    finally:
        src.close()
