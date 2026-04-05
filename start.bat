@echo off
chcp 65001 > nul

title Shizuku Nya Bot - Web Launcher
color 0B
cls

set PYTHON_EXE=python

echo Checking dependencies...
%PYTHON_EXE% -c "import flask, fastapi, uvicorn, openai, mysql.connector, PIL, colorama, requests" 2>nul
if errorlevel 1 (
    echo Missing dependencies, installing...
    %PYTHON_EXE% -m pip install flask fastapi uvicorn openai mysql-connector-python pillow colorama requests
)

echo.
echo ==============================================
echo   ShizukuNyaBot - Web Control Panel
echo ==============================================
echo.
echo Starting web control panel...
echo The launcher will run startup self-checks before opening the panel.
echo.
echo Press Ctrl+C to stop the service.
echo.

%PYTHON_EXE% src\launcher_boot.py

pause
