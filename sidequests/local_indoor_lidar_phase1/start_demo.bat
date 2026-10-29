@echo off
cd /d "%~dp0\..\.."
set OMP_NUM_THREADS=4
set OPENBLAS_NUM_THREADS=4
set MKL_NUM_THREADS=4
python -B -W error sidequests/local_indoor_lidar_phase1/server.py
pause
