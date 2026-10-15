"""Synthetic HTTP fixture; no real source or gold annotation is created."""
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import importlib.util
from pathlib import Path
import numpy as np
from contracts import OLD, write, sha, project


class HTTP(unittest.TestCase):
    def test_windows_index_source_missing_and_drift(self):
        spec = importlib.util.spec_from_file_location('new_http_test', Path(__file__).with_name('server.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            e = Path(folder)/'synthetic_http_only'; e.mkdir(); p = e/'primary'
            raw = np.array([[1, 0, 0], [1.2, .1, .2]], dtype='f4')
            rel = 'common/synthetic/0000.npz'; (p/'common/synthetic').mkdir(parents=True)
            np.savez(p/rel, raw=raw, nominal=raw, corrected=raw, U=np.ones(2, bool))
            files = {rel:sha(p/rel)}
            rel = 'runs/G0/synthetic/0000.npz'; (p/'runs/G0/synthetic').mkdir(parents=True)
            np.savez(p/rel, selected=np.array([1, 0]), cluster=np.array([0, -1])); files[rel] = sha(p/rel)
            row = dict(sid='synthetic', fi=0, source={'meta':'not_real', 'points':'not_real'}, U=2, selected=1, source_frame={}, time=0)
            rel = 'runs/G0/synthetic/0000.json'; write(p/rel, row); files[rel] = sha(p/rel)
            rel = 'projection/synthetic/0000_128.npz'; (p/'projection/synthetic').mkdir(parents=True)
            prs = [project(raw, dict(bounds_radians=[[-1, 1], [-1, 1]]), 128, 512, mode) for mode in ['range', 'axial']]
            np.savez(p/rel, **{mode+'_'+k:v for mode, pr in zip(['range', 'axial'], prs) for k, v in pr.items()}); files[rel] = sha(p/rel)
            write(e/'RUN_MANIFEST.json', dict(schema='hfus-learn/1', run_id=e.name, source_sha256={}, sources={'synthetic':dict(frames=1, sha256=row['source'])}, split=dict(empty_sid='empty')))
            write(e/'ANNOTATION_TASKS.json', []); write(e/'LABEL_MANIFEST.json', {}); write(e/'EXPERIMENT_MATRIX.json', {})
            write(p/'INDEX.json', dict(run_manifest_sha256=sha(e/'RUN_MANIFEST.json'), files=files, geometry_streams=['G0']))
            server = module.serve(e); thread = threading.Thread(target=server.serve_forever); thread.start()
            url = 'http://127.0.0.1:'+str(server.server_address[1])
            try:
                with urllib.request.urlopen(url+'/learn/'+e.name+'/frame?sid=synthetic&fi=0') as f:
                    self.assertEqual(json.load(f)['rows'], [0, 1])
                with urllib.request.urlopen(url+'/learn/'+e.name+'/source?sid=synthetic&fi=0&row=0') as f:
                    self.assertEqual(json.load(f)['status'], 'BLOCKED_MISSING_ORIGINAL')
                with urllib.request.urlopen(url+'/') as f: self.assertEqual(f.read(), (OLD/'index.html').read_bytes())
                with self.assertRaises(ValueError): module.View(e, expected_manifest='wrong_sha')
                self.assertEqual(module.View(e).verified('common\\synthetic\\0000.npz'), p/'common/synthetic/0000.npz')
                with (p/'common/synthetic/0000.npz').open('ab') as f: f.write(b'content_drift')
                with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(url+'/learn/'+e.name+'/frame?sid=synthetic&fi=0')
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
