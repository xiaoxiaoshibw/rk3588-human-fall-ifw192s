@echo off
call "%~dp0start_latest.cmd" --analysis "%~dp0..\docs\evidence\2026-10-26_target_skeleton\replay386_final\analysis.json" --analysis "%~dp0..\docs\evidence\2026-10-26_target_skeleton\replay780_final\analysis.json" %*
exit /b %errorlevel%
