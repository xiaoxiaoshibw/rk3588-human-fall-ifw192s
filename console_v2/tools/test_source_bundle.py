"""Regression for the source bundle given to LAN colleagues.

Checks: required build inputs are present, development-only trees are absent,
manifest hashes match, the zip mirrors the manifest, the PowerShell launchers
keep a UTF-8 BOM (Windows PowerShell 5.1 needs it for Chinese text), and the
bundle is reproducible (two runs produce the same zip SHA).
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'console_v2' / 'tools' / 'make_source_bundle.py'
WORK = ROOT / 'console_v2' / '.tools' / 'source-bundle-test'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


class SourceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if WORK.exists():
            shutil.rmtree(WORK)
        WORK.mkdir(parents=True)
        cls.outputs = []
        for name in ('a', 'b'):
            out = WORK / name
            result = subprocess.run([sys.executable, '-B', '-W', 'error', str(SCRIPT),
                                     '--out', str(out), '--zip'],
                                    cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.outputs.append(out)
        cls.manifest = json.loads((cls.outputs[0] / 'MANIFEST.json').read_text(encoding='utf8'))
        cls.paths = {item['path'] for item in cls.manifest['files']}

    @classmethod
    def tearDownClass(cls):
        if WORK.exists():
            shutil.rmtree(WORK)

    def test_required_build_inputs(self):
        for rel in (
            'console_v2/app/native/CMakeLists.txt',
            'console_v2/app/native/Main.qml',
            'console_v2/app/service/AppService.csproj',
            'console_v2/app/service/Program.cs',
            'console_v2/spike/service/FrameCodec.cs',
            'console_v2/app/local_replay_worker.py',
            'pc_apps/range_fall/analysis.py',
            'pc_apps/annotator_v2/server.py',
            'pc_apps/annotator_v2/dist/index.html',
            'src/human_fall_detection/core/range_runtime.py',
            'src/inno_lidar_ros/config/ifw192s/ifw192s_azimuth_192x256.csv',
            'launcher/BuildAndRun.ps1',
            'launcher/ConsoleV2Launcher.ps1',
            'config/console.json',
            '启动控制台.cmd',
            '编译并启动.cmd',
            '构建.cmd',
            '局域网诊断.cmd',
            'README_编译与运行.md',
        ):
            self.assertIn(rel, self.paths)

    def test_dev_only_content_excluded(self):
        forbidden = ('data/', 'captures/', 'docs/evidence/', 'console_v2/.tools/',
                     'console_v2/user_data/', 'console_v2/app/runtime/',
                     'console_v2/app/build/', 'console_v2/app/build-dist/',
                     'console_v2/spike/service/payload.zip', 'node_modules/')
        for path in self.paths:
            for prefix in forbidden:
                self.assertFalse(path.startswith(prefix), path)
        self.assertFalse(any(path.endswith('.log') for path in self.paths))

    def test_manifest_matches_files(self):
        total = 0
        for item in self.manifest['files']:
            path = self.outputs[0] / item['path']
            self.assertTrue(path.is_file(), item['path'])
            self.assertEqual(path.stat().st_size, item['bytes'], item['path'])
            self.assertEqual(sha256(path), item['sha256'], item['path'])
            total += item['bytes']
        self.assertEqual(total, json.loads((self.outputs[0] / 'VERSION.json').read_text(
            encoding='utf8'))['totalBytes'])

    def test_zip_matches_manifest(self):
        with zipfile.ZipFile(self.outputs[0].with_suffix('.zip')) as archive:
            self.assertEqual(sorted(archive.namelist()), sorted(self.paths))
            for info in archive.infolist():
                self.assertEqual(info.date_time, (2020, 1, 1, 0, 0, 0))

    def test_powershell_scripts_keep_utf8_bom(self):
        for rel in ('launcher/BuildAndRun.ps1', 'launcher/ConsoleV2Launcher.ps1'):
            data = (self.outputs[0] / rel).read_bytes()
            self.assertEqual(data[:3], b'\xef\xbb\xbf', rel)

    def test_bundle_is_reproducible(self):
        self.assertEqual(sha256(self.outputs[0].with_suffix('.zip')),
                         sha256(self.outputs[1].with_suffix('.zip')))

    def test_existing_output_is_not_overwritten(self):
        result = subprocess.run([sys.executable, '-B', '-W', 'error', str(SCRIPT),
                                 '--out', str(self.outputs[0])],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('不覆盖', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()