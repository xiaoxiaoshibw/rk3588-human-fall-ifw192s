@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\BuildAndRun.ps1" -BuildOnly %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo Build failed with exit code %CODE%.
    pause
)
exit /b %CODE%