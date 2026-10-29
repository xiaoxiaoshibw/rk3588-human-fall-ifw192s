"""Real Qt controls, sidecar rename and local annotator startup against private input."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_integration as fixtures
from test_integration import ROOT, SDK, DLL, HOST


class TestWorkspace(unittest.TestCase):
    setUp = fixtures.TestApp.setUp
    _delete_workdir = fixtures.TestApp._delete_workdir
    def test_drawer_rename_annotation_and_source_immutability(self):
        work = self._delete_workdir(['workspace_001', 'workspace_002'])
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in work.rglob('*') if p.is_file()}
        names = self.out / 'session_names.json'
        args = [str(SDK), str(DLL), '--session', str(work / 'workspace_001'),
                '--host', str(HOST), '--report', str(self.out / 'run.json'),
                '--names-file', str(names), '--python', sys.executable,
                '--workspace-report', str(self.out / 'workspace.json'), '--no-external-open']
        done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=35)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
        report = json.loads((self.out / 'workspace.json').read_text())
        self.assertEqual(report['status'], 'PASS', report)
        self.assertEqual(json.loads(names.read_text())['workspace_001'], '客厅 · 躺倒测试')
        self.assertIn('sid=workspace_001&frame=0', report['annotationUrl'])
        for path, sha in before.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), sha)
        service = json.loads((self.out / 'run.json').read_text())
        self.assertEqual(service['jointMutationRequests'], 0)
        self.assertEqual(service['sessionDeletes'], 0)
        self.assertTrue(any(row['eventType'] == 'annotatorOpened' for row in service['log']))


if __name__ == '__main__':
    unittest.main()
