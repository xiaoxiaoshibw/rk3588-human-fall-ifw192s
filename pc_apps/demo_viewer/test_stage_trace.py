import hashlib
import unittest
from types import SimpleNamespace
import numpy as np
from stage_trace import trace_frame


class TraceTests(unittest.TestCase):
    def test_stage_partition_and_source_rows(self):
        rows = np.arange(9).reshape(3, 3)
        frame = SimpleNamespace(valid=np.ones((3, 3), bool), source_rows=rows,
                                range_m=np.ones((3, 3)), grid=SimpleNamespace(shape=(3, 3)),
                                xyz=np.column_stack((rows.ravel() * .01, np.zeros(9), np.ones(9))),
                                rejected={'duplicate_rows': np.array([9])})
        class Background:
            known = np.ones((3, 3), bool)
            delta_m = .3
            def foreground(self, frame):
                mask = np.zeros((3, 3), bool)
                mask[0, :2] = True
                return {'mask': mask}
        record = dict(target_source_rows=[0, 1], target_track_id='A', tracks=[])
        components = [dict(component_id=0, source_rows=np.array([0, 1]), retained=False)]
        trace = trace_frame(frame, Background(), record, components, np.eye(3), 0, [], [])
        self.assertEqual(trace['stages']['background_rejected']['count'], 7)
        self.assertEqual(trace['stages']['foreground']['count'], 2)
        self.assertEqual(trace['components'][0]['target_overlap'], 2)
        self.assertEqual(trace['target']['sha256'], hashlib.sha256(np.array([0, 1], dtype='<i8').tobytes()).hexdigest())
        self.assertEqual(trace['semantic'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
