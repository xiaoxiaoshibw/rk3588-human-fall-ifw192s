"""证据胶水直接回归；旧参考是代理，不是人体标签。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from test_range_frontend import scene
from replay_range_frontend import compare, percentiles, reference_rows
from core.range_contract import load_ground, reference_summary


class ContractTests(unittest.TestCase):
    def test_instrumentation_preserves_measurements_and_empty_lift(self):
        from core.range_components import label_components
        grid, raw, frame = scene(np.ones((5, 7)))
        timing = {}
        measured = grid.decode(raw, frame.binding, timings=timing)
        np.testing.assert_array_equal(measured.source_rows, frame.source_rows)
        np.testing.assert_array_equal(measured.range_m, frame.range_m)
        self.assertEqual(len(timing), 7)
        _, groups = label_components(frame, np.zeros(frame.grid.shape, dtype=bool), timings=timing)
        self.assertEqual(groups, [])
        self.assertEqual(timing['source_lift_ms'], 0)

    def test_torso_and_limbs_connected_sources(self):
        from core.range_components import label_components
        _, _, frame = scene(np.full((11, 11),2.0))
        mask=np.zeros(frame.grid.shape,dtype=bool)
        mask[2:8,4:7]=True
        mask[3,1:10]=True
        mask[7:11,3]=True
        mask[7:11,7]=True
        _, groups=label_components(frame,mask,min_points=1)
        self.assertEqual(len(groups),1)
        np.testing.assert_array_equal(groups[0]['source_rows'],np.sort(frame.source_rows[mask]))

    def test_split_and_empty_survival_denominators(self):
        _, _, frame = scene(np.ones((2, 4)))
        ref = dict(target_source_rows=[0, 1, 2, 3], track=dict(track_status='locked'))
        mask = np.zeros((2, 4), dtype=bool)
        mask.ravel()[[0, 1, 2, 4]] = True
        comps = [dict(component_id=0, source_rows=np.array([0,1,4]), retained=True),
                 dict(component_id=1, source_rows=np.array([2]), retained=False)]
        c = compare(frame, mask, comps, ref)
        self.assertEqual(c['kept_reference_points'], 3)
        self.assertAlmostEqual(c['reference_dispersion_fraction'], 1/3)
        self.assertEqual(c['removed_reference_rows'], [2,3])
        self.assertEqual(c['added_component_rows'], [4])
        self.assertEqual(c['union_reference_fraction'], .75)
        self.assertEqual(c['component_reference_jaccard'], .4)
        c = compare(frame, np.zeros_like(mask), [], ref)
        self.assertIsNone(c['reference_dispersion_fraction'])
        self.assertEqual(c['dispersion_reason'], 'no_surviving_reference_rows')
        self.assertEqual(c['union_reference_fraction'], 0)

    def test_prediction_and_occlusion_excluded(self):
        _, _, frame = scene(np.ones((2, 4)))
        for track in [dict(track_status='locked',position_predicted=True),dict(track_status='occluded')]:
            c = compare(frame, frame.valid, [], dict(target_source_rows=[0], track=track))
            self.assertFalse(c['reference_observed'])

    def test_reference_sha_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'SUMMARY.json').write_text(json.dumps(dict(meta_sha256='m',points_sha256='p')))
            meta = dict(frames=[dict(count_points=4)])
            (p/'target_frames.jsonl').write_text(json.dumps(dict(frame=0,target_source_rows=[0]))+'\n')
            self.assertEqual(len(reference_rows(p,meta,'m','p')),1)
            with self.assertRaisesRegex(ValueError,'different source bytes'):
                reference_rows(p,meta,'wrong','p')
            for rows in ([0,0],[True],[4]):
                (p/'target_frames.jsonl').write_text(json.dumps(dict(frame=0,target_source_rows=rows))+'\n')
                with self.assertRaises(ValueError):
                    reference_rows(p,meta,'m','p')

    def test_percentiles_and_summary_effective_n(self):
        p = percentiles([1,2,3,4,5])
        self.assertEqual(p['samples'],5)
        self.assertEqual(p['p50_ms'],3)
        self.assertAlmostEqual(p['p99_ms'],4.96)
        self.assertIsNone(percentiles([])['p95_ms'])
        with self.assertRaises(ValueError):
            percentiles([float('nan')])
        rows=[]
        for total in (1,9):
            rows.append(dict(reference_observed=True,reference_points=total,kept_reference_points=1,
                selected_intersection_points=1,union_reference_points=1,union_reference_fraction=1/total,
                reference_dispersion_fraction=0))
        summary=reference_summary(rows)
        self.assertEqual(summary['union_reference_fraction']['samples'],2)
        self.assertAlmostEqual(summary['union_reference_fraction']['median'],5/9)
        self.assertAlmostEqual(summary['aggregate']['weighted_union_coverage'],.2)
        self.assertEqual(summary['diagnostic_component_points']['samples'],0)
        self.assertIsNone(reference_summary([])['aggregate']['weighted_union_coverage'])

    def test_ground_same_frame_different_source_or_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            b=dict(session='s',meta_sha256='m',points_sha256='p',coordinate='RAW/innolidar',units='m',
                   grid_sha256='g',epoch='e',coordinate_transform='identity')
            raw=json.dumps(dict(sid='s',source_sha256=dict(meta='m',points='p'),from_frame='RAW/innolidar',
                                units='m',plane=dict(normal_source=[0,0,1],offset_source_m=1))).encode()
            (p/'transform.json').write_bytes(raw)
            g=dict(status='valid',frame='innolidar',binding=b,normal=[0,0,1],offset_m=1,
                   provenance=dict(source=str(p/'transform.json'),sha256=hashlib.sha256(raw).hexdigest()))
            (p/'ground.json').write_text(json.dumps(g))
            self.assertEqual(load_ground(p/'ground.json',b),g)
            with self.assertRaisesRegex(ValueError,'binding'):
                load_ground(p/'ground.json',dict(b,points_sha256='different'))
            (p/'transform.json').write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'SHA'):
                load_ground(p/'ground.json',b)


if __name__ == '__main__':
    unittest.main()
