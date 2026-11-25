import json
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import service_replay as replay


class ServiceReplayTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.session=self.root/'data/sessions/cap_20261028_houdao'
        self.session.mkdir(parents=True)
        rows=np.zeros(8,dtype=replay.ROW_DTYPE)
        grid=replay.sc.load_grid()
        az=np.radians(grid.azimuth_deg[0,:8]);el=np.radians(grid.elevation_deg[0,:8])
        rows['x']=2*np.cos(el)*np.cos(az);rows['y']=2*np.cos(el)*np.sin(az);rows['z']=2*np.sin(el)
        self.meta=dict(sensor=dict(frame_id='innolidar'),frames=[dict(seq=i,stamp_sec=100,
            stamp_nanosec=i*100000000,offset_points=i*len(rows),count_points=len(rows)) for i in range(5)])
        (self.session/'meta.json').write_text(json.dumps(self.meta),encoding='utf8')
        (self.session/'points.bin').write_bytes(rows.tobytes()*5)
        self.root_patch=patch.object(replay,'ROOT',self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.directory.cleanup()

    def make_replay(self,**kwargs):
        return replay.ServiceReplay('houdao',output=self.root/'output',deterministic=True,**kwargs)

    def test_undeclared_action_recording_never_becomes_empty_background(self):
        run=self.make_replay()
        try:
            rows=[run.next() for _ in range(5)]
            self.assertIsNone(run.next())
            self.assertIsNone(run.engine.runtime)
            self.assertTrue(all(not r['pipeline']['declaredEmptyPrefix'] for r in rows))
            self.assertTrue(all(r['pipeline']['initialization']['ground']=='not_loaded' for r in rows))
            self.assertTrue(all(r['geometry'] is None and r['n']==0 and r['hm'] is None for r in rows))
            self.assertTrue(all(r['depth'].startswith('data:image/png;base64,') for r in rows))
        finally:run.close()

    def test_future_points_cannot_change_already_consumed_prefix(self):
        def prefix():
            run=self.make_replay()
            try:return [run.next(False)['wire_sha256'] for _ in range(2)]
            finally:run.close()
        before=prefix()
        path=self.session/'points.bin';raw=path.read_bytes();boundary=2*8*replay.ROW_DTYPE.itemsize
        path.write_bytes(raw[:boundary]+b'\0'*(len(raw)-boundary))
        self.assertEqual(prefix(),before)

    def test_actual_service_slot_overwrite_and_ttl_are_exercised(self):
        run=self.make_replay()
        try:
            first,_=run._message(0);second,_=run._message(1)
            run.service.submit(first);run.service.submit(second)
            run.service.process_latest()
            self.assertEqual(run.service.snapshot()['source']['seq'],1)
            self.assertEqual(run.service.snapshot()['health']['overwritten'],1)
            run.clock.advance(.6)
            stale=run.service.snapshot()
            self.assertIsNone(stale['source'])
            self.assertEqual(stale['target_source_rows'],[])
            self.assertEqual(stale['service']['confirmedEnabled'],False)
            self.assertGreater(stale['health']['invalidationRevision'],0)
        finally:run.close()

    def test_repeated_source_header_requires_rebind(self):
        run=self.make_replay()
        try:
            msg,_=run._message(0)
            for _ in range(2):
                run.service.submit(msg);run.service.process_latest()
            self.assertIn('source_rewound',run.engine.disabled)
            self.assertIsNone(run.service.snapshot()['source'])
        finally:run.close()

    def test_derived_output_cannot_target_source_data(self):
        with self.assertRaisesRegex(ValueError,'outside data'):
            replay.ServiceReplay('houdao',output=self.root/'data/forbidden',deterministic=True)

    def test_display_reads_service_hint_without_retiming_it(self):
        state=dict(source=dict(seq=50),target_source_rows=[1,2],fall_status='upright',
            local_range=dict(ground=dict(available=True),demoFallCandidate=dict(level=2,state='sustained',durationSec=3.75),
                             posture=dict(state='lying_candidate')))
        result=replay.activity(state)
        self.assertEqual(result['label'],'low_horizontal_sustained')
        self.assertEqual(result['low_duration_s'],3.75)
        self.assertFalse(result['confirmed'])
        state['source']=None
        self.assertEqual(replay.activity(state)['label'],'unknown')

    def test_display_uses_exact_service_preview_and_does_not_replace_missing(self):
        run=self.make_replay()
        try:
            row=run.next()
            raw=base64.b64decode(row['depth'].split(',',1)[1])
            state=run.service.snapshot()['local_range']
            self.assertEqual(base64.b64encode(raw).decode(),state['preview'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['pipeline']['previewSha256'])
            with patch.object(run.service,'process_preview',return_value=False):
                row=run.next()
            self.assertIsNone(row['depth'])
            self.assertIsNone(row['depth_box'])
            self.assertFalse(row['pipeline']['previewAvailable'])
        finally:run.close()

    def test_batch_rejects_protected_output_before_creating_it(self):
        import pseudo_live
        with patch.object(pseudo_live,'ROOT',self.root):
            for mode in ('service','historical'):
                for name in ('data','captures'):
                    output=self.root/name/('forbidden_'+mode)
                    with self.assertRaisesRegex(ValueError,'outside data'):
                        pseudo_live.batch(output,mode=mode)
                    self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
