"""Regression checks for raw depth decoding/provenance and measurement continuity."""
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from fall_geometry import FallGeometryRuntime, frame_geometry
from fall_candidate_runtime import file_sha256
from prepare_fall_events import prepare
from urfall_raw_depth import decode_png, load_pinhole, median_reference, DepthTarget
from evaluate_urfall_raw import evaluate


CAMERA = dict(width=4, height=4, fx=2., fy=2., cx=1.5, cy=1.5,
              schema='urfall_pinhole_v1', camera='cam0', status='nominal_diagnostic', physical_verified=False)


def png(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format='PNG')
    return stream.getvalue()


def measurement(height, upright=False, low=False, middle=False):
    return dict(valid=True, centroid_height_m=height, upright=upright, low=low, middle=middle)


class DecodeTest(unittest.TestCase):
    def test_real_units_pixel_mapping_and_holes(self):
        image = np.full((4, 4), 65535, dtype=np.uint16); image[0, 0] = 0
        points, pixels, depths = decode_png(png(image), 6., CAMERA, stride=2)
        self.assertEqual(pixels.tolist(), [0, 2, 8, 10])
        self.assertEqual(depths[0, 0], 0.)
        np.testing.assert_allclose(points[3], [1.5, 6., -1.5])
        _, _, adl_depths = decode_png(png(image), 7., CAMERA, stride=2)
        self.assertEqual(adl_depths[1, 1], 7.)
        u = CAMERA['fx']*points[3, 0]/points[3, 1] + CAMERA['cx']
        v = CAMERA['cy'] - CAMERA['fy']*points[3, 2]/points[3, 1]
        self.assertEqual(int(v)*4+int(u), pixels[3])

    def test_bad_encoding_shape_and_stride_rejected(self):
        with self.assertRaises(ValueError):
            decode_png(png(np.ones((4, 4), dtype=np.uint8)), 6., CAMERA)
        with self.assertRaises(ValueError):
            decode_png(png(np.ones((5, 4), dtype=np.uint16)), 6., CAMERA)
        with self.assertRaises(ValueError):
            decode_png(png(np.ones((4, 4), dtype=np.uint16)), 6., CAMERA, stride=0)

    def test_calibration_requires_explicit_unverified_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'camera.json'
            path.write_text(json.dumps(CAMERA), encoding='utf-8')
            self.assertEqual(load_pinhole(path)['fx'], 2.)
            for changes in (dict(physical_verified=True), dict(fx=0.), dict(cx=-1.), dict(width=True)):
                path.write_text(json.dumps(dict(CAMERA, **changes)), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_pinhole(path)

    def test_background_keeps_missing_pixels_and_only_consumes_given_prefix(self):
        prefix = [np.array([[0., 1.], [2., 4.]]), np.array([[0., 3.], [2., 5.]])]
        before = median_reference(prefix)
        np.testing.assert_array_equal(before, [[0., 1.], [2., 4.]])
        prefix.append(np.full((2, 2), 100.))
        np.testing.assert_array_equal(before, median_reference(prefix[:2]))

    def test_empty_corpus_retains_all_expected_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'DOWNLOAD.json').write_text('[]',encoding='utf-8')
            (root/'urfall-cam0-falls.csv').write_text('',encoding='utf-8')
            (root/'urfall-cam0-adls.csv').write_text('',encoding='utf-8')
            calibration=root/'camera.json'
            calibration.write_text(json.dumps(CAMERA),encoding='utf-8')
            result=evaluate(root,root/'pending',calibration,root/'report')
            self.assertEqual(result['completed_sequences'],0)
            self.assertEqual(len(result['results']),70)
            self.assertEqual(result['failure_counts'],{'INPUT_NOT_READY_WITHIN_WAIT':70})
            with self.assertRaises(ValueError):
                evaluate(root,root,calibration,root/'bad',wait_seconds=float('nan'))


