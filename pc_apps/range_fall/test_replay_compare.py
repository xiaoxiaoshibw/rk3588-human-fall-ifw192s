"""已保存/已审计回放到同款页面；无拟合、设备或模型调用。"""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'tools'))
import replay_compare as view
import test_range_experiment as fixture


def write(path,value):path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')


class ReplayViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.RangeExperimentTests.setUpClass()

    def setUp(self):
        self.f=fixture.RangeExperimentTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.session=self.f.session; self.root=self.f.root
        self.audit=self.root/'audit';view.experiment.run(self.session,self.audit,self.f.replay)

    def build(self,name='view',**kwargs):
        return view.build(self.session,self.root/name,replay=self.f.replay,audit=self.audit,preview=False,**kwargs)

    def saved(self):
        saved=self.root/'saved';saved.mkdir();(saved/'data').mkdir()
        identity=view.read_json(self.f.replay/'SUMMARY.json')['source_binding']
        plane=dict(normal=[0,0,1],offset_m=1,binding=identity)
        rows=[]
        for i in range(4):
            rows.append(dict(i=i,t=i*.1,st='suspected' if i==2 else 'unknown',rs=['fixture'],
                tid='t' if i else None,n=2 if i else 0,hm=.2 if i else None,ht=.3 if i else None,
                sp=.6 if i else None,rt=None,vt=None,bb=[0,0,0,1,1,1] if i else None,
                c=[1,1] if i else None,cam=None,bl=None,bg=[0,0,0],tg=[0,0,0] if i else []))
        summary=dict(schema='session_compare_v1',session=self.session.name,source_binding=identity,
            source=dict(frames=4,camera_frames=0,duration_sec=.3,camera_sha256=None,camera_index_sha256=None),
            honesty=dict(non_causal_background=True,human_gt='UNKNOWN',fall_gt='UNKNOWN'),ground=plane,
            fall=dict(confirmed_enabled=False,events=[],states={'unknown':3,'suspected':1}),tracking={})
        write(saved/'SUMMARY.json',summary);write(saved/'GROUND.json',plane)
        (saved/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows)+';',encoding='utf-8')
        self.save_ledger(saved,rows)
        return saved,rows

    def save_ledger(self,saved,rows):
        (saved/'FRAMES.jsonl').write_text(''.join(json.dumps({k:v for k,v in row.items() if k not in ('bg','tg')})+'\n' for row in rows),encoding='utf-8')

    def test_audited_mode_no_fit_or_algorithm_update_and_unknown_height(self):
        with mock.patch.object(view.sc,'fit_ground',side_effect=AssertionError('no fitting')),\
             mock.patch.object(view.sc,'background_range',side_effect=AssertionError('no background')),\
             mock.patch.object(view.sc,'RangeTracker',side_effect=AssertionError('no tracker')):
            s=self.build()
        rows=view.js_records(self.root/'view/data/frames.js')
        self.assertEqual(s['input_inference_sha256'],view.read_json(self.f.replay/'SUMMARY.json')['inference_output_sha256'])
        self.assertTrue(all(r['hm'] is None for r in rows))
        self.assertFalse(s['honesty']['non_causal_background'])
        self.assertEqual(rows[-1]['n'],400)
        self.assertEqual(rows[0]['tg'],[]);self.assertIsNone(rows[0]['bb'])
        self.assertIn('地面不可用',(self.root/'view/index.html').read_text(encoding='utf-8'))
        self.assertNotIn('@@',(self.root/'view/index.html').read_text(encoding='utf-8'))

    def test_saved_view_preserves_points_state_without_fitting(self):
        saved,rows=self.saved()
        with mock.patch.object(view.sc,'fit_ground',side_effect=AssertionError('no fitting')):
            s=view.build(self.session,self.root/'view',saved=saved,preview=False)
        out=view.js_records(self.root/'view/data/frames.js')
        for old,new in zip(rows,out):
            for key in ('bg','tg','st','hm','bb','n'):self.assertEqual(old[key],new[key])
        self.assertTrue(s['honesty']['non_causal_background'])
        self.assertIn('UNAVAILABLE',s['row_provenance'])

    def test_saved_display_ledger_mismatch_rejected(self):
        saved,rows=self.saved();rows[-1]['hm']=999
        (saved/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows)+';',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'display/ledger'):view.build(self.session,self.root/'bad',saved=saved,preview=False)

    def test_saved_wrong_session_sha_rejected(self):
        saved,_=self.saved();s=view.read_json(saved/'SUMMARY.json');s['source_binding']['points_sha256']='0'*64;write(saved/'SUMMARY.json',s)
        with self.assertRaisesRegex(ValueError,'source/calibration'):view.build(self.session,self.root/'bad',saved=saved,preview=False)

    def test_saved_frozen_sha_cannot_be_bypassed_by_changing_both_ledgers(self):
        saved,rows=self.saved()
        write(saved/'CHECKS.json',dict(artifacts={n:view.file_binding(saved/n) for n in ['SUMMARY.json','GROUND.json','FRAMES.jsonl','data/frames.js']}))
        rows[2]['hm']=.1;self.save_ledger(saved,rows)
        (saved/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows)+';',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'artifact SHA mismatch'):view.build(self.session,self.root/'bad',saved=saved,preview=False)

    def test_unmeasured_features_cannot_leak_to_display(self):
        saved,rows=self.saved();rows[0]['sp']=.8
        self.save_ledger(saved,rows);(saved/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows)+';',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'unmeasured features'):view.build(self.session,self.root/'bad',saved=saved,preview=False)

    def test_stale_or_rehashed_missing_manifest_rejected(self):
        s=view.read_json(self.audit/'SUMMARY.json');key=next(k for k in s['binding']['audit_sources'] if k.endswith('range_tracker.py'))
        del s['binding']['audit_sources'][key];s.pop('content_sha256');s['content_sha256']=view.digest(s);write(self.audit/'SUMMARY.json',s)
        with self.assertRaisesRegex(ValueError,'incomplete audit source'):self.build()

    def test_changed_rule_ledger_rejected(self):
        with (self.audit/'RULE_BASELINE.jsonl').open('a',encoding='utf-8') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'ledger SHA'):self.build()

    def test_empty_measurement_cannot_have_box_or_height(self):
        saved,rows=self.saved();rows[0]['bb']=[0]*6
        (saved/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows)+';',encoding='utf-8');self.save_ledger(saved,rows)
        with self.assertRaisesRegex(ValueError,'unmeasured frame'):view.build(self.session,self.root/'bad',saved=saved,preview=False)

    def test_output_guards_and_mode_required(self):
        with self.assertRaisesRegex(ValueError,'choose exactly'):view.build(self.session,self.root/'bad',preview=False)
        with self.assertRaisesRegex(ValueError,'overlaps'):view.build(self.session,self.session/'bad',replay=self.f.replay,audit=self.audit,preview=False)
        self.build()
        with self.assertRaisesRegex(ValueError,'already exists'):self.build()

    def test_causal_prefix_rows_equal(self):
        self.build();r=self.root/'prefix'
        fixture.replay(self.session,r,empty_prefix_frames=1,frontend='range_v1',limit=3)
        a=self.root/'prefix_audit';view.experiment.run(self.session,a,r)
        view.build(self.session,self.root/'prefix_view',replay=r,audit=a,preview=False)
        self.assertEqual(view.js_records(self.root/'view/data/frames.js')[:3],view.js_records(self.root/'prefix_view/data/frames.js'))

    def test_camera_pairing_exact_delta_and_empty(self):
        camera=([dict(recv_unix_ns=1792700000000000001),dict(recv_unix_ns=1792700000100000001)],b'')
        self.assertEqual(view.camera_link(camera,1792700000),[0,1e-9])
        self.assertIsNone(view.camera_link(([],b''),1))
        self.assertIsNone(view.camera_link(camera,True))

    def test_read_sources_mutated_during_export_rejected(self):
        saved,_=self.saved()
        def change(*args):
            p=saved/'GROUND.json';p.write_bytes(p.read_bytes()+b' ')
        with mock.patch.object(view,'render_preview',side_effect=change):
            with self.assertRaisesRegex(ValueError,'changed during'):view.build(self.session,self.root/'bad',saved=saved,preview=True)
        self.assertFalse((self.root/'bad/SUMMARY.json').exists())

    def test_title_and_summary_html_escaped(self):
        self.build(title='<script>alert(1)</script>@@TITLE@@')
        content=(self.root/'view/index.html').read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;@@TITLE@@',content)
        self.assertNotIn('<script>alert(1)</script>',content)

    def test_nonfinite_projected_lines_never_reach_rasterizer(self):
        self.assertFalse(view.drawable_segment([[float('nan'),0,1],[1,1,2]]))
        self.assertFalse(view.drawable_segment([[0,0,-1],[1,1,2]]))
        self.assertFalse(view.drawable_segment([[1e20,0,1],[1,1,2]]))
        self.assertTrue(view.drawable_segment([[0,0,1],[1,1,2]]))


if __name__=='__main__':unittest.main()
