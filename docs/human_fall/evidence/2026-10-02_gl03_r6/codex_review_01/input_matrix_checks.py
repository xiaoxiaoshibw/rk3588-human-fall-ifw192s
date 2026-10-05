"""Independent GL03 v1 classification/qualification matrix."""
import copy
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'src/human_fall_detection'),str(ROOT/'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref

class InputMatrix(unittest.TestCase):
    def snap(self,record):
        return ref.ReferenceBinding().snapshot(None,record)
    def unavailable(self,record):
        try:
            snap=self.snap(record)
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']))
    def summary(self):
        return dict(calibration_id='legacy',frames=dict(lidar='innolidar',reference='fixture_reference'),
                    transforms=dict(T_reference_lidar=ref.transform()))
    def test_G03_full_blocks_cannot_downgrade(self):
        for key in ('units','created_at_utc','rotations','verification','status','input','ground','ground_derived','sensor_height_m'):
            for kind in ('absent',None):
                with self.subTest(key=key,kind=kind):
                    record=self.summary();record[key]=None
                    if kind is None:record['kind']=None
                    self.unavailable(record)
    def test_G07_minimal_summaries_and_plain_extensions_remain_supported(self):
        for version in ('absent',1):
            for kind in ('absent',None):
                record=self.summary();record['unrelated_extension']={'note':'ignored'}
                if version==1:record['schema_version']=1
                if kind is None:record['kind']=None
                self.assertIsNotNone(self.snap(record)['candidates'][0]['center_reference_m'])
    def test_G03_explicit_summary_versions_refused(self):
        for version in (99,True,1.,None,'1'):
            with self.subTest(version=version):
                record=self.summary();record['schema_version']=version;self.unavailable(record)
    def test_G03_full_parent_source_label_must_be_a_frame_name(self):
        for value in (42,True,['innolidar']):
            with self.subTest(value=value):
                record=ref.calibration(ref.transform());record['frames']['lidar']=value
                self.unavailable(record)
    def test_G03_full_parent_optional_reference_label_cannot_be_a_container(self):
        for value in ([],{}):
            with self.subTest(value=value):
                record=ref.calibration(ref.transform());record['frames']['reference']=value
                self.unavailable(record)
    def test_G03_damaged_summary_container_is_rejected_or_unavailable(self):
        for key in ('frames','transforms'):
            with self.subTest(key=key):
                record=self.summary();record[key]='damaged'
                self.unavailable(record)
    def test_G03_bad_canonical_record_cannot_enable_standalone_fallback(self):
        record=self.summary();record['transforms']['T_reference_lidar']='damaged'
        try:
            snap=ref.ReferenceBinding().snapshot(ref.transform(),record)
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']))

if __name__=='__main__':unittest.main(verbosity=2)
