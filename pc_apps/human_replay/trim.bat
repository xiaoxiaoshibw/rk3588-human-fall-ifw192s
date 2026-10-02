@echo off
REM HR-03 quick trim entry: src_sid start_seq end_seq
REM   e.g.  trim.bat cap_20261002_165321 1989287 1989294
setlocal
set "HERE=%~dp0"
set "SRC=%HERE%..\..\captures\remote\%~1"
if "%~1"=="" (
  echo Usage: %~nx0 ^<src_sid^> ^<start_seq^> ^<end_seq^>
  exit /b 2
)
if "%~2"=="" ( echo missing ^<start_seq^> & exit /b 2 )
if "%~3"=="" ( echo missing ^<end_seq^> & exit /b 2 )
node "%HERE%trim.js" --src "%SRC%" --start %2 --end %3
endlocal
