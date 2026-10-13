"""固定数学反例与真实候选成员审计；不生成真人GT。"""
import unittest

import numpy as np

from server import estimate, get_frame, validate_request


def fixture():
    return np.array([[x, y, z] for z in np.linspace(0.12, 1.72, 45)
                     for x in [-0.16, -0.12, 0.12, 0.16] for y in [-0.03, 0.03]])


class PreviewChecks(unittest.TestCase):
    def assert_support(self, cloud, rows, nodes):
        members = dict(zip(rows, cloud))
        for node in nodes.values():
            if not node['valid']:
                self.assertIsNone(node['xyz'])
                self.assertEqual(node['support_rows'], [])
                continue
            self.assertTrue(set(node['support_rows']).issubset(members))
            self.assertEqual(node['support_n'], len(node['support_rows']))
            expected = np.median([members[r] for r in node['support_rows']], axis=0)
            np.testing.assert_allclose(node['xyz'], expected, atol=1e-6, rtol=0)

    def test_supported_regions_and_unsigned_lower_pair(self):
        cloud = fixture()
        rows = list(range(len(cloud)))
        nodes, _ = estimate(cloud, rows)
        self.assertTrue(all(n['valid'] for n in nodes.values()))
        self.assertEqual(nodes['TOP_REGION']['reason'], 'HEAD_OR_HAND_NOT_VERIFIED')
        self.assert_support(cloud, rows, nodes)

    def test_absence_invalid_and_broad_mixed_cloud(self):
        for cloud in [np.empty((0, 3)), np.zeros((8, 3)), np.full((60, 3), np.nan), fixture() * [20, 1, 1]]:
            nodes, _ = estimate(cloud, list(range(len(cloud))))
            self.assertTrue(all(not n['valid'] for n in nodes.values()))
        cloud = fixture()
        cloud[0] = [np.nan, 0, 1]
        nodes, _ = estimate(cloud, list(range(len(cloud))))
        self.assertTrue(all(0 not in n['support_rows'] for n in nodes.values()))

    def test_duplicate_rows_and_invalid_navigation(self):
        cloud = fixture()
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_MEMBER_ROWS'):
            estimate(cloud, [0] * len(cloud))
        for sid, fi in [('175429', 220), ('cap_20261010_175429', -1), ('cap_20261010_175429', 258)]:
            with self.assertRaises(ValueError):
                validate_request(sid, fi)

    def test_real_same_frame_support_without_gt_and_empty_cache_separation(self):
        near = get_frame('cap_20261010_175429', 220)
        self.assertTrue(near['human_annotation_consumed_as_input'])
        self.assertFalse(near['node_ground_truth_available'])
        self.assertEqual(near['frame'], 220)
        candidates = {c['id']: c for c in near['candidates']}
        self.assertGreater(sum(n['valid'] for n in candidates[near['default_candidate']]['nodes'].values()), 0)
        for c in near['candidates']:
            self.assert_support(c['points'], c['member_rows'], c['nodes'])
        # 倒放/切会话重新取该帧，节点不从近距帧补画。
        furniture = get_frame('cap_20261010_175227', 40)
        self.assertEqual(furniture['sid'], 'cap_20261010_175227')
        self.assertEqual(furniture['candidates'], [])
        self.assertEqual(get_frame('cap_20261010_175429', 220), near)
        machine = get_frame('cap_20261010_175429', 220, 'candidate')
        self.assertFalse(machine['ground_truth_used_by_estimator'])
        body = next(c for c in machine['candidates'] if c['id'] == 'a_220_2')
        self.assertTrue(all(not n['valid'] for n in body['nodes'].values()))
        with self.assertRaisesRegex(ValueError, 'INVALID_INPUT_MODE'):
            get_frame('cap_20261010_175429', 220, 'wrong')


if __name__ == '__main__':
    unittest.main()
