@echo off
setlocal
cd /d "%~dp0.."
echo Local read-only range tracking bridge. Qt URL: ws://127.0.0.1:8952
echo No background by default. Use a validated memory background or explicitly declare an empty prefix.
python -B -W error "%~dp0..\pc_apps\range_fall\live_bridge.py" --body-candidates %*
exit /b %errorlevel%
