@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:8920/index_v2.html
python -B -m http.server 8920 --bind 127.0.0.1 --directory "%~dp0"
