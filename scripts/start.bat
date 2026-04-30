@echo off
chcp 65001 > nul

title Shizuku Nya Bot - Web Launcher
color 0B
cls

set PYTHON_EXE=python
set ROOT_DIR=%~dp0..
set BACKEND_DIR=%ROOT_DIR%\backend
set PYTHONPATH=%BACKEND_DIR%;%PYTHONPATH%
pushd "%ROOT_DIR%"

echo Checking dependencies...
%PYTHON_EXE% -c "import flask, fastapi, uvicorn, openai, mysql.connector, PIL, colorama, requests, docx, pptx, openpyxl, pypdf, reportlab" 2>nul
if errorlevel 1 (
    echo Missing dependencies, installing...
    %PYTHON_EXE% -m pip install -r "%BACKEND_DIR%\requirements.txt"
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

%PYTHON_EXE% -m app.core.launcher_boot

pause
popd
