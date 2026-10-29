"""发行包搬迁、缺件/篡改拒绝与可复现ZIP。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import make_release
from release import verify_package


class ReleaseTests(unittest.TestCase):
    def test_portable_package_verifies_and_starts_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);archive=folder/'release.zip'
            result=make_release.build(archive)
            self.assertEqual(result['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as z:
                self.assertFalse(any('/data/' in n or '/ML/' in n for n in z.namelist()))
                z.extractall(folder)
            package=folder/'RangeReplay-0.1.0'
            verify_package(package)
            for args in (['--check'],['--version'],['--help']):
                done=subprocess.run([sys.executable,'-B','-W','error',str(package/'run.py')]+args,
                    cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                self.assertEqual(done.returncode,0,done.stderr.decode(errors='replace'))
            path=package/'src/human_fall_detection/scripts/sensor_health.py'
            path.write_bytes(path.read_bytes()+b'\n# tampered\n')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):verify_package(package)
            done=subprocess.run([sys.executable,'-B','-W','error',str(package/'run.py'),'--check'],
                cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(done.returncode,0)

    def test_zip_is_reproducible_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'a.zip',Path(temp)/'b.zip'
            self.assertEqual(make_release.build(a)['sha256'],make_release.build(b)['sha256'])
            with self.assertRaises(FileExistsError):make_release.build(a)


if __name__=='__main__': unittest.main()
