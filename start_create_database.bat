@echo off
chcp 65001 >nul
echo =============================
echo   数据库一键创建工具
echo =============================
echo.
echo 正在创建数据库和表...
echo.

cd /d "%~dp0"
python src/create_database.py

echo.
echo 数据库创建完成！
echo.
pause