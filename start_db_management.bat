@echo off
setlocal
chcp 65001 > nul

cd /d "%~dp0"
set PYTHON_EXE=python

echo Starting DB management page via unified launcher...
echo Running startup self-check based on launcher settings.
echo.

set DEFAULT_PAGE=/db_console
%PYTHON_EXE% src\launcher_boot.py

endlocal
