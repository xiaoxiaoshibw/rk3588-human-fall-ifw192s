@echo off
rem ============================================================
rem HFUS-D04 Demo 一键启动 (方案 A: 本地 http server, 无目录选择)
rem   1) 起  python  demo_server.py    (索引缓存 ./demo_d04_index.json)
rem   2) 起  cmd /c start <url>?AUTO=1  打开浏览器并进入自动加载模式
rem 关闭: 关掉本黑窗口即可
rem ============================================================
setlocal
cd /d "%~dp0.."

set "PY=python"
%PY% --version >nul 2>&1 || set "PY=py"
%PY% --version >nul 2>&1 || (echo [open_demo_d04] 未找到 python。请先装 Python 3.x 并加入 PATH。& pause & exit /b 1)

set "PORT=8907"
echo [open_demo_d04] serving D:\Code\ldiar  (port %PORT%)
start "HFUS-D04 Demo" %PY% "%~dp0..\sidequests\human_fusion_lab_next\d04\demo_server.py" --port %PORT%

rem 等服务器就绪 (最多 ~10s)
for /l %%i in (1,1,20) do (
  powershell -NoProfile -Command "try{ (Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:%PORT%/api/variants -TimeoutSec 1) | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1 && goto :server_ready
  timeout /t 1 /nobreak >nul
)
echo [open_demo_d04] 服务器未及时就绪, 仍尝试打开浏览器...
:server_ready
start "" "http://127.0.0.1:%PORT%/?AUTO=1"
echo [open_demo_d04] 浏览器已打开. 关掉 "HFUS-D04 Demo" 窗口即停止服务器.
endlocal
