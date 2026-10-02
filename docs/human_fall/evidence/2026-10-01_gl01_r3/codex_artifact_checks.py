"""Independent checks for corrupt persisted constrained ground records."""
import copy
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
sys.path.insert(0, str(ROOT/'src/human_fall_detection/tests'))
from core.ground import fit_ground_plane_constrained, validate_constrained_ground
from test_gl01_constrained_ground import clean_scene


class ArtifactChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        points, up, fit, regions = clean_scene()
        cls.record = fit_ground_plane_constrained(points, frame='innolidar',
            up_axis=up, sensor_height_interval_m=[.5,1.6], fit_indices=fit,
            fit_frame_group='fit', validation_regions=regions)
        assert cls.record['status'] == 'valid'

    def check_rejected(self, mutate):
        damaged=copy.deepcopy(self.record)
        mutate(damaged)
        with self.assertRaises(ValueError):
            validate_constrained_ground(damaged)

    def test_loaded_fit_group_cannot_equal_validation_group(self):
        self.check_rejected(lambda g:g.update(fit_frame_group=g['validation_regions'][0]['frame_group']))

    def test_loaded_negative_residuals_and_impossible_support_rejected(self):
        for key,value in [('rms_m',-.01),('p95_m',-.01),('support_fraction',1.2),('rms_m',False)]:
            with self.subTest(key=key,value=value):
                self.check_rejected(lambda g:g['validation_regions'][0].update({key:value}))

    def test_loaded_height_must_match_declared_prior(self):
        self.check_rejected(lambda g:g.update(sensor_height_interval_m=[.5,.9]))

    def test_loaded_normal_must_match_declared_up_axis(self):
        self.check_rejected(lambda g:g.update(up_axis=[1.,0.,0.]))

    def test_loaded_fit_source_indices_must_be_valid(self):
        for index in (True, self.record['input_point_count']):
            with self.subTest(index=index):
                self.check_rejected(lambda g:g['fit_support_indices'].__setitem__(0,index))

    def test_loaded_budget_cannot_be_zero(self):
        self.check_rejected(lambda g:g.update(iterations=0))


if __name__=='__main__':
    unittest.main(verbosity=2)
