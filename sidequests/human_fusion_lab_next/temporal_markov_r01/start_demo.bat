@echo off
cd /d "%~dp0\..\..\.."
python -B -W error sidequests/human_fusion_lab_next/temporal_markov_r01/server.py --port 8947
