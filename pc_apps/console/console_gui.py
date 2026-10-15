# -*- coding: utf-8 -*-
"""总控制台 GUI 壳：WebView2 窗口内嵌 console.html（三站切换都在页面里）。

为什么不 Electron：Win11 自带 WebView2 运行时（Edge Chromium 内核），
pywebview 一行起窗口；UI 复用 console.html 单文件，零重复维护。

控制台启动时同时拉起本地回放/标注服务（human_replay_lib，127.0.0.1:8901），
控制台退出即自动关闭。打包成 exe 时 human_replay 目录以 datas 形式内嵌。

启动：python console_gui.py  （或根目录 open_console.bat）
依赖：pip install pywebview
"""
import configparser
import errno
import functools
import http.server
import json
import os
import runpy
import socket
import sys
import threading

import webview
import joint_capture

# PyInstaller onefile 解压目录优先（console.html / human_replay 被打进 exe）
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
LEARN_RUN_ID = None


def _shell_url(port, fall_port=None, capture_port=None, real_fall_port=None, plane_port=None):
    """壳页 URL：相对路径由 pywebview 内置本地 http 服务供给 WebView2。

    不能用 file:// + 查询串：WebView2 会把 '?' 百分号编码进文件名去找，
    直接 ERR_FILE_NOT_FOUND（2026-10-05 实测）。
    """
    url = "console.html?replay_port=%d" % port
    url += "&fall_port=%d" % fall_port if fall_port else ""
    url += "&capture_port=%d" % capture_port if capture_port else ""
    url += "&real_fall_port=%d" % real_fall_port if real_fall_port else ""
    if fall_port and LEARN_RUN_ID:
        from urllib.parse import quote
        url += "&learn_run=" + quote(LEARN_RUN_ID, safe="")
    return url + ("&plane_port=%d" % plane_port if plane_port else "")


def _start_plane_pages_server():
    """PLANE-01 证据页面（只读静态子目录 `plane01_pages/`）；缺目录时返回 None，不影响其他入口。"""
    directory = os.path.join(HERE, "plane01_pages")
    if not os.path.isdir(directory):
        return None
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except (OSError, ValueError) as exc:
        print("plane pages unavailable: %s" % exc)
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _start_joint_capture_server():
    root = (_frozen_capture_root() if getattr(sys, "frozen", False)
            else os.path.join(os.path.dirname(os.path.dirname(HERE)), "captures", "remote"))
    root = os.environ.get("HR_DEST_ROOT") or root
    # 拉回用的官方 fetch.py 与回放页取同一份解析结果（ENV/INI 旁路优先，否则打包内嵌）：
    # joint_capture 不再自行猜目录（R6/A2），也保证 SOURCE_BYPASS 下拉回用仓库副本。
    replay_dir, _origin = _replay_dir()
    return joint_capture.start_server(root, os.path.join(HERE, "joint_capture.html"),
                                      fetch_dir=replay_dir)


