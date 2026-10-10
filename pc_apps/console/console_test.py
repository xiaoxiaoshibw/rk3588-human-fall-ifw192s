"""GL-W01 startup: existing replay server must not prevent a new console instance."""
import importlib.util
import errno
import json
import os
from pathlib import Path
import sys
import socket
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
        # _replay_dir 返回 (source_dir, origin)，见 console_gui ENV/INI/PACKAGED 分层。
        d, _origin = G._replay_dir()
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
        class TrackedServer(H.ThreadingHTTPServer):
            def __init__(self, address, handler):
                super().__init__(address, handler)
                servers.append(self)
        # Real occupied socket with address reuse enabled, as on the existing
        # Windows replay service. A mocked OSError misses duplicate listeners.
        occupied = H.ThreadingHTTPServer(('127.0.0.1', 0), H.Handler)
        self.assertTrue(occupied.allow_reuse_address)
        self.addCleanup(occupied.server_close)
        occupied_port = occupied.server_address[1]
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C,'DEST_ROOT',tmp), patch.object(G,'HERE',str(REPLAY.parent)):
            namespace = {'C':H.C,'ThreadingHTTPServer':TrackedServer,'PORT':occupied_port,'Handler':H.Handler}
            with patch.object(G.runpy,'run_path',return_value=namespace):
                port = G._start_replay_server()
                try:
                    self.assertNotEqual(port,occupied_port)
                    self.assertFalse(servers[0].allow_reuse_address)
                    self.assertEqual(servers[0].socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR), 0)
                    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                        self.assertEqual(servers[0].socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE), 1)
                    with urllib.request.urlopen('http://127.0.0.1:%d/api/leveling/sessions'%port) as response:
                        self.assertEqual(json.load(response)['sessions'], [])
                    with patch.object(H.sys,'stderr',None):
                        with urllib.request.urlopen('http://127.0.0.1:%d/leveling.html'%port) as response:
                            self.assertEqual(response.status,200)
                finally:
                    for server in servers:
                        server.shutdown();server.server_close()

    def test_unrelated_socket_error_is_not_hidden_by_fallback(self):
        attempts = []
        class InvalidServer:
            def __init__(self, address, handler):
                attempts.append(address)
                raise OSError(errno.EINVAL, 'invalid socket configuration')
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C,'DEST_ROOT',tmp), patch.object(G,'HERE',str(REPLAY.parent)):
            namespace = {'C':H.C,'ThreadingHTTPServer':InvalidServer,'PORT':8901,'Handler':H.Handler}
            with patch.object(G.runpy,'run_path',return_value=namespace):
                with self.assertRaises(OSError) as error:
                    G._start_replay_server()
                self.assertEqual(error.exception.errno,errno.EINVAL)
                self.assertEqual(attempts,[('127.0.0.1',8901)])


if __name__=='__main__':
    unittest.main()
