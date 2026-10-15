import unittest
from pathlib import Path
import numpy as np
import yaml
from scipy.spatial.transform import Rotation
from scene_change import FrozenSurfaces


class SceneChangeTest(unittest.TestCase):
    def test_vibrating_furniture_is_background_new_body_is_not(self):
        cfg = yaml.safe_load(Path(__file__).with_name('config_scene_change.yaml').read_text(encoding='utf8'))
        grid = np.linspace(-1., 1., 55)
        u, v = np.meshgrid(grid, grid)
        planes = np.concatenate([np.column_stack((u.ravel(), v.ravel(), np.zeros(u.size))),
            np.column_stack((u.ravel(), np.full(u.size, 1.5), v.ravel()+1.)),
            np.column_stack((np.full(u.size, 1.5), u.ravel(), v.ravel()+1.))])
        model = FrozenSurfaces(planes, .055, cfg)
        body = np.array([[.3, .3, .13], [.3, .3, .4], [.3, .3, .8]])
        original = np.concatenate((planes, body))
        rot = Rotation.from_rotvec([.003, -.004, .002]).as_matrix()
        vibrating = original @ rot.T + [.012, -.01, .008]
        corrected, evidence = model.compensate(vibrating, {'translation_m': .05, 'rotation_rad': .02})
        self.assertEqual(evidence['status'], 'COMPENSATED')
        self.assertLess(np.max(np.linalg.norm(corrected-original, axis=1)), .002)
        fg, bg, _, _ = model.split(corrected, np.ones(len(corrected), bool))
        np.testing.assert_array_equal(fg, np.arange(len(planes), len(original)))
        self.assertTrue(bg[:len(planes)].all())
        near_edge = np.array([[0., 0., .05], [0., 0., .08], [.3, .3, .4]])
        shifted = near_edge + [0., 0., .02]
        fg, bg, _, _, ambiguous = model.split_pose_hypotheses(near_edge, shifted, np.ones(3, bool))
        np.testing.assert_array_equal(fg, [1, 2])
        self.assertTrue(bg[0] and ambiguous[0])
        # Reject correction rather than erasing points when observed pose exceeds calibration.
        rejected, diag = model.compensate(vibrating, {'translation_m': .001, 'rotation_rad': .001})
        self.assertEqual(diag['status'], 'OUTSIDE_EMPTY_SCENE_VIBRATION_ENVELOPE')
        np.testing.assert_array_equal(rejected, vibrating)
        single = FrozenSurfaces(planes[:u.size], .055, cfg)
        _, diag = single.compensate(vibrating[:u.size])
        self.assertEqual(diag['status'], 'DEGENERATE_STATIC_ANCHORS')
        fg, _, _, _ = model.split(np.array([[np.nan, 0., 0.], [0., 0., 0.]]), [True, True])
        self.assertEqual(len(fg), 0)
        empty = np.empty((0, 3))
        self.assertEqual(model.compensate(empty)[1]['status'], 'INSUFFICIENT_STATIC_ANCHORS')
        self.assertEqual(len(model.split(empty, np.empty(0, bool))[0]), 0)
        with self.assertRaises(ValueError): model.split(body, [True])


if __name__ == '__main__': unittest.main()
