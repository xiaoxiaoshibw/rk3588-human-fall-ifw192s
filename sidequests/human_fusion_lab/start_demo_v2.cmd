@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8798/api/sessions' -TimeoutSec 2; if($r.version -eq 2){ exit 0 }; exit 1 } catch { exit 1 }"
if not errorlevel 1 (
  start "" "http://127.0.0.1:8798"
  exit /b
)
start "" "http://127.0.0.1:8798"
node server_v2.js 8798
pause
