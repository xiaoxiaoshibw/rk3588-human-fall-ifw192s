@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\BuildAndRun.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo Build/run failed with exit code %CODE%.
    echo See the messages above and console_v2\user_data\build\toolchain.json.
    pause
)
exit /b %CODE%