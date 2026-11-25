@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\BuildAndRun.ps1" -Diagnose
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\ConsoleV2Launcher.ps1" -Diagnose
echo.
pause