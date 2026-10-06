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
import http.server
import os
import runpy
import sys
import threading

import webview

# PyInstaller onefile 解压目录优先（console.html / human_replay 被打进 exe）
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _shell_url(port):
    """壳页 URL：相对路径由 pywebview 内置本地 http 服务供给 WebView2。

    不能用 file:// + 查询串：WebView2 会把 '?' 百分号编码进文件名去找，
    直接 ERR_FILE_NOT_FOUND（2026-10-05 实测）。
    """
    return "console.html?replay_port=%d" % port


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
    try:
        srv = m["ThreadingHTTPServer"](("127.0.0.1", m["PORT"]), m["Handler"])
    except OSError:
        # An existing console/replay instance may own 8901; keep each instance's code/data together.
        srv = m["ThreadingHTTPServer"](("127.0.0.1", 0), m["Handler"])
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


if __name__ == "__main__":
    # 冻结后 multiprocessing/线程在 Windows 需显式支持（pyinstaller 约定）
    if getattr(sys, "frozen", False):
        import multiprocessing
        multiprocessing.freeze_support()

    replay_dir, origin = _replay_dir()
    mode = "SOURCE_BYPASS" if origin in ("ENV", "INI") else "PYINSTALLER"
    print("human_replay source=%s" % origin)
    print("resolved root=%s" % replay_dir)
    print("mode=%s" % mode)
    replay_port = _start_replay_server()
    _suppress_edge_save_bubble()
    webview.create_window(
        "总控制台",
        _shell_url(replay_port),
        width=1440, height=900,
        min_size=(900, 600),
    )
    webview.start()  # Win11 自动选 WebView2；无运行时则退回 Edge/IE 并提示
    sys.exit(0)