class ContinuityTest(unittest.TestCase):
    def test_ambiguous_axis_preserves_measured_height_and_anchor(self):
        grid = np.stack(np.meshgrid(*([[-.2, 0., .2]]*3)), axis=-1).reshape(-1, 3)
        grid[:, 2] += .6
        evidence = frame_geometry(grid, [0, 0, 1], 0.)
        self.assertTrue(evidence['valid'])
        self.assertFalse(evidence['axis_valid'])
        self.assertIsNone(evidence['inclination_deg'])
        self.assertAlmostEqual(evidence['centroid_height_m'], .6)
        runtime = FallGeometryRuntime([0, 0, 1], 0.)
        runtime.push(None, 0., 'p', 'g', 'c', measurements=measurement(1.1, upright=True))
        result = runtime.push(grid, .1, 'p', 'g', 'c')
        self.assertEqual(result['state'], 'orientation_unknown')
        self.assertAlmostEqual(result['height_anchor_m'], 1.1)
        self.assertIsNotNone(result['evidence']['vertical_velocity_m_s'])

    def test_vertical_descent_does_not_overwrite_recent_high_reference(self):
        runtime = FallGeometryRuntime()
        for t, h in ((0., 1.1), (.1, .95), (.2, .8), (.3, .65)):
            runtime.push(None, t, 'p', 'g', 'c', measurements=measurement(h, upright=True))
        runtime.push(None, .4, 'p', 'g', 'c', measurements=measurement(.6, middle=True))
        runtime.push(None, .5, 'p', 'g', 'c', measurements=measurement(.5, low=True))
        result = runtime.push(None, .8, 'p', 'g', 'c', measurements=measurement(.5, low=True))
        self.assertIsNotNone(result['new_event'])
        self.assertEqual(result['height_anchor_m'], 1.1)

    def test_real_intermediate_height_can_support_process_without_an_angle(self):
        grid=np.stack(np.meshgrid(*([[-.2,0.,.2]]*3)),axis=-1).reshape(-1,3)
        grid[:,2]+=.7
        runtime=FallGeometryRuntime([0,0,1],0.)
        runtime.push(None,0.,'p','g','c',measurements=measurement(1.1,upright=True))
        runtime.push(grid,.1,'p','g','c')
        for t in (.2,.5):
            result=runtime.push(None,t,'p','g','c',measurements=measurement(.4,low=True))
        self.assertIsNotNone(result['new_event'])
        self.assertEqual(result['descent_process_basis'],'measured_intermediate_height')

    def test_endpoint_noise_is_not_an_invented_intermediate_height(self):
        runtime=FallGeometryRuntime()
        for t,h in ((0.,1.1),(.1,1.095),(.2,1.105)):
            runtime.push(None,t,'p','g','c',measurements=measurement(h,upright=True))
        for t in (.3,.6,.9):
            result=runtime.push(None,t,'p','g','c',measurements=measurement(.4,low=True))
            self.assertIsNone(result['new_event'])
        self.assertIsNone(result['descent_process_basis'])

    def test_masked_orientation_preserves_only_measured_low_height_hold(self):
        grid=np.stack(np.meshgrid(*([[-.1,0.,.1]]*3)),axis=-1).reshape(-1,3)
        grid[:,2]+=.4
        for gap,raises_height in ((False,False),(True,False),(False,True)):
            runtime=FallGeometryRuntime([0,0,1],0.)
            runtime.push(None,0.,'p','g','c',measurements=measurement(1.1,upright=True))
            runtime.push(None,.1,'p','g','c',measurements=measurement(.7,middle=True))
            runtime.push(None,.2,'p','g','c',measurements=measurement(.4,low=True))
            runtime.push(grid+([0,0,.5] if raises_height else [0,0,0]),.3,'p','g','c',observed=not gap)
            result=runtime.push(grid,.5,'p','g','c')
            self.assertEqual(result['new_event'] is not None,not gap and not raises_height)
            self.assertIsNone(result['evidence']['inclination_deg'])

    def test_old_reference_expires_and_real_gap_still_breaks_descent(self):
        runtime = FallGeometryRuntime()
        for i in range(26):
            runtime.push(None, i/10, 'p', 'g', 'c', measurements=measurement(1.1 if i == 0 else .65, upright=True))
        runtime.push(None, 2.6, 'p', 'g', 'c', measurements=measurement(.6, middle=True))
        for t in (2.7, 3.0):
            result = runtime.push(None, t, 'p', 'g', 'c', measurements=measurement(.5, low=True))
        self.assertIsNone(result['new_event'])
        self.assertEqual(result['height_anchor_m'], .65)

    def test_cache_masks_angle_without_breaking_height_segment(self):
        grid = np.stack(np.meshgrid(*([[-.2, 0., .2]]*3)), axis=-1).reshape(-1, 3)
        grid[:, 2] += .6
        runtime = FallGeometryRuntime([0, 0, 1], 0.)
        first = runtime.push(None, 0., 'p', 'g', 'c', measurements=measurement(1.1, upright=True))
        ambiguous = runtime.push(grid, .1, 'p', 'g', 'c')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root/'frames.jsonl'
            frames.write_text('\n'.join(json.dumps(dict(frame=i,timestamp_s=i/10,
                geometry=value,binding=['p','g','c'])) for i,value in enumerate((first,ambiguous))),encoding='utf-8')
            (root/'SUMMARY.json').write_text(json.dumps(dict(session='fixture',
                frame_schema='fall_geometry_frames_v1',frames_sha256=file_sha256(frames),
                runs=[dict(frames=2)])),encoding='utf-8')
            annotation = root/'annotation.json'
            annotation.write_text(json.dumps(dict(schema='fall_events_v1',session='fixture',
                subject='synthetic',duration_s=1.,clock=dict(offset_s=0.,uncertainty_s=0.),
                events=[])),encoding='utf-8')
            result = prepare(frames,annotation,root/'cache')
            with np.load(root/'cache/frames.npz',allow_pickle=False) as cache:
                self.assertTrue(cache['feature_mask'][1,0])
                self.assertFalse(cache['feature_mask'][1,1])
                self.assertEqual(cache['segment_index'].tolist(),[0,0])
            self.assertIn('fall_annotation.py',result['code_sha256'])

    def test_reacquisition_has_new_generation(self):
        z = np.linspace(0., 1.6, 60)
        points = np.column_stack((z*0., z*0.+2., z))
        pixels = np.arange(60)
        target = DepthTarget()
        rows, status, _ = target.select(points, pixels, z, 0.)
        self.assertEqual(status, 'measured_component')
        self.assertEqual(len(rows), 60)
        self.assertEqual(target.generation, 1)
        target.select(points, pixels, z, 1.)
        self.assertEqual(target.generation, 2)


if __name__ == '__main__':
    unittest.main()
