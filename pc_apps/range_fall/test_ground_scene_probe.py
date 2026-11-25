from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import ground_scene_probe as capture
import ground_scene_analysis as analysis


class GroundSceneDiagnosticTests(unittest.TestCase):
    def test_capture_frame_budget_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            for count in (0, 27, 129):
                with self.assertRaisesRegex(ValueError, 'between 28 and 128'):
                    capture.capture('unused', 'unused', Path(directory)/'unused', 'unused', count)

    def test_both_entry_points_reject_protected_output_before_network_or_analysis(self):
        for folder in ('data/diagnostic', 'captures/diagnostic'):
            with self.assertRaisesRegex(ValueError, 'outside data'):
                capture.capture('unused', 'unused', capture.ROOT/folder, 'unused')
            with self.assertRaisesRegex(ValueError, 'outside data'):
                analysis.analyze(Path('unused'), Path('unused'), capture.ROOT/folder)

    def test_archive_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'clouds.npz').write_bytes(b'tampered')
            (root/'capture.json').write_text(json.dumps(dict(archive_sha256='0'*64)), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'archive checksum mismatch'):
                analysis.analyze(root,Path('unused'),root/'analysis')

    def test_camera_eof_retains_complete_jpeg_and_records_failure(self):
        output=BytesIO()
        Image.new('RGB',(3,3),'red').save(output,format='JPEG')
        payload=output.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(capture.urllib.request,'urlopen',return_value=BytesIO(payload)):
                result=capture.capture_camera('unused',Path(directory))
            self.assertEqual(len(result['images']),1)
            self.assertIn('stream ended',result['error'])
            self.assertEqual((Path(directory)/'usb_00.jpg').read_bytes(),payload)

    @staticmethod
    def points(raised=False):
        rng=np.random.RandomState(19)
        centers=np.array([[0,0],[1,0],[0,1],[1,1]],dtype=float)
        points=np.concatenate([np.column_stack((center+rng.uniform(-.12,.12,(30,2)),
            rng.normal(0,.002,30)+(0.30 if raised and i==3 else 0))) for i,center in enumerate(centers)])
        return points,np.repeat(np.arange(1,5),30)

    def test_candidate_remains_an_original_three_point_hypothesis(self):
        points,codes=self.points()
        ranked,feasible=analysis.candidate_scan(points,codes)
        self.assertTrue(feasible)
        chosen=ranked[feasible[0]]
        distance=points[chosen['sample_rows']]@np.array(chosen['normal'])+chosen['offset']
        np.testing.assert_allclose(distance,0,atol=1e-12)
        self.assertTrue(chosen['fit_regions_pass'])

    def test_incompatible_region_does_not_gain_a_candidate(self):
        points,codes=self.points(raised=True)
        _,feasible=analysis.candidate_scan(points,codes)
        self.assertEqual(feasible,[])

    def test_fit_candidate_does_not_bypass_independent_holdout_failure(self):
        points,codes=self.points()
        ranked,feasible=analysis.candidate_scan(points,codes)
        chosen=ranked[feasible[0]]
        held_points=points+np.array([0,0,.4])
        original=analysis.quality.ESTIMATORS
        with patch.object(analysis.quality,'ESTIMATORS',dict(original,ransac=lambda p:
                (np.array(chosen['normal']),chosen['offset']))):
            report=analysis.quality.compare(points,codes,[dict(ordinal=25,points=held_points,regions=codes)],np.array([0,0,1]))
        self.assertEqual(report['consensus'],'NO_RECOMMENDATION')
        self.assertIn('GL_HOLDOUT_QUALITY',report['estimators']['ransac']['reject_reasons'])

    def test_full_shadow_restores_estimators_on_failure(self):
        original=analysis.quality.ESTIMATORS
        original_compare=analysis.site.compare
        audit=dict(first_fit_feasible_rank=0,hypotheses=[dict(normal=[0,0,1],offset=1)])
        with patch.object(analysis.site,'fit_site',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                analysis.full_shadow([],[],dict(binding={},source={}),audit)
        self.assertIs(analysis.quality.ESTIMATORS,original)
        self.assertIs(analysis.site.compare,original_compare)


if __name__ == '__main__':
    unittest.main()
