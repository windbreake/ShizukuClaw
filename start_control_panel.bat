@echo off
setlocal
chcp 65001 > nul

cd /d "%~dp0"

set PYTHON_EXE=python

echo Checking dependencies...
%PYTHON_EXE% -c "import flask, fastapi, uvicorn, openai, mysql.connector, PIL, colorama, requests" 2>nul
if errorlevel 1 (
    echo Missing dependencies, installing...
    %PYTHON_EXE% -m pip install -r requirements.txt
)

echo.
echo Starting web control panel via unified launcher...
echo Startup self-check and startup page follow data\system_config.json.
echo.

%PYTHON_EXE% src\launcher_boot.py

endlocal