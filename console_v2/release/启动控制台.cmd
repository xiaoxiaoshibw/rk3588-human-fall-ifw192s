@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\ConsoleV2Launcher.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo ConsoleV2 failed with exit code %CODE%.
    echo See the logs folder printed above.
    pause
)
exit /b %CODE%