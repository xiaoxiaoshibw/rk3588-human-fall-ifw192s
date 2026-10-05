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
}
DIRS = ("LiDAR_Console/", "LiDAR_Console/captures/", "LiDAR_Console/captures/remote/")


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
