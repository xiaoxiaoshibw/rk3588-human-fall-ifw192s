"""Synthetic scene references: real chronology, no post-event reconstruction."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image

from fall_candidate_runtime import file_sha256
from urfall_scene_reference import build,load_reference,check_clock,check_ground
from urfall_raw_depth import run,load_pinhole
from evaluate_urfall_raw import evaluate


def make_fixture(root):
    camera=dict(schema='urfall_pinhole_v1',camera='cam0',width=160,height=120,
                fx=100.,fy=100.,cx=79.5,cy=50.,status='nominal_diagnostic',physical_verified=False,
                source='analytic software fixture; not calibrated real camera')
    calibration=root/'camera.json';calibration.write_text(json.dumps(camera),encoding='utf-8')
    v,u=np.mgrid[:120,:160]
    floor=np.full((120,160),4.,dtype=float)
    below=v>75
    floor[below]=100./(v[below]-50.)
    source=root/'adl-01-cam0-d.zip';target=root/'fall-01-cam0-d.zip'
    source_sync=root/'adl-01-data.csv';target_sync=root/'fall-01-data.csv'
    for archive,sync,sequence,count,scale,body in [
            (source,source_sync,'adl-01',10,7.,False),(target,target_sync,'fall-01',40,6.,True)]:
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for i in range(count):
                depth=floor.copy()
                if body:
                    angle=min(1.,max(0.,(i/30.-.1)/.4))*np.pi/2
                    x=(u-79.5)*1.85/100.;height=-(v-50.)*1.85/100.
                    along=(x+.6)*np.sin(angle)+(height+.8)*np.cos(angle)
                    across=(x+.6)*np.cos(angle)-(height+.8)*np.sin(angle)
                    mask=(along>=0)&(along<=1.4)&(np.abs(across)<=.14)&(depth>1.85)
                    depth[mask]=1.85
                image=np.rint(depth/scale*65535).astype(np.uint16)
                stream=io.BytesIO();Image.fromarray(image).save(stream,format='PNG')
                z.writestr('%s-cam0-d/%s-cam0-d-%03d.png'%(sequence,sequence,i+1),stream.getvalue())
        sync.write_text(''.join('%d,%d\n'%(i+1,round(i*1000/30)) for i in range(count)),encoding='utf-8')
    clock=root/'clock_pair.json'
    metadata=dict(schema='recording_clock_pair_v1',qualification='metadata_declared',
                  clock_id='synthetic_monotonic',installation_id='synthetic_setup',
                  source_archive_sha256=file_sha256(source),target_archive_sha256=file_sha256(target),
                  source_origin_s=0.,target_origin_s=100.,uncertainty_s=.001,
                  empty_source_prefix_declared=True)
    clock.write_text(json.dumps(metadata),encoding='utf-8')
    return dict(source=source,source_sync=source_sync,target=target,target_sync=target_sync,
                calibration=calibration,clock=clock)


def build_fixture(paths,out):
    return build(paths['source'],paths['source_sync'],paths['target'],paths['target_sync'],
                 paths['calibration'],paths['clock'],out)


class SceneReferenceTest(unittest.TestCase):
    def test_pre_event_context_observes_from_first_frame_and_detects_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=make_fixture(root);manifest=build_fixture(p,root/'reference')
            external=run(p['target'],p['target_sync'],p['calibration'],root/'external',
                         ground_start_fraction=.75,scene_reference_path=root/'reference/REFERENCE.json')
            internal=run(p['target'],p['target_sync'],p['calibration'],root/'internal',ground_start_fraction=.75)
            frames=[json.loads(s) for s in (root/'external/FRAMES.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(frames[0]['extraction_status'],'measured_component')
            self.assertGreater(frames[0]['target_points'],40)
            self.assertEqual(len(external['events']),1)
            self.assertEqual(internal['events'],[])
            self.assertFalse(manifest['physical_verified'])
            self.assertEqual(external['protocol']['scene_reference']['chronology']['qualification'],
                             'metadata_declared; not physical verification')
            prefix=run(p['target'],p['target_sync'],p['calibration'],root/'prefix',limit=6,
                       scene_reference_path=root/'reference/REFERENCE.json')
            short=[json.loads(s) for s in (root/'prefix/FRAMES.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(short,frames[:6])

    def test_bad_clock_and_same_recording_refused(self):
        base=dict(schema='recording_clock_pair_v1',qualification='metadata_declared',clock_id='c',
                  installation_id='s',empty_source_prefix_declared=True,source_archive_sha256='a',
                  target_archive_sha256='b',source_origin_s=0.,target_origin_s=1.,uncertainty_s=.1)
        for changes in (dict(target_origin_s=.4),dict(source_origin_s=2.),dict(clock_id=''),
                        dict(uncertainty_s=float('nan')),dict(empty_source_prefix_declared=False)):
            with self.assertRaises(ValueError):
                check_clock(dict(base,**changes),'a','b',.3,0.)
        with self.assertRaises(ValueError):
            check_clock(dict(base,target_archive_sha256='a'),'a','a',.3,0.)

    def test_corrupt_or_mismatched_reference_has_no_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=make_fixture(root);build_fixture(p,root/'reference')
            reference=root/'reference/REFERENCE.json';camera=load_pinhole(p['calibration'])
            args=(reference,camera,file_sha256(p['calibration']),4,'fall-01',
                  file_sha256(p['target']),file_sha256(p['target_sync']),0.)
            load_reference(*args)
            original=json.loads(reference.read_text(encoding='utf-8'))
            for changes in (dict(holdout_support=dict(original['ground']['holdout_support'],fraction=.1)),
                            dict(settings=dict(original['ground']['settings'],min_holdout_support=.1)),
                            dict(normal=[0.,0.,-1.])):
                with self.assertRaises(ValueError):
                    check_ground(dict(original['ground'],**changes))
            with self.assertRaises(ValueError):
                load_reference(reference,dict(camera,fx=101.),*args[2:])
            with self.assertRaises(ValueError):
                load_reference(*args[:4],'fall-02',*args[5:])
            with self.assertRaises(ValueError):
                load_reference(*args[:3],8,*args[4:])
            bad_depth=np.full((30,40),np.nan)
            np.savez_compressed(root/'reference/reference.npz',depth_m=bad_depth)
            corrupt=dict(original,members_sha256=dict(original['members_sha256'],
                **{'reference.npz':file_sha256(root/'reference/reference.npz')}))
            reference.write_text(json.dumps(corrupt),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'depth grid'):
                load_reference(*args)
            reference.write_text(json.dumps(original),encoding='utf-8')
            (root/'reference/reference.npz').write_bytes(b'bad cache')
            with self.assertRaisesRegex(ValueError,'SHA'):
                run(p['target'],p['target_sync'],p['calibration'],root/'must_not_run',
                    scene_reference_path=reference)
            self.assertFalse((root/'must_not_run').exists())

    def test_batch_reference_request_keeps_missing_reference_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=make_fixture(root)
            (root/'DOWNLOAD.json').write_text(json.dumps([dict(name=p['target'].name,status='OK',
                sha256=file_sha256(p['target']))]),encoding='utf-8')
            for name in ('urfall-cam0-falls.csv','urfall-cam0-adls.csv'):
                (root/name).write_text('',encoding='utf-8')
            report=evaluate(root,root/'pending',p['calibration'],root/'batch',
                            scene_references=root/'references')
            self.assertEqual(report['completed_sequences'],0)
            self.assertEqual(report['failure_counts']['SCENE_REFERENCE_NOT_PROVIDED'],1)
            self.assertEqual(len(report['results']),70)


if __name__=='__main__':
    unittest.main()
