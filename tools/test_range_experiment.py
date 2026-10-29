"""合并入口的软件契约，不提供同步/人体GT。"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/human_fall_detection/scripts'))
from range_experiment import (run,row_statistics,integer_clock_ns,RuleBaseline,
                              INFERENCE_KEYS,CALIBRATION)
from sync_audit import file_binding
from test_sync_audit import alignment
from replay_range_tracking import run as replay
from core.capture_input import ROW_DTYPE,EXPECTED_LAYOUT
from core.range_image import ScanGrid


def write(path,value):path.write_text(json.dumps(value,sort_keys=True,allow_nan=False),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


class RangeExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid=ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv',
                                  CALIBRATION/'ifw192s_elevation_192x256.csv')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.session=self.root/'session'; self.session.mkdir()
        grid=self.grid; n=int(np.prod(grid.shape)); raw=np.zeros(n,dtype=ROW_DTYPE)
        raw['ring']=np.repeat(np.arange(grid.shape[0]),grid.shape[1])
        az,el=np.radians(grid.azimuth_deg.ravel()),np.radians(grid.elevation_deg.ravel())
        directions=np.column_stack((np.cos(el)*np.cos(az),np.cos(el)*np.sin(az),np.sin(el)))
        frames=[]
        with (self.session/'points.bin').open('wb') as stream:
            for i in range(4):
                depth=np.full(grid.shape,2.0)
                if i:depth[60:80,60:80]=1.5
                xyz=directions*depth.ravel()[:,None]
                for k,key in enumerate(('x','y','z')):raw[key]=xyz[:,k]
                raw['timestamp']=700000+i*.1
                stream.write(raw.tobytes())
                frames.append(dict(seq=i,stamp_sec=700000,stamp_nanosec=i*100000000,
                    bag_time_sec=1792700000+i*.1,count_points=n,offset_points=i*n,dropped_points=0))
        write(self.session/'meta.json',dict(format='human_capture_session',format_version=1,
            point_layout=EXPECTED_LAYOUT,point_file='points.bin',point_stride_bytes=28,
            sensor=dict(frame_id='innolidar',units='m'),extraction=dict(tool='bag2session/0.1.0',
            point_step_bytes_src=26,dropped_frames=0),time_domain='device_stamp_s_unanchored',
            frames=frames,total_points=4*n,total_dropped_points=0))
        self.replay=self.root/'replay'
        with contextlib.redirect_stdout(io.StringIO()):
            replay(self.session,self.replay,empty_prefix_frames=1,frontend='range_v1')

    def modify_record(self,change):
        rows=records(self.replay/'frames.jsonl'); change(rows)
        infer=hashlib.sha256(); aggregate=hashlib.sha256()
        with (self.replay/'frames.jsonl').open('w',encoding='utf-8') as stream:
            for row in rows:
                pure=json.dumps({k:row[k] for k in INFERENCE_KEYS},sort_keys=True,allow_nan=False)
                row['inference_sha256']=hashlib.sha256(pure.encode()).hexdigest(); infer.update(pure.encode())
                serial=json.dumps(row,sort_keys=True,allow_nan=False); aggregate.update(serial.encode())
                stream.write(serial+'\n')
        s=read(self.replay/'SUMMARY.json'); s.update(frames_sha256=file_binding(self.replay/'frames.jsonl')['sha256'],
            algorithm_output_sha256=aggregate.hexdigest(),inference_output_sha256=infer.hexdigest())
        write(self.replay/'SUMMARY.json',s)

    def test_no_camera_keeps_lidar_audit_and_unknown_sync(self):
        before={p.name:p.read_bytes() for p in self.session.iterdir()}
        result=run(self.session,self.root/'audit',self.replay)
        self.assertEqual(result['status'],'SOFTWARE_AUDITED')
        self.assertEqual(result['frames_processed'],4)
        self.assertEqual(result['sync_status'],'INCOMPLETE')
        self.assertEqual(result['quality']['physical_sync_error_s'],'UNKNOWN')
        self.assertEqual(result['totals']['target_observed_frames'],1)
        self.assertEqual(result['totals']['repeated_output_rows'],0)
        self.assertEqual(result['totals']['raw_rows'],4*np.prod(self.grid.shape))
        self.assertFalse(result['rule_baseline']['confirmed_enabled'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.session.iterdir()})

    def test_relative_cli_works_with_isolated_python(self):
        root=Path(__file__).resolve().parents[1]
        args=[sys.executable,'-B','-W','error','tools/range_experiment.py',
              '--session',str(self.session),'--out',str(self.root/'cli')]
        result=subprocess.run(args,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        self.assertEqual(subprocess.run(args,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode,1)

    def test_sampling_counts_repeats_foreign_and_empty_denominator(self):
        s=row_statistics([0,1,2],[0,0,4,True,1.5])
        self.assertEqual((s['repeated_output_rows'],s['foreign_unique_rows'],s['invalid_output_rows'],s['removed_unique_rows']),(1,1,2,2))
        self.assertIsNone(row_statistics([],[])['duplicate_fraction'])

    def test_exact_nanosecond_clock_preserves_regression(self):
        ns=1792700000000000000
        c=integer_clock_ns([ns,ns+1,ns+1,ns,ns+2])
        self.assertEqual((c['duplicates'],c['regressions']),(1,1))
        self.assertAlmostEqual(c['max_positive_interval_s'],2e-9)

    def test_same_frame_name_cannot_bypass_wrong_source_sha(self):
        s=read(self.replay/'SUMMARY.json'); s['source_binding']['points_sha256']='0'*64
        write(self.replay/'SUMMARY.json',s)
        with self.assertRaisesRegex(ValueError,'source SHA mismatch'):run(self.session,self.root/'bad',self.replay)

    def test_ledger_tampering_rejected(self):
        with (self.replay/'frames.jsonl').open('a') as f:f.write(' ') 
        with self.assertRaisesRegex(ValueError,'ledger SHA mismatch'):run(self.session,self.root/'bad',self.replay)

    def test_repeated_track_rows_rejected_even_with_rehashed_ledger(self):
        self.modify_record(lambda rows:rows[-1]['tracks'][0]['source_rows'].append(rows[-1]['tracks'][0]['source_rows'][0]))
        with self.assertRaisesRegex(ValueError,'unique current component union'):run(self.session,self.root/'bad',self.replay)

    def test_foreign_rows_rejected(self):
        self.modify_record(lambda rows:rows[-1]['tracks'][0]['source_rows'].__setitem__(0,999999))
        with self.assertRaisesRegex(ValueError,'unique current component union'):run(self.session,self.root/'bad',self.replay)

    def test_cross_track_component_reuse_rejected(self):
        def change(rows):
            other=json.loads(json.dumps(rows[-1]['tracks'][0])); other['track_id']='other'; rows[-1]['tracks'].append(other)
        self.modify_record(change)
        with self.assertRaisesRegex(ValueError,'one-to-one'):run(self.session,self.root/'bad',self.replay)

    def test_prediction_cannot_carry_measured_points(self):
        self.modify_record(lambda rows:rows[-1]['tracks'][0].update(observed=False,position_predicted=True))
        with self.assertRaisesRegex(ValueError,'prediction contains'):run(self.session,self.root/'bad',self.replay)

    def test_conflicting_measurement_flags_rejected(self):
        self.modify_record(lambda rows:rows[-1]['tracks'][0].update(position_predicted=True))
        with self.assertRaisesRegex(ValueError,'flag conflict'):run(self.session,self.root/'bad',self.replay)

    def test_feature_count_must_match_real_rows(self):
        self.modify_record(lambda rows:rows[-1]['tracks'][0]['features'].update(point_count=1))
        with self.assertRaisesRegex(ValueError,'point count mismatch'):run(self.session,self.root/'bad',self.replay)

    def test_dangling_target_id_rejected(self):
        self.modify_record(lambda rows:rows[0].update(target_track_id='absent'))
        with self.assertRaisesRegex(ValueError,'dangling target'):run(self.session,self.root/'bad',self.replay)

    def test_target_cannot_read_different_rows(self):
        self.modify_record(lambda rows:rows[-1]['target_source_rows'].append(0))
        with self.assertRaisesRegex(ValueError,'selected stable'):run(self.session,self.root/'bad',self.replay)

    def test_bag_time_is_not_w2_header_time(self):
        self.modify_record(lambda rows:rows[-1].update(time_s=1792700000.3))
        with self.assertRaisesRegex(ValueError,'header clock'):run(self.session,self.root/'bad',self.replay)

    def test_source_code_change_marks_stale_without_reinterpreting_old_rows(self):
        s=read(self.replay/'SUMMARY.json'); key=next(iter(s['source_sha256'])); s['source_sha256'][key]='0'*64
        write(self.replay/'SUMMARY.json',s)
        result=run(self.session,self.root/'stale',self.replay)
        self.assertEqual(result['status'],'STALE'); self.assertEqual(result['frames_processed'],0)
        self.assertFalse(result['rule_baseline']['executed'])

    def test_missing_required_source_manifest_entry_marks_stale(self):
        s=read(self.replay/'SUMMARY.json')
        key=next(k for k in s['source_sha256'] if k.endswith('range_tracker.py'))
        del s['source_sha256'][key]; write(self.replay/'SUMMARY.json',s)
        result=run(self.session,self.root/'missing-source',self.replay)
        self.assertEqual(result['status'],'STALE')
        self.assertEqual(result['frames_processed'],0)
        self.assertTrue(any(k.endswith('range_tracker.py') for k in result['source_code_changes']))
        self.assertFalse(result['rule_baseline']['executed'])

    def test_alignment_without_source_binding_is_never_applied(self):
        path=self.root/'alignment.json'; write(path,alignment())
        result=run(self.session,self.root/'unbound',alignment_path=path)
        self.assertEqual(result['alignment_binding'],'UNBOUND'); self.assertFalse(result['temporal_link_applied'])
        document=alignment(); document['source_binding']={'points.bin':{'sha256':'wrong'}}; write(path,document)
        with self.assertRaisesRegex(ValueError,'alignment source binding mismatch'):
            run(self.session,self.root/'wrong',alignment_path=path)

    def test_historical_joint_failure_and_current_bytes_are_both_preserved(self):
        write(self.session/'joint.json',dict(state='failed',error='old fetch failure',radar_frames=4,camera_frames=0))
        r=run(self.session,self.root/'joint')
        self.assertEqual(r['quality']['joint_state'],'failed')
        self.assertTrue(r['quality']['current_lidar_bytes_complete'])
        self.assertEqual(r['quality']['actual_sampling_loss'],'UNKNOWN')

    def test_previous_audit_and_sync_tool_change(self):
        out=self.root/'first'; run(self.session,out,self.replay)
        r=run(self.session,self.root/'same',self.replay,previous=out)
        self.assertEqual(r['previous_status'],'UNCHANGED')
        fake=self.root/'tool.py'; fake.write_text('# changed tool bytes')
        with mock.patch('sync_audit.__file__',str(fake)):
            r=run(self.session,self.root/'changed',self.replay,previous=out)
        self.assertEqual(r['previous_status'],'STALE')

    def test_previous_report_tampering_is_not_unchanged(self):
        previous=self.root/'previous'; run(self.session,previous,self.replay)
        report=read(previous/'SUMMARY.json'); report['frames_processed']=999; write(previous/'SUMMARY.json',report)
        with self.assertRaisesRegex(ValueError,'previous combined audit content SHA mismatch'):
            run(self.session,self.root/'tampered',self.replay,previous=previous)

    def test_source_only_scope_change_invalidates_previous(self):
        previous=self.root/'previous'; run(self.session,previous)
        changed=run(self.session,self.root/'short',previous=previous,limit=1)
        self.assertEqual(changed['previous_status'],'STALE')
        self.assertEqual(changed['binding']['frame_range'],[0,1])

    def test_late_source_mutation_rejected(self):
        import range_experiment
        original=range_experiment.integer_clock_ns
        def mutate(values):
            result=original(values)
            (self.session/'points.bin').write_bytes((self.session/'points.bin').read_bytes()+b'x')
            return result
        with mock.patch('range_experiment.integer_clock_ns',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'source changed during combined audit'):
                run(self.session,self.root/'changed')

    def test_ground_mutation_after_load_is_rejected(self):
        import range_experiment
        binding=read(self.replay/'SUMMARY.json')['source_binding']
        provenance=self.root/'plane.json'
        write(provenance,dict(sid=self.session.name,source_sha256=dict(meta=binding['meta_sha256'],points=binding['points_sha256']),
            from_frame='RAW/innolidar',units='m',plane=dict(normal_source=[0,0,1],offset_source_m=0)))
        path=self.root/'ground.json'
        write(path,dict(status='valid',frame='innolidar',normal=[0,0,1],offset_m=0,binding=binding,
            provenance=dict(source=str(provenance),sha256=file_binding(provenance)['sha256'])))
        original=range_experiment.load_ground
        def mutate(*args):
            result=original(*args); provenance.write_bytes(provenance.read_bytes()+b' '); return result
        with mock.patch('range_experiment.load_ground',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'ground changed while reading'):
                run(self.session,self.root/'changed',ground_path=path)

    def test_causal_prefix_and_output_protection(self):
        full=self.root/'full'; run(self.session,full,self.replay)
        prefix_replay=self.root/'prefix_replay'
        with contextlib.redirect_stdout(io.StringIO()):
            replay(self.session,prefix_replay,empty_prefix_frames=1,frontend='range_v1',limit=3)
        prefix=self.root/'prefix'; run(self.session,prefix,prefix_replay)
        for name in ('SOURCE_ROWS.jsonl','RULE_BASELINE.jsonl'):
            self.assertEqual(records(full/name)[:3],records(prefix/name))
        for destination in (self.session/'bad',full):
            with self.assertRaises(ValueError):run(self.session,destination)

    def test_rule_low_birth_and_measured_descent_never_confirm(self):
        from types import SimpleNamespace
        xyz=np.column_stack((np.linspace(-.4,.4,100),.05*np.sin(np.linspace(0, 4*np.pi, 100)),np.full(100,.2)))
        frame=SimpleNamespace(xyz=xyz, binding=())
        plane=dict(status='valid',frame='innolidar',normal=[0,0,1],offset_m=0)
        def sequence(heights):
            rule=RuleBaseline('synthetic',plane,'fixture'); out=[]
            for i,h in enumerate(heights):
                frame.xyz[:,2]=h
                out.append(rule.update(frame,dict(frame=i,time_s=i*.1,generation=0,target_track_id='t',
                    target_source_rows=list(range(100)),inference_sha256='synthetic',tracks=[dict(
                        track_id='t',status='tracked',observed=True,position_predicted=False,source_rows=list(range(100)))])))
            return out
        low=sequence([.2]*40)
        self.assertTrue(all(r['state']['state']=='low_posture_unclassified' for r in low))
        falling=sequence([1.7]*5+list(np.linspace(1.7,.2,10))+[.2]*30)
        self.assertTrue(any(r['state']['state']=='suspected' for r in falling))
        self.assertTrue(all(r['state']['new_event'] is None and not r['state']['confirmed_enabled'] for r in falling))


if __name__=='__main__':unittest.main()
