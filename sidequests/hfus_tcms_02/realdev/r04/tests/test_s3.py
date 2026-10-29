"""S3 contract tests: transform math, hard rejects, object adapters, gates, causal state."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transform as X  # noqa: E402

N = np.array([-0.4265240687245509, -0.022919694282833247, 0.9041857698574097])
D = 1.3371657243363564
REF = np.array([0.8905792877996809, 0.0, 0.4548280247986191])
S2_BASIS = dict(seal='x', role='test')
ART = X.build(N, D, REF, 'C3D_03', dict(meta='m', points='p'), S2_BASIS, 'protocol')


class TransformMath(unittest.TestCase):
    def setUp(self):
        self.T = X.Transform(ART)

    def test_artifact_fields(self):
        for key in ('candidate_id', 'plane', 'R', 't', 'units', 'from_frame', 'to_frame',
                    'source_sha256', 's2_basis', 'constructed_utc', 'transform_id', 'coordinate_version',
                    'qualification'):
            self.assertIn(key, ART)
        self.assertEqual(ART['units'], 'm')
        self.assertTrue(ART['coordinate_version'].startswith('S3_LOCAL/'))
        self.assertEqual(ART['candidate_id'], 'C3D_03')
        self.assertEqual(set(ART['qualification']),
                         {'identity_confirmed', 'geometry_validated_local', 'physical_verified', 'runtime_eligible'})
        self.assertFalse(any(ART['qualification'].values()))

    def test_orthonormal_and_det(self):
        self.assertLess(np.abs(self.T.R @ self.T.R.T - np.eye(3)).max(), 1e-10)
        self.assertAlmostEqual(float(np.linalg.det(self.T.R)), 1.0, places=12)
        np.testing.assert_allclose(self.T.R[2], ART['plane']['normal'], atol=1e-12)

    def test_plane_maps_to_zero_and_roundtrip(self):
        rng = np.random.default_rng(3)
        p = rng.normal(size=(500, 3)) * 3
        q = self.T.points(p, self.T.tag(0, False), 0)
        plane = p @ self.T.R[2] + self.T.t[2]
        self.assertLess(np.abs(q[:, 2] - plane).max(), 1e-12)
        self.assertLess(np.linalg.norm(self.T.inverse(q) - p, axis=1).max(), 1e-12)
        self.assertLess(np.abs(q.astype('f4').astype(float) - q).max(), 1e-5)

    def test_plane_points_have_zero_z(self):
        rng = np.random.default_rng(4)
        xy = rng.normal(size=(200, 2))
        # invert a target plane point back to RAW: q=(u,v,0) -> p = (q - t) @ R
        raw = (np.column_stack([xy, np.zeros(len(xy))]) - self.T.t) @ self.T.R
        q = self.T.points(raw, self.T.tag(0, False), 0)
        self.assertLess(np.abs(q[:, 2]).max(), 1e-12)

    def test_invalid_and_zero_rows_untouched(self):
        raw = np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0], [np.nan, 0.0, 1.0], [0.0, 0.0, 0.0]])
        q = self.T.points(raw, self.T.tag(7, False), 7, source_validity=True)
        np.testing.assert_array_equal(q[[1, 3]], raw[[1, 3]])
        self.assertTrue(np.array_equal(q[2].view('u8'), raw[2].view('u8')))
        self.assertTrue(np.isfinite(q[0]).all())

    def test_vectors_covariance_box(self):
        v = np.array([0.5, -0.25, 0.125])
        np.testing.assert_allclose(self.T.vectors(v), self.T.R @ v)
        cov = np.diag([0.01, 0.04, 0.09])
        np.testing.assert_allclose(self.T.covariance(cov), self.T.R @ cov @ self.T.R.T)
        lo, hi = np.array([1.0, 0.5, -0.1]), np.array([1.4, 0.9, 0.2])
        corners = self.T.box(lo, hi, 3)
        self.assertEqual(corners.shape, (8, 3))
        direct = np.array([[x, y, z] for x in (1.0, 1.4) for y in (0.5, 0.9) for z in (-0.1, 0.2)])
        np.testing.assert_allclose(corners, direct @ self.T.R.T + self.T.t)
        self.assertEqual(len(np.unique(corners, axis=0)), 8)
        only_two = np.array([self.T.points(lo, self.T.tag(3, False), 3), self.T.points(hi, self.T.tag(3, False), 3)])
        self.assertFalse(np.allclose(corners[:2], only_two))

    def test_object_patch(self):
        obj = dict(fi=2, frame='RAW', transform_id=None, coordinate_version='RAW/innolidar',
                   center=[1.2, 0.7, 0.1], min=[1.0, 0.5, -0.1], max=[1.4, 0.9, 0.2],
                   velocity=[0.3, -0.2, 0.1], covariance=np.diag([0.01, 0.04, 0.09]).tolist(),
                   version='synthetic', identity_source='SYNTHETIC')
        out = self.T.object(obj, 2)
        self.assertEqual(out['frame'], 'candidate_local')
        self.assertEqual(out['transform_id'], self.T.id)
        self.assertEqual(len(out['obb_corners']), 8)
        self.assertFalse(out['identity_valid_for_coordinate_version'])
        self.assertFalse(out['human_confirmation'])
        self.assertEqual(out['historical_identity_source'], 'SYNTHETIC')
        self.assertTrue(out['version'].endswith(self.T.id))

    def test_rejects(self):
        with self.assertRaises(ValueError):
            X.Transform(dict(ART, from_frame='ground_offline_display'))
        with self.assertRaises(ValueError):
            X.Transform(dict(ART, to_frame='something_else'))
        with self.assertRaises(ValueError):
            X.Transform(dict(ART, R=(np.diag([1.0, 1.0, -1.0]) @ np.asarray(ART['R'])).tolist()))
        with self.assertRaises(ValueError):
            X.Transform(dict(ART, R=(np.asarray(ART['R']) * 1.01).tolist()))
        with self.assertRaises(ValueError):
            X.Transform(dict(ART, units='mm'))
        with self.assertRaises(ValueError):
            X.build([0.0, 0.0, 1.0], 1.0, [0.0, 0.0, 5.0], 'SYN', {}, {}, 'x')
        with self.assertRaises(ValueError):
            X.build([np.nan, 0.0, 1.0], 1.0, REF, 'SYN', {}, {}, 'x')
        with self.assertRaises(ValueError):
            self.T.points(np.zeros((1, 3)), self.T.tag(0, True), 0)
        with self.assertRaises(ValueError):
            self.T.points(np.array([[np.nan, 0.0, 0.0]]), self.T.tag(0, False), 0)

    def test_check_points_conservation(self):
        rng = np.random.default_rng(11)
        raw = rng.normal(size=(1000, 3)) * 4
        raw[::17] = 0.0
        raw[1::23] = np.nan
        local = self.T.points(raw, self.T.tag(5, False), 5, source_validity=True)
        out = X.check_points(self.T, raw, local)
        self.assertTrue(out['invalid_bytes_identical'])
        self.assertEqual(out['roundtrip_over_tol'], 0)
        self.assertEqual(out['display_over_tol'], 0)
        broken = local.copy()
        broken[0, 0] += 0.01
        with self.assertRaises(ValueError):
            X.check_points(self.T, raw, broken)


class Gates(unittest.TestCase):
    def test_patch_frame(self):
        import run as R
        good = np.zeros(100)
        self.assertTrue(R.patch_frame_stats(good)['PASS'])
        self.assertFalse(R.patch_frame_stats(np.zeros(19))['PASS'])
        self.assertFalse(R.patch_frame_stats(np.linspace(-0.09, 0.09, 100))['PASS'])
        small = np.concatenate([np.zeros(95), np.full(5, 0.04)])
        self.assertTrue(R.patch_frame_stats(small)['PASS'])
        bad = np.concatenate([np.zeros(75), np.full(25, 0.06)])
        self.assertFalse(R.patch_frame_stats(bad)['PASS'])

    def test_pooled_spread(self):
        import run as R
        res = np.zeros(100)
        pts = np.column_stack([np.linspace(0, 0.35, 100), np.linspace(0, 0.35, 100)])
        self.assertTrue(R.pooled_patch_stats(res, pts)['PASS'])
        flat = np.column_stack([np.linspace(0, 0.05, 100), np.linspace(0, 0.05, 100)])
        self.assertFalse(R.pooled_patch_stats(res, flat)['PASS'])

    def test_online_state(self):
        import run as R
        self.assertEqual(R.online_state(192, 270, True), 'RAW')
        self.assertEqual(R.online_state(193, 270, True), 'CANDIDATE_PLANE_PREVIEW')
        self.assertEqual(R.online_state(270, 270, True), 'CANDIDATE_PLANE_PREVIEW')
        self.assertEqual(R.online_state(271, 270, True), 'GEOMETRY_VALIDATED_LOCAL')
        self.assertEqual(R.online_state(271, 270, False), 'CANDIDATE_PLANE_PREVIEW')


class Constants(unittest.TestCase):
    def test_registered_values(self):
        self.assertEqual(X.valid_xyz(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]])).tolist(), [True, False])
        self.assertLess(np.linalg.norm(REF - np.dot(REF, X.build(N, D, REF, 'C', {}, {}, 'x')['R'][2])
                                       * np.asarray(X.build(N, D, REF, 'C', {}, {}, 'x')['R'][2])), 1.0)


if __name__ == '__main__':
    unittest.main()