def _start_fall_server():
    """仓内真人离线原型同进程独立端口；缺数据时保留其他控制台功能。"""
    global LEARN_RUN_ID
    LEARN_RUN_ID = None
    root = (os.path.dirname(os.path.dirname(_frozen_capture_root()))
            if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(HERE)))
    source_dir = os.path.join(root, "sidequests", "human_fusion_lab_next", "pointset", "r01")
    if not os.path.isfile(os.path.join(source_dir, "server.py")):
        return None
    sys.path.insert(0, source_dir)
    try:
        module = runpy.run_path(os.path.join(source_dir, "server.py"))
        # Versioned extension shares the original handler and old root assets.
        learn_dir = os.path.join(root, "sidequests", "human_fusion_lab_next", "learn", "r01")
        learn_pointer = os.path.join(learn_dir, "CURRENT.json")
        if os.path.isfile(learn_pointer):
            with open(learn_pointer, encoding="utf8") as stream:
                learn_run = json.load(stream)
            sys.path.insert(0, learn_dir)
            extension = runpy.run_path(os.path.join(learn_dir, "server.py"))
            module["Handler"] = extension["handler"](learn_run["evidence"], learn_run["manifest_sha256"], learn_run["index_sha256"], learn_run["viewer_sha256"])
            LEARN_RUN_ID = learn_run["run_id"]
        server = module["ThreadingHTTPServer"](("127.0.0.1", 0), module["Handler"])
    except (OSError, ValueError, ImportError, KeyError) as exc:
        print("fall replay unavailable: %s" % exc)
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _start_real_fall_server():
    """启动真实录制 r04 离线回放；缺少数据时不影响其他控制台入口。"""
    root = (os.path.dirname(os.path.dirname(_frozen_capture_root()))
            if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(HERE)))
    source_dir = os.path.join(root, "sidequests", "human_fusion_lab_next", "real_fall", "r04")
    if not os.path.isfile(os.path.join(source_dir, "server.py")):
        return None
    sys.path.insert(0, source_dir)
    try:
        module = runpy.run_path(os.path.join(source_dir, "server.py"))
        server = module["ThreadingHTTPServer"](("127.0.0.1", 0), module["Handler"])
    except (OSError, ValueError, ImportError, KeyError) as exc:
        print("real fall replay unavailable: %s" % exc)
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _is_valid_source_dir(d):
    """源码目录最小校验：目录存在 + 至少含 human_replay_lib.py 与 human_detect.py。"""
    if not d or not os.path.isdir(d):
        return False
    for required in ("human_replay_lib.py", "human_detect.py"):
        if not os.path.isfile(os.path.join(d, required)):
            return False
    return True


def _read_passthrough_ini():
    """读取 console_passthrough.ini（与 exe 同目录），返回 replay_dir 或 None。

    只认 [human_replay] replay_dir 一个键（模板见仓库内 console_passthrough.ini.example）。
    ini 不存在→静默 None；存在但格式错/键缺失/目录无效→各打一条 ASCII WARN
    后返回 None，不 raise，让 _replay_dir() 继续 fallback PACKAGED。
    """
    if not getattr(sys, "frozen", False):
        return None  # 源码跑（python console_gui.py）时跳过 ini，直接用平级仓内目录
    ini_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                            "console_passthrough.ini")
    if not os.path.isfile(ini_path):
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8-sig")
    except configparser.Error as exc:
        print("human_replay INI ignored: bad format (%s)" % exc)
        return None
    try:
        src = parser.get("human_replay", "replay_dir").strip()
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("human_replay INI ignored: no [human_replay] replay_dir key")
        return None
    if not src:
        print("human_replay INI ignored: replay_dir empty")
        return None
    src = os.path.abspath(os.path.expandvars(os.path.expanduser(src)))
    if not os.path.isdir(src):
        print("human_replay INI ignored: directory not found (%s)" % src)
        return None
    if not _is_valid_source_dir(src):
        print("human_replay INI ignored: missing human_replay_lib.py / human_detect.py (%s)" % src)
        return None
    return src


def _replay_dir():
    """返回 (source_dir, origin)：human_replay 目录与其来源标记。

    优先级（配置存在且**有效**才生效，失效自动掉进下一档）：
      1. valid ENV  INNO_HUMAN_REPLAY_DIR
      2. valid INI  console_passthrough.ini 的 [human_replay] replay_dir
      3. PACKAGED   PyInstaller _MEIPASS 内嵌；源码运行时退化为仓内平级目录
    """
    env_dir = os.environ.get("INNO_HUMAN_REPLAY_DIR", "").strip()
    if env_dir:
        env_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(env_dir)))
        if not os.path.isdir(env_dir):
            print("human_replay ENV ignored: directory not found (%s)" % env_dir)
        elif not _is_valid_source_dir(env_dir):
            print("human_replay ENV ignored: missing human_replay_lib.py / human_detect.py (%s)" % env_dir)
        else:
            return env_dir, "ENV"

    ini_dir = _read_passthrough_ini()
    if ini_dir:
        return ini_dir, "INI"

    # 冻结：_MEIPASS 下打包内 human_replay；源码运行：console/ 平级
    for d in (os.path.join(HERE, "human_replay"),
              os.path.join(os.path.dirname(HERE), "human_replay")):
        if _is_valid_source_dir(d):
            return d, "PACKAGED"
    return os.path.join(HERE, "human_replay"), "PACKAGED"


