"""Real Qt mouse events against the production QML on a read-only LiDAR frame."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'console_v2'


class TestCameraGestures(unittest.TestCase):
    def run_native(self,reload=False):
        out=APP/'.tools/app-evidence'/('camera_'+uuid.uuid4().hex)
        out.mkdir(parents=True)
        print('CAMERA_TEST_OUTPUT '+str(out),flush=True)
        args=[str(APP/'.tools/dotnet/dotnet.exe'),
              os.environ.get('FALL_APP_DLL',str(APP/'app/service/bin/Release/net8.0-windows/AppService.dll')),
              '--host',os.environ.get('FALL_APP_HOST',str(APP/'app/runtime/ConsoleV2.exe')),
              '--session',os.environ.get('FALL_SESSION',str(ROOT/'data/sessions/cap_20261025_203653')),
              '--report',str(out/'service.json')]
        if reload:
            qml=out/'qml';qml.mkdir()
            for name in ('Main.qml','colormap_depth.png','colormap_height.png','colormap_intensity.png'):
                shutil.copy2(APP/'app/native'/name,qml/name)
            args+=['--qml-file',str(qml/'Main.qml'),'--camera-reload-report',str(out/'events.json')]
        else:
            args+=['--camera-report',str(out/'events.json')]
        if not reload and os.environ.get('FALL_QML_FILE'):
            args+=['--qml-file',os.environ['FALL_QML_FILE']]
        done=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=45)
        (out/'stdout.txt').write_bytes(done.stdout);(out/'stderr.txt').write_bytes(done.stderr)
        report=json.loads((out/'events.json').read_text('utf-8'))
        self.assertEqual(report['status'],'PASS',json.dumps(report,ensure_ascii=False))
        self.assertEqual(done.returncode,0,done.stderr.decode(errors='replace'))
        service=json.loads((out/'service.json').read_text('utf-8'))
        self.assertEqual(service['status'],'PASS')
        self.assertEqual(service['jointMutationRequests'],0)
        self.assertEqual(service['directBoardCalls'],0)

    def test_new_drags_pan_mixed_buttons_and_cancellation(self):
        self.run_native()

    def test_reload_preserves_pose_and_ignores_unrelated_files(self):
        self.run_native(reload=True)


if __name__=='__main__':unittest.main()
