@echo off
setlocal
cd /d "%~dp0"

echo =============================
echo   Create PostgreSQL DB/tables
echo =============================
echo.
echo Running create_postgresql_database.py ...
echo.

python src\create_postgresql_database.py

echo.
echo Done.
echo.
pause
endlocal