def _start_replay_server():
    """同进程起 8901 服务：导入 human_replay_lib 后手动绑端口、serve_forever。

    不用其 main()：main 会 webbrowser.open 弹浏览器，而服务由控制台 iframe 消费。
    """
    replay_dir, origin = _replay_dir()
    sys.path.insert(0, replay_dir)
    m = runpy.run_path(os.path.join(replay_dir, "human_replay_lib.py"))
    # 仓内 exe 与源码共用捕获目录；移动版的数据放 exe 旁，不依赖快捷方式 cwd。
    if getattr(sys, "frozen", False):
        m["C"].DEST_ROOT = _frozen_capture_root()
    os.makedirs(m["C"].DEST_ROOT, exist_ok=True)
    class ReplayServer(m["ThreadingHTTPServer"]):
        # Windows SO_REUSEADDR permits two listeners on one port; keep each
        # console's pages and data on its own server, including the fallback.
        allow_reuse_address = False
        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    try:
        srv = ReplayServer(("127.0.0.1", m["PORT"]), m["Handler"])
    except OSError as exc:
        if exc.errno not in (errno.EADDRINUSE, errno.EACCES) and getattr(exc, "winerror", None) not in (10048, 10013):
            raise
        # An existing console/replay instance may own 8901; keep each instance's code/data together.
        srv = ReplayServer(("127.0.0.1", 0), m["Handler"])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("human_replay 服务 http://127.0.0.1:%d/（随控制台退出）" % srv.server_address[1])
    return srv.server_address[1]


def _frozen_capture_root():
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    root = exe_dir
    while True:
        if (os.path.isfile(os.path.join(root, "pc_apps", "human_replay", "human_replay_lib.py"))
                and os.path.isdir(os.path.join(root, "captures", "remote"))):
            return os.path.join(root, "captures", "remote")
        parent = os.path.dirname(root)
        if parent == root:
            return os.path.join(exe_dir, "captures", "remote")
        root = parent


def _suppress_edge_save_bubble():
    """Win11 Edge 首次下载弹「保留/删除」气泡挡窗口：往注册表写入默认下载目录。

    每次启动都写（用户手动清空过也能补回）；无 winreg（非 Windows）时跳过。
    """
    try:
        import winreg
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for sub in (r"SOFTWARE\Microsoft\Edge", r"SOFTWARE\Policies\Microsoft\Edge"):
                try:
                    with winreg.CreateKey(root, sub) as k:
                        winreg.SetValueEx(k, "DownloadDirectory", 0, winreg.REG_SZ, downloads)
                except OSError:  # HKLM 无管理员权限时静默跳过，HKCU 已生效
                    pass
    except ImportError:
        pass


