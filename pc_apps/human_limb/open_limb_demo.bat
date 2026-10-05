@echo off
REM Limb 支线演示入口：fetch → run limb → 打开 viewer
setlocal
set CAPDIR=D:\Code\ldiar\captures\remote
set PC_APPS=D:\Code\ldiar\pc_apps

echo [1/3] fetch 等待会话（HR-01 复用）...
python %PC_APPS%\human_replay\fetch.py --once || echo fetch 返回非零，继续

echo [2/3] 找出最近一个会话
for /f "delims=" %%a in ('dir /b /ad /o-d "%CAPDIR%\cap_*" 2^>nul') do (
  set SID=%%a
  goto :found
)
:found
if not defined SID (
  echo 没有会话可跑
  exit /b 2
)
echo    会话 %SID%

echo [3/3] limb 检测 + 起 viewer
python %PC_APPS%\human_limb\run_session_limb.py %CAPDIR%\%SID%
REM 起静态 HTTP 服务做 viewer 宿主（浏览器的 webkitdirectory 不需要 HTTP，但保留备用）
start "" /b python -m http.server 8901 --directory D:\Code\ldiar\pc_apps
REM 直接开 viewer 文件
start "" %PC_APPS%\human_limb\limb_viewer.html
echo [OK] 浏览器点开 viewer 后，点「选会话目录」选 %CAPDIR%\%SID% — HR-07 完成
