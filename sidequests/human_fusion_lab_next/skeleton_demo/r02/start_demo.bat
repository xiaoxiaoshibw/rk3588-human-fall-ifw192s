@echo off
cd /d "%~dp0\..\..\..\.."
python -B -W error sidequests\human_fusion_lab_next\skeleton_demo\r02\server.py --port 8926
pause