def _write_check_report(destination, report):
    """检查报告独占创建（证据不覆盖纪律）；已存在时给可读提示并以 exit 2 退出。

    历史：直接 open(…, 'x') 抛 FileExistsError traceback，重跑检查会被当成崩溃（R6/A8）。
    """
    import json
    try:
        with open(destination, "x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    except FileExistsError:
        print("check report already exists, not overwritten: %s" % destination)
        sys.exit(2)


if __name__ == "__main__":
    # 冻结后 multiprocessing/线程在 Windows 需显式支持（pyinstaller 约定）
    if getattr(sys, "frozen", False):
        import multiprocessing
        multiprocessing.freeze_support()

    if "--check-joint-capture" in sys.argv:
        import json
        import urllib.request
        server, recorder = _start_joint_capture_server()
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/status" % server.server_port) as response:
                report = json.load(response)
            with urllib.request.urlopen("http://127.0.0.1:%d/" % server.server_port) as response:
                page = response.read().decode('utf-8')
            report['page_ok'] = 'USB 摄像头＋雷达联合录制' in page
            replay_dir, _origin = _replay_dir()

            def embedded(*parts):
                with open(os.path.join(*parts), encoding='utf-8') as stream:
                    return stream.read()

            # 内嵌副本必须含“拉回完成 → 自动打开回放”接线：联合页发消息 / 壳页监听 / 回放页读 ?sid
            report['page_version'] = {
                'joint_page': "'joint-completed'" in page,
                'console_shell': '"joint-completed"' in embedded(HERE, 'console.html'),
                'replay_page': '__load_session_sid(qsid)' in embedded(replay_dir, 'index.html'),
            }
            # R6/A4：拉回集成点必须可加载——验证 fetch.py 存在且同进程可调用 process_session
            # （不触网；R5 教训：这条路径此前无任何发布级探针，子进程 bug 直达用户）。
            report['joint_fetch_ok'] = False
            try:
                report['joint_fetch_ok'] = callable(
                    joint_capture.load_fetch(replay_dir).get('process_session'))
            except BaseException as exc:
                report['joint_fetch_error'] = '%s: %s' % (type(exc).__name__, exc)
            report['shell_url'] = _shell_url(8901, capture_port=server.server_port)
            destination = sys.argv[sys.argv.index("--check-joint-capture") + 1]
            _write_check_report(destination, report)
        finally:
            recorder.close()
            server.shutdown()
            server.server_close()
        sys.exit(0 if (report['page_ok'] and report['joint_fetch_ok']
                       and all(report['page_version'].values())) else 1)

    # Scoped candidate-EXE check: no camera, recorder, board or legacy real-fall service.
    if "--check-learn" in sys.argv:
        import urllib.request
        report = {"scope": "HFUS_E0_LEARN_SURFACE_ONLY", "GUI": "NOT_RUN", "capture": "NOT_RUN"}
        try:
            port = _start_fall_server()
            if not port or not LEARN_RUN_ID:
                raise ValueError("No frozen learning run registered")
            base = "http://127.0.0.1:%d/learn/%s/" % (port, LEARN_RUN_ID)
            def fetch_json(suffix):
                with urllib.request.urlopen(base + suffix) as response:
                    return json.load(response)
            catalog = fetch_json("catalog")
            sid = next(iter(catalog["sources"]))
            frame = fetch_json("frame?sid=%s&fi=0&group=G0" % sid)
            source = fetch_json("source?sid=%s&fi=0&row=%d" % (sid, frame["rows"][0]))
            with urllib.request.urlopen(base) as response:
                page_ok = "HFUS" in response.read().decode("utf8")
            report.update(port=port, run_id=LEARN_RUN_ID, manifest_sha256=catalog["manifest_sha256"],
                          viewer_sha256=catalog["viewer_sha256"], U=len(frame["rows"]),
                          actual_fit_count=catalog["models"]["actual_fit_count"],
                          original_bytes_status=source["status"], page_ok=page_ok,
                          shell_url=_shell_url(8901, fall_port=port),
                          ok=page_ok and source["status"] == "ORIGINAL_BYTES_SHA_VERIFIED")
        except Exception as exc:
            report.update(ok=False, error=str(exc))
        _write_check_report(sys.argv[sys.argv.index("--check-learn") + 1], report)
        sys.exit(0 if report["ok"] else 1)

    # Headless release check exercises the frozen servers without opening a GUI.
    if "--check-startup" in sys.argv:
        import json
        import urllib.request
        report = {}
        try:
            report["replay_port"] = _start_replay_server()
            report["fall_port"] = _start_fall_server()
            report["real_fall_port"] = _start_real_fall_server()
            if not report["fall_port"]:
                raise ValueError("pointset replay did not start")
            if not report["real_fall_port"]:
                raise ValueError("real fall replay did not start")
            with urllib.request.urlopen("http://127.0.0.1:%d/api/info" % report["fall_port"]) as response:
                info = json.load(response)
            report["sessions"] = info["sessions"]
            sid = report['sessions'][0]['session_id']
            with urllib.request.urlopen("http://127.0.0.1:%d/api/frame?sid=%s&fi=0&dataset=actions" % (report["fall_port"],sid)) as response:
                frame = json.load(response)
            report['dataset'] = info['dataset']
            report["alarm_frame"] = frame['frame_index']
            report['target_points'] = frame['body_3d'][0]['point_count']
            report["skeleton_nodes"] = len(frame['body_3d'][0]['skeleton']['nodes'])
            report['confirmed_fall'] = frame['posture']['confirmed']
            real_url = "http://127.0.0.1:%d" % report["real_fall_port"]
            with urllib.request.urlopen(real_url + "/api/info") as response:
                real_info = json.load(response)
            real_sid = "cap_20261013_094333"
            empty_sid = "cap_20261013_131958"
            with urllib.request.urlopen(real_url + "/api/frame?sid=%s&i=72" % real_sid) as response:
                real_frame = json.load(response)
            with urllib.request.urlopen(real_url + "/api/frame?sid=%s&i=0" % empty_sid) as response:
                empty_frame = json.load(response)
            events = real_info["sessions"][real_sid]["events"]
            nodes = real_frame["row"]["skeleton"]["nodes"]
            report["real_fall"] = {
                "frames": real_info["sessions"][real_sid]["frames"],
                "frame": real_frame["row"]["frame"],
                "target_points": len(real_frame["target"]),
                "valid_nodes": sum(1 for node in nodes.values() if node.get("valid")),
                "alert_active": real_frame["row"]["alert_active"],
                "event_count": len(events),
                "event_verified": events[0].get("verified") if events else None,
                "empty_observed": empty_frame["row"]["observed"],
                "empty_events": len(real_info["sessions"][empty_sid]["events"]),
            }
            report["shell_url"] = _shell_url(
                report["replay_port"], report["fall_port"],
                real_fall_port=report["real_fall_port"],
            )
            report["plane_port"] = _start_plane_pages_server()
            plane_ok = False
            if report["plane_port"]:
                with urllib.request.urlopen("http://127.0.0.1:%d/index.html" % report["plane_port"]) as response:
                    plane_ok = "PLANE-01" in response.read().decode("utf8")
            report["plane_pages_ok"] = plane_ok
            report["ok"] = (
                report['dataset'] == 'actions' and report['target_points'] > 0
                and report["skeleton_nodes"] == 13 and not report['confirmed_fall']
                and report["real_fall"]["frames"] == 164
                and report["real_fall"]["frame"] == 72
                and report["real_fall"]["valid_nodes"] == 13
                and report["real_fall"]["alert_active"]
                and report["real_fall"]["event_count"] == 1
                and report["real_fall"]["event_verified"] is False
                and not report["real_fall"]["empty_observed"]
                and report["real_fall"]["empty_events"] == 0
                and report["plane_pages_ok"]
            )
        except Exception as exc:
            report.update(ok=False, error=str(exc))
        destination = sys.argv[sys.argv.index("--check-startup") + 1]
        _write_check_report(destination, report)
        sys.exit(0 if report["ok"] else 1)

    replay_dir, origin = _replay_dir()
    mode = "SOURCE_BYPASS" if origin in ("ENV", "INI") else "PYINSTALLER"
    print("human_replay source=%s" % origin)
    print("resolved root=%s" % replay_dir)
    print("mode=%s" % mode)
    replay_port = _start_replay_server()
    fall_port = _start_fall_server()
    real_fall_port = _start_real_fall_server()
    plane_port = _start_plane_pages_server()
    capture_server, recorder = _start_joint_capture_server()
    _suppress_edge_save_bubble()
    webview.create_window(
        "总控制台",
        _shell_url(replay_port, fall_port, capture_server.server_port,
                   real_fall_port=real_fall_port, plane_port=plane_port),
        width=1440, height=900,
        min_size=(900, 600),
    )
    try:
        webview.start()  # Win11 自动选 WebView2；无运行时则退回 Edge/IE 并提示
    finally:
        recorder.close()
        capture_server.shutdown()
        capture_server.server_close()
    sys.exit(0)
