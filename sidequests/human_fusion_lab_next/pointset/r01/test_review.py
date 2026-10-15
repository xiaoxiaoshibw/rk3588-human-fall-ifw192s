import unittest
from copy import deepcopy

import numpy as np
import torch

from server import validate_review
from train_parts import PointPartNet


class ReviewChecks(unittest.TestCase):
    def test_scope_indices_and_hash_binding(self):
        obj = {'id': 'c0', 'kind': 'AUTOMATIC_CANDIDATE', 'source_indices': [1, 2]}
        frame = {'session_id': 'SYNTHETIC', 'frame_index': 0, 'source_frame': {'count_points': 5}, 'reference': [], 'full_3d': [], 'roi_3d': [obj], 'full_2d': []}
        cat = {'sessions': [{'session_id': 'SYNTHETIC', 'source_sha256': {'meta': 'm', 'points': 'p'}}]}
        row = {'schema_version': 'pointset-annotation/1', 'session_id': 'SYNTHETIC', 'frame_index': 0,
               'source_sha256': {'meta': 'm', 'points': 'p'}, 'reviewer': 'SYNTHETIC_TEST_ONLY', 'provenance': 'HUMAN_REVIEW',
               'part_class': 'TORSO', 'source_indices': [1], 'object_id': 'c0', 'object_scope': 'roi_3d', 'object_kind': 'AUTOMATIC_CANDIDATE'}
        self.assertEqual(validate_review(row, cat, frame), row)
        for key, value in [('object_scope', 'full_3d'), ('source_indices', [4]), ('reviewer', ''), ('source_sha256', {}), ('part_class', 'fake')]:
            bad = deepcopy(row)
            bad[key] = value
            with self.assertRaises(ValueError):
                validate_review(bad, cat, frame)

    def test_pointpart_permutation_equivariance(self):
        torch.manual_seed(42)
        torch.set_num_threads(2)
        net = PointPartNet().eval()
        points = torch.randn(1, 3, 64)
        permutation = torch.randperm(64)
        with torch.no_grad():
            a = net(points).numpy()
            b = net(points[:, :, permutation]).numpy()
        np.testing.assert_allclose(a[:, :, permutation], b, atol=1e-6)


if __name__ == '__main__':
    unittest.main()
