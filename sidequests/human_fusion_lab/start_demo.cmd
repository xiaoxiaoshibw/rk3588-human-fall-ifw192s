@echo off
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8791/api/sessions' -TimeoutSec 2; if($r.default -eq 'xgb69_candidate'){ exit 0 }; exit 1 } catch { exit 1 }"
if not errorlevel 1 (
  start "" "http://127.0.0.1:8791"
  exit /b
)
cd /d D:\Code\ldiar\sidequests\human_fusion_lab
start "" "http://127.0.0.1:8791"
node server.js 8791
pause
