import json
import hashlib
import tempfile
import unittest
from unittest.mock import Mock,patch
from pathlib import Path
import numpy as np
from coordinates import GroundCoordinates
from server import Store
from run import HERE

class CoordinateChain(unittest.TestCase):
    def test_all_display_objects_use_same_transform(self):
        store=Store()
        try:
            for variant in store.data:
                a=store.frame('cap_20261018_110029',341,variant,'room',coordinate='raw')
                b=store.frame('cap_20261018_110029',341,variant,'room',coordinate='ground')
                for key in ('room','fg','target'):
                    np.testing.assert_allclose(b[key],store.coordinates.points(a[key]),rtol=0,atol=1e-12)
                for key,n in a['row']['skeleton']['nodes'].items():
                    if n['xyz'] is not None:
                        np.testing.assert_allclose(b['row']['skeleton']['nodes'][key]['xyz'],store.coordinates.points(n['xyz']),rtol=0,atol=1e-12)
                p=np.array(b['fg'])
                np.testing.assert_array_equal(b['row']['bbox_foreground']['min'],p.min(0))
                np.testing.assert_array_equal(b['row']['bbox_foreground']['max'],p.max(0))
                if b['row']['bbox'] is not None:
                    np.testing.assert_array_equal(b['row']['bbox']['min'],np.asarray(b['target']).min(0))
                    np.testing.assert_array_equal(b['row']['bbox']['max'],np.asarray(b['target']).max(0))
                    self.assertGreaterEqual(b['row']['bbox']['min'][0],b['row']['bbox_foreground']['min'][0]-1e-12)
                    self.assertLessEqual(b['row']['bbox']['max'][0],b['row']['bbox_foreground']['max'][0]+1e-12)
                self.assertLessEqual(b['row']['foreground']['body_points'],b['row']['foreground']['points'])
                x=store.frame('cap_20261018_110029',341,variant,key='OUTER_A',coordinate='raw')
                y=store.frame('cap_20261018_110029',341,variant,key='OUTER_A',coordinate='ground')
                np.testing.assert_allclose(np.array(y['points']).reshape(-1,3),store.coordinates.points(x['points']),rtol=0,atol=1e-12)
                self.assertEqual(x['global_rows'],y['global_rows'])
                self.assertEqual(x['local_rows'],y['local_rows'])
                self.assertEqual(b['coordinate'],y['coordinate'])
            with self.assertRaises(ValueError):store.frame('cap_20261018_110029',341,'partition',coordinate='wrong')
        finally:store.src.close()

    def test_wrong_source_and_improper_rotation_rejected(self):
        store=Store()
        try:
            with tempfile.TemporaryDirectory() as folder:
                p=Path(folder)/'transform.json';a=store.coordinates.artifact.copy()
                p.write_text(json.dumps(a),encoding='utf8')
                with self.assertRaises(ValueError):GroundCoordinates(p,'wrong_sid',store.src.binding)
                a['R']=[[-1,0,0],[0,1,0],[0,0,1]];p.write_text(json.dumps(a),encoding='utf8')
                with self.assertRaises(ValueError):GroundCoordinates(p,'cap_20261018_110029',store.src.binding)
        finally:store.src.close()

    def test_pointer_cannot_substitute_another_same_session_ground(self):
        store=Store()
        try:
            pointer=json.loads((HERE/'LATEST.json').read_text(encoding='utf8'))
            with tempfile.TemporaryDirectory() as folder:
                transform=Path(folder)/'other_ground.json'
                artifact=json.loads(json.dumps(store.coordinates.artifact))
                artifact['t'][2]+=.1
                artifact['transform_id']='different_same_session_ground'
                transform.write_text(json.dumps(artifact),encoding='utf8')
                # It is a valid rigid transform bound to the very same source.
                GroundCoordinates(transform,store.sid,store.src.binding)
                pointer['ground_transform']=dict(path=str(transform),sha256=hashlib.sha256(transform.read_bytes()).hexdigest())
                candidate=Path(folder)/'pointer.json';candidate.write_text(json.dumps(pointer),encoding='utf8')
                with self.assertRaisesRegex(ValueError,'differs from completed run'):Store(candidate)
        finally:store.src.close()

    def test_store_initialization_failures_close_source(self):
        pointer=json.loads((HERE/'LATEST.json').read_text(encoding='utf8'))
        binding=json.loads((HERE.parents[3]/pointer['output']/'RUN.json').read_text(encoding='utf8'))
        for failure in ('coordinate','default'):
            source=Mock(sid=binding['sid'],binding=binding['input_sha'])
            with tempfile.TemporaryDirectory() as folder:
                candidate=Path(folder)/'pointer.json'
                p=json.loads(json.dumps(pointer))
                if failure=='default':p['default_variant']='bogus'
                candidate.write_text(json.dumps(p),encoding='utf8')
                with patch('server.P.source',return_value=source):
                    if failure=='coordinate':
                        with patch('server.GroundCoordinates',side_effect=ValueError('injected coordinate failure')):
                            with self.assertRaisesRegex(ValueError,'injected'):Store(candidate)
                    else:
                        with self.assertRaisesRegex(ValueError,'invalid project default'):Store(candidate)
                source.close.assert_called_once_with()

if __name__=='__main__':unittest.main()
