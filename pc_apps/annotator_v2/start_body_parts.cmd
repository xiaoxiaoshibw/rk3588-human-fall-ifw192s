@echo off
setlocal
cd /d "%~dp0"
call npm run build
if errorlevel 1 exit /b 1
echo Open http://127.0.0.1:8947/?sid=cap_20261017_113516^&frame=453
python -B -W error server.py --port 8947 --analysis "..\..\docs\evidence\2026-10-26_target_skeleton\replay780_final\analysis.json" --analysis "..\..\docs\evidence\2026-10-26_target_skeleton\replay386_final\analysis.json" --store-root body_store_dev %*
