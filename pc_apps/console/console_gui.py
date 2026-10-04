# -*- coding: utf-8 -*-
"""总控制台 GUI 壳：WebView2 窗口内嵌 console.html（三站切换都在页面里）。

为什么不 Electron：Win11 自带 WebView2 运行时（Edge Chromium 内核），
pywebview 一行起窗口；UI 复用 console.html 单文件，零重复维护。

控制台启动时同时拉起本地回放/标注服务（human_replay_lib，127.0.0.1:8901），
控制台退出即自动关闭。打包成 exe 时 human_replay 目录以 datas 形式内嵌。

启动：python console_gui.py  （或根目录 open_console.bat）
依赖：pip install pywebview
"""
import http.server
import os
import runpy
import sys
import threading

import webview

# PyInstaller onefile 解压目录优先（console.html / human_replay 被打进 exe）
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, "console.html")


def _start_replay_server():
    """同进程起 8901 服务：导入 human_replay_lib 后手动绑端口、serve_forever。

    不用其 main()：main 会 webbrowser.open 弹浏览器，而服务由控制台 iframe 消费。
    """
    sys.path.insert(0, os.path.join(HERE, "human_replay"))
    m = runpy.run_path(os.path.join(HERE, "human_replay", "human_replay_lib.py"))
    # 冻结时数据根不在 _MEIPASS（解压目录），改指 exe 工作目录下的 captures/remote
    if getattr(sys, "frozen", False):
        m["C"].DEST_ROOT = os.path.join(os.getcwd(), "captures", "remote")
    os.makedirs(m["C"].DEST_ROOT, exist_ok=True)
    srv = m["ThreadingHTTPServer"](("127.0.0.1", m["PORT"]), m["Handler"])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("human_replay 服务 http://127.0.0.1:%d/（随控制台退出）" % m["PORT"])


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

    _start_replay_server()
    _suppress_edge_save_bubble()
    webview.create_window(
        "总控制台",
        PAGE,
        width=1440, height=900,
        min_size=(900, 600),
    )
    webview.start()  # Win11 自动选 WebView2；无运行时则退回 Edge/IE 并提示
    sys.exit(0)
