"""Protocol v2 contract checks; oracle picks are explicitly not blind labels."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_gt_v2 as tool


class V2Tests(unittest.TestCase):
    def test_centroid_perspective_and_density(self):
        cam = tool.v1.default_camera()
        pts = np.array([[3., -.6, .8], [8., 1., 1.7], [8., 1., 1.7]])
        u, v, _ = tool.v1.project(pts, cam)
        expected = [float(u.mean()), float(v.mean())]
        np.testing.assert_allclose(tool.projected_centroid(pts, cam), expected)
        old_u, old_v, _ = tool.v1.project(pts.mean(axis=0)[None, :], cam)
        self.assertGreater(math.hypot(old_u[0] - expected[0], old_v[0] - expected[1]), 1)

    def test_centroid_rejects_invalid_and_filters_visibility(self):
        cam = tool.v1.default_camera()
        valid = np.array([[5., 0., 1.]])
        all_pts = np.vstack([valid, [np.nan, 0, 0], [-5, 0, 0], [5, 100, 1]])
        self.assertEqual(tool.projected_centroid(all_pts, cam), tool.projected_centroid(valid, cam))
        for bad in (np.empty((0, 3)), np.zeros((2, 2)), np.array([[-1., 0., 0.]])):
            with self.assertRaises(ValueError):
                tool.projected_centroid(bad, cam)

    def test_range_edges(self):
        self.assertEqual([tool.range_bin(x) for x in (3.9, 4., 5.5, 7., 8.5, float('nan'))],
                         [None, 0, 1, 2, None, None])

    def test_suite_balance_and_determinism(self):
        a, b = tool.build_suite(20261019), tool.build_suite(20261019)
        self.assertEqual(len(a), 24)
        self.assertEqual(sum(t['has_person'] for _, t in a), 18)
        self.assertEqual(sum(t.get('adjacent', False) for _, t in a), 6)
        for i in range(3):
            self.assertEqual(sum(t['has_person'] and tool.range_bin(t['range_m']) == i for _, t in a), 6)
        for (points, truth), (other, other_truth) in zip(a, b):
            np.testing.assert_array_equal(points, other)
            self.assertEqual(truth, other_truth)

    def test_render_neutral_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'a.png', Path(directory) / 'b.png'
            pts, _ = tool.build_suite(20261019)[0]
            tool.render(pts, tool.v1.default_camera(), a)
            tool.render(pts, tool.v1.default_camera(), b)
            self.assertEqual(tool.v1.sha256_file(a), tool.v1.sha256_file(b))

    def test_pick_validation(self):
        cam = tool.v1.default_camera()
        good = {'picks': [{'case': 'a', 'u': 5, 'v': 6}, {'case': 'b', 'u': None, 'v': None}]}
        self.assertEqual(len(tool.validate_picks(good, {'a', 'b'}, cam)), 2)
        for u, v in ((None, 5), (5, None), (float('nan'), 5), (5, float('inf')),
                     (True, 5), ('5', 5), (-1, 5), (1280, 5), (5, 720)):
            doc = copy.deepcopy(good)
            doc['picks'][0].update(u=u, v=v)
            with self.assertRaises(ValueError):
                tool.validate_picks(doc, {'a', 'b'}, cam)
        for entries in (good['picks'][:1], good['picks'] * 2,
                        [{'case': 'x', 'u': None, 'v': None}], [{'case': 'a', 'u': None}]):
            with self.assertRaises(ValueError):
                tool.validate_picks({'picks': entries}, {'a', 'b'}, cam)

    def test_output_protection_and_holdout(self):
        root = Path(tool.__file__).resolve().parents[2]
        for path in (root / 'data' / 'never_create_v2', root / 'captures' / 'never_create_v2'):
            with self.assertRaises(ValueError):
                tool.fresh_output(path)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                tool.render_suite(Path(directory) / 'holdout', 20261020)
            self.assertFalse((Path(directory) / 'holdout').exists())
            with self.assertRaises(FileExistsError):
                tool.fresh_output(directory)

    def test_score_roundtrip_noise_counts_and_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            suite = d / 'suite'
            tool.render_suite(suite, 20261019)
            truth = tool.read(suite / 'truth/truth.json')
            doc = {'kind': 'oracle', 'annotator': {'model_id': 'SYNTHETIC_ORACLE'},
                   'suite_manifest_sha256': tool.v1.sha256_file(suite / 'MANIFEST.json'),
                   'picks': [{'case': c['case'],
                              'u': c['truth_px'][0] if c['has_person'] else None,
                              'v': c['truth_px'][1] if c['has_person'] else None} for c in truth['cases']]}
            picks = d / 'oracle.json'
            tool.write(picks, doc)
            tool.score_suite(suite, picks, d / 'oracle')
            report = tool.read(d / 'oracle/SELFCHECK.json')
            self.assertEqual((report['tp'], report['fn'], report['fp'], report['tn']), (18, 0, 0, 6))
            self.assertLess(report['px_err']['max'], 1e-9)
            self.assertFalse(report['eligible_for_gt'])
            for p in doc['picks']:
                if p['u'] is not None:
                    p['u'] += 5
            people = [p for p in doc['picks'] if p['u'] is not None]
            people[0].update(u=None, v=None)
            empty = next(p for p in doc['picks'] if p['u'] is None and p is not people[0])
            empty.update(u=640, v=360)
            doc['kind'] = 'injected_contract'
            noisy = d / 'noisy.json'
            tool.write(noisy, doc)
            tool.score_suite(suite, noisy, d / 'noisy')
            report = tool.read(d / 'noisy/SELFCHECK.json')
            self.assertEqual((report['tp'], report['fn'], report['fp'], report['tn']), (17, 1, 1, 5))
            self.assertAlmostEqual(report['px_err']['max'], 5)
            missing = copy.deepcopy(doc)
            for p in missing['picks']:
                p.update(u=None, v=None)
            all_missing = d / 'all_fn.json'
            tool.write(all_missing, missing)
            tool.score_suite(suite, all_missing, d / 'all_fn')
            report = tool.read(d / 'all_fn/SELFCHECK.json')
            self.assertEqual((report['tp'], report['fn'], report['fp'], report['tn']), (0, 18, 0, 6))
            self.assertIsNone(report['px_err'])
            self.assertTrue(all(b['n_tp'] == 0 and b['px'] is None and b['lateral_m'] is None
                                for b in report['by_range']))
            self.assertTrue(all(b['n_person'] == 6 for b in report['by_range']))
            doc['suite_manifest_sha256'] = 'wrong'
            wrong = d / 'wrong.json'
            tool.write(wrong, doc)
            with self.assertRaises(ValueError):
                tool.score_suite(suite, wrong, d / 'wrong')
            self.assertFalse((d / 'wrong').exists())
            (suite / 'renders/case_000.png').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                tool.verify_suite(suite)


if __name__ == '__main__':
    unittest.main(verbosity=2)
