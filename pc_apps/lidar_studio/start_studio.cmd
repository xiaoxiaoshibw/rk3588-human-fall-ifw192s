@echo off
setlocal
cd /d "%~dp0\..\.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.12 not found in PATH.
    pause
    exit /b 1
)

echo [LiDAR Studio] Starting server on http://127.0.0.1:8960 ...
start "LiDAR Studio Server" /min cmd /c "python -B pc_apps\lidar_studio\server.py --host 127.0.0.1 --port 8960"

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8960/"
endlocal
