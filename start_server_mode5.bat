@echo off
cd /d %~dp0backend
echo 5 | python app/main.py
pause
