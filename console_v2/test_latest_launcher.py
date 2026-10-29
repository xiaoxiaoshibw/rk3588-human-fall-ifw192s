"""The fixed launcher must build current sources and never fall back to an old exe."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import app_dev


class LatestLauncherTests(unittest.TestCase):
    def test_rebuild_while_previous_runtime_is_open_uses_new_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='qt latest ') as tmp:
            root = Path(tmp)
            app = root/'console_v2'
            (app/'app/native').mkdir(parents=True)
            source = app/'app/native/version.txt'
            source.write_text('old')
            launched = []
            def run(argv, **options):
                args = list(map(str, argv))
                if 'AppService.csproj' in ' '.join(args):
                    dest = Path(args[args.index('--output')+1]); dest.mkdir(parents=True,exist_ok=True)
                    (dest/'AppService.dll').write_text(source.read_text())
                elif args[:2] == ['cmake','--build']:
                    dest = Path(args[2]); dest.mkdir(parents=True,exist_ok=True)
                    (dest/'ConsoleV2.exe').write_text(source.read_text())
                elif any(p.endswith('AppService.dll') for p in args):
                    dll = Path(args[1]); host = Path(args[args.index('--host')+1])
                    launched.append((dll,host,dll.read_text(),host.read_text()))
                return subprocess.CompletedProcess(args, 0)
            with patch.object(app_dev,'APP',app), patch.object(app_dev,'ROOT',root), \
                    patch.object(app_dev.subprocess,'run',side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app_dev.main(['run','--isolated-run']), 0)
                old_dll, old_host, _, _ = launched[0]
                # Windows denies overwriting these open files; the second run must not touch them.
                with old_dll.open('rb'), old_host.open('rb'):
                    source.write_text('new')
                    self.assertEqual(app_dev.main(['run','--isolated-run']), 0)
                self.assertEqual(launched[0][2:], ('old','old'))
                self.assertEqual(launched[1][2:], ('new','new'))
                self.assertNotEqual(launched[0][0], launched[1][0])
                self.assertNotEqual(launched[0][1], launched[1][1])
                self.assertEqual(old_dll.read_text(), 'old')
                self.assertEqual(old_host.read_text(), 'old')

    def test_failed_build_never_starts_existing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)/'console_v2'
            (app/'app/runtime').mkdir(parents=True)
            (app/'app/runtime/ConsoleV2.exe').write_text('stale')
            calls = []
            def fail(argv, **options):
                calls.append(list(map(str,argv)))
                return subprocess.CompletedProcess(argv,1)
            with patch.object(app_dev,'APP',app), patch.object(app_dev,'ROOT',Path(tmp)), \
                    patch.object(app_dev.subprocess,'run',side_effect=fail), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app_dev.main(['run','--isolated-run']), 2)
            self.assertEqual(len(calls),1)
            self.assertIn('build',calls[0])
            self.assertEqual((app/'app/runtime/ConsoleV2.exe').read_text(),'stale')

    @unittest.skipUnless(os.name == 'nt', 'Windows batch quoting')
    def test_fixed_cmd_from_another_cwd_and_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='qt launcher space ') as tmp:
            root = Path(tmp)
            app, bin_dir = root/'console_v2', root/'bin'
            app.mkdir(); bin_dir.mkdir()
            (app/'start_latest.cmd').write_bytes((Path(__file__).parent/'start_latest.cmd').read_bytes())
            capture = root/'capture.py'
            capture.write_text('import json,os,sys\nfrom pathlib import Path\n'
                               'Path(os.environ["CAPTURE"]).write_text(json.dumps({"cwd":os.getcwd(),"argv":sys.argv[1:]}))\n')
            # Intercept only this test's python command; no Qt or board access.
            (bin_dir/'python.cmd').write_text('@echo off\n"'+sys.executable+'" "'+str(capture)+'" %*\n')
            captured = root/'args.json'
            env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'], CAPTURE=str(captured))
            command = '"'+os.environ.get('COMSPEC','cmd.exe')+'" /d /s /c ""'+str(app/'start_latest.cmd')+'" --session "session with spaces""'
            result = subprocess.run(command,
                                    cwd=bin_dir,env=env,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            actual = json.loads(captured.read_text())
            self.assertEqual(Path(actual['cwd']),root)
            self.assertIn(str(app/'app_dev.py'),actual['argv'])
            self.assertIn('--isolated-run',actual['argv'])
            self.assertEqual(actual['argv'][-2:],['--session','session with spaces'])


if __name__ == '__main__':
    unittest.main()
