@echo off
REM Console GUI launcher: WebView2 window hosting pc_apps/console/console.html
REM console_gui.py 同进程拉起 8901 回放服务，无需另跑 open_replay.bat
pythonw %~dp0pc_apps\console\console_gui.py
