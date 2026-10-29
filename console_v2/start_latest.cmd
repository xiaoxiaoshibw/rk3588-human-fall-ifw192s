@echo off
setlocal
cd /d "%~dp0.."
echo Building and starting the latest Qt console...
python -B -W error "%~dp0app_dev.py" run --isolated-run --qml-file "%~dp0app\native\Main.qml" %*
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
    echo.
    echo Startup failed. The old executable was not launched. See Application logs above.
    pause
)
exit /b %launch_exit%
