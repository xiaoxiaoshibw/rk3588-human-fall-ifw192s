@echo off
call "%~dp0start_latest.cmd" --session "%~dp0..\data\sessions\cap_20261025_203653" --joint-url http://127.0.0.1:62911/ %*
exit /b %errorlevel%
