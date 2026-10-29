@echo off
setlocal
set "flow=%~dp0..\docs\evidence\2026-10-26_unified_flow"
if not exist "%flow%\run780_final\analysis.json" (
    echo Integrated preview results are missing. See docs\UNIFIED_FLOW.md.
    exit /b 2
)
call "%~dp0start_latest.cmd" --session "%~dp0..\data\sessions\cap_20261017_113516" --frame 690 --analysis "%flow%\run386_final\analysis.json" --analysis "%flow%\run780_final\analysis.json" --gt-root "%~dp0..\pc_apps\annotator_v2\flow_store_dev" %*
exit /b %errorlevel%
