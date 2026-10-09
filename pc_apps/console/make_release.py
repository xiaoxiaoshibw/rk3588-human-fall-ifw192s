# -*- coding: utf-8 -*-
"""生成发布包 dist/LiDAR_Console.zip（先跑 PyInstaller 产出 dist/Console.exe）。

在本目录运行：
    python -m PyInstaller --noconfirm Console.spec
    python -B make_release.py
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(HERE, "dist", "LiDAR_Console.zip")

FILES = {  # zip 内路径 -> 源文件（相对脚本目录）
    "LiDAR_Console/Console.exe": "dist/Console.exe",
    "LiDAR_Console/console_icon.ico": "console_icon.ico",
    "LiDAR_Console/README.txt": "README.txt",
    "LiDAR_Console/源码/console_gui.py": "console_gui.py",
    "LiDAR_Console/源码/console.html": "console.html",
    "LiDAR_Console/源码/Console.spec": "Console.spec",
    "LiDAR_Console/源码/console_icon.ico": "console_icon.ico",
    "LiDAR_Console/源码/console_test.py": "console_test.py",
    "LiDAR_Console/源码/console_html.test.js": "console_html.test.js",
    "LiDAR_Console/源码/make_console_shortcut.py": "make_console_shortcut.py",
    "LiDAR_Console/源码/make_release.py": "make_release.py",
    # B1 新增 (运行时 datas 已在 exe 内嵌 via spec, 源码副本在 ZIP 里参考用)
    "LiDAR_Console/源码/human_replay/human_track.html": "../human_replay/human_track.html",
    "LiDAR_Console/源码/human_replay/detect_overlay.js": "../human_replay/detect_overlay.js",
    "LiDAR_Console/源码/human_replay/detect_ui.js": "../human_replay/detect_ui.js",
    "LiDAR_Console/源码/human_replay/detect_overlay.test.js": "../human_replay/detect_overlay.test.js",
    "LiDAR_Console/源码/human_replay/human_track_static.test.js": "../human_replay/human_track_static.test.js",
    "LiDAR_Console/源码/human_replay/bg_envelope.json": "../human_replay/bg_envelope.json",
    # 开发工具: 重新生成 bg_envelope.json 的运行脚本
    "LiDAR_Console/源码/human_ml/dump_bg_envelope.py": "../human_ml/dump_bg_envelope.py",
}
DIRS = ("LiDAR_Console/", "LiDAR_Console/captures/", "LiDAR_Console/captures/remote/",
        "LiDAR_Console/源码/human_replay/", "LiDAR_Console/源码/human_ml/")


def main():
    missing = [s for s in FILES.values() if not os.path.isfile(os.path.join(HERE, s))]
    if missing:
        raise SystemExit("缺少文件，请先跑 PyInstaller：%s" % ", ".join(missing))
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for d in DIRS:
            z.writestr(d, b"")
        for name, src in FILES.items():
            z.write(os.path.join(HERE, src), name)
    print("生成 %s (%.1f MB)" % (ZIP, os.path.getsize(ZIP) / 1e6))


if __name__ == "__main__":
    main()
