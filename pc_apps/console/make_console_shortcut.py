# -*- coding: utf-8 -*-
"""在桌面创建指向 dist/Console.exe 的快捷方式（exe 内嵌图标，任务栏/桌面统一）。

用法: 先打包 (python -m PyInstaller ... Console.spec), 再跑此脚本。
"""
import os

import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
exe = os.path.join(HERE, "dist", "Console.exe")

shell = win32com.client.Dispatch("WScript.Shell")
lnk = shell.CreateShortcut(os.path.join(DESKTOP, "总控制台.lnk"))
lnk.TargetPath = exe
lnk.WorkingDirectory = os.path.dirname(exe)
lnk.IconLocation = exe + ",0"   # 用 exe 内嵌图标, 跟随 exe 移动
lnk.Description = "LiDAR Console"
lnk.save()
print("OK:", os.path.join(DESKTOP, "总控制台.lnk"), "->", exe)
