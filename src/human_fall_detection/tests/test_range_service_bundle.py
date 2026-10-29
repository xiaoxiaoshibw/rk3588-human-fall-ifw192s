"""The deployable closure must run without repository PYTHONPATH helpers."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('range_bundle', ROOT/'src/human_fall_detection/scripts/prepare_range_service_bundle.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BundleTests(unittest.TestCase):
    def test_deterministic_recognition_only_closure_imports_in_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            first = builder.build(ROOT, out/'one.tar')
            second = builder.build(ROOT, out/'two.tar')
            self.assertEqual(first['sha256'], second['sha256'])
            unpacked = out/'bundle'
            unpacked.mkdir()
            with tarfile.open(out/'one.tar') as tar:
                # All names are generated repository-relative by our builder.
                for member in tar:
                    self.assertNotIn('..', Path(member.name).parts)
                    target = unpacked/member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as f:
                        target.write_bytes(f.read())
            release = json.loads((unpacked/'RELEASE.json').read_text('utf8'))
            self.assertEqual(release['kind'], 'range_recognition_only')
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-B', '-W', 'error', str(unpacked/release['entry']), '--help'],
                cwd=unpacked, env=env, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
