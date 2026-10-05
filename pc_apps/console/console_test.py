"""GL-W01 startup: existing replay server must not prevent a new console instance."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

REPLAY = Path(__file__).resolve().parent.parent / 'human_replay'
sys.path.insert(0, str(REPLAY))
import human_replay_lib as H
import console_gui as G


class ConsoleStartupTest(unittest.TestCase):
    def test_shell_url_is_relative_not_file_scheme(self):
        # WebView2 对 file://+查询串报 ERR_FILE_NOT_FOUND（2026-10-05 定位）；
        # 壳页须走 pywebview 内置本地 http 服务，用相对路径交给它处理。
        url = G._shell_url(8901)
        self.assertEqual(url, 'console.html?replay_port=8901')
        self.assertFalse(url.startswith('file://'))

    def test_replay_dir_found_in_source_layout(self):
        # 源码运行时 human_replay 与 console/ 平级（pc_apps/human_replay），
        # 不在 console/ 里（2026-10-05 修复，此前源码启动直接 FileNotFoundError）。
        d = G._replay_dir()
        self.assertTrue(os.path.isfile(os.path.join(d, 'human_replay_lib.py')), d)

    def test_frozen_capture_root_ignores_shortcut_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            source = root / 'pc_apps' / 'human_replay' / 'human_replay_lib.py'
            source.parent.mkdir(parents=True)
            source.touch()
            captures = root / 'captures' / 'remote'
            captures.mkdir(parents=True)
            exe = root / 'pc_apps' / 'console' / 'dist' / 'Console.exe'
            exe.parent.mkdir(parents=True)
            # Empty captures next to dist was the old incorrect shortcut root.
            (exe.parent / 'captures' / 'remote').mkdir(parents=True)
            with patch.object(G.sys, 'executable', str(exe)):
                self.assertEqual(Path(G._frozen_capture_root()), captures)
            portable = Path(tmp) / 'portable' / 'Console.exe'
            with patch.object(G.sys, 'executable', str(portable)):
                self.assertEqual(Path(G._frozen_capture_root()), portable.parent / 'captures' / 'remote')

    def test_occupied_default_port_uses_new_instance_server(self):
        servers = []
        def make(address, handler):
            if address[1] == 8901:
                raise OSError('occupied by existing replay instance')
            server = H.ThreadingHTTPServer(address, handler)
            servers.append(server)
            return server
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C,'DEST_ROOT',tmp), patch.object(G,'HERE',str(REPLAY.parent)):
            namespace = {'C':H.C,'ThreadingHTTPServer':make,'PORT':8901,'Handler':H.Handler}
            with patch.object(G.runpy,'run_path',return_value=namespace):
                port = G._start_replay_server()
                try:
                    self.assertNotEqual(port,8901)
                    with urllib.request.urlopen('http://127.0.0.1:%d/api/leveling/sessions'%port) as response:
                        self.assertIn(b'"sessions": []',response.read())
                    with patch.object(H.sys,'stderr',None):
                        with urllib.request.urlopen('http://127.0.0.1:%d/leveling.html'%port) as response:
                            self.assertEqual(response.status,200)
                finally:
                    for server in servers:
                        server.shutdown();server.server_close()


if __name__=='__main__':
    unittest.main()
