@echo off
REM 设置控制台为UTF-8编码
chcp 65001 > nul

title 傲娇猫娘小雫 - Web启动器
color 0B
cls

REM 确保使用正确的Python解释器路径
set PYTHON_EXE=python

REM 检查依赖是否安装
echo Checking dependencies...
%PYTHON_EXE% -c "import flask, fastapi, uvicorn, openai, mysql.connector, PIL, colorama, requests" 2>nul
if errorlevel 1 (
    echo Missing dependencies, installing...
    %PYTHON_EXE% -m pip install flask fastapi uvicorn openai mysql-connector-python pillow colorama requests
)

echo.
echo ==============================================
echo   🐱 ShizukuNyaBot - Web Control Panel
echo ==============================================
echo.
echo 正在启动 Web 控制面板...
echo 服务启动后将自动打开浏览器访问: http://localhost:8888/control_panel
echo.
echo 按 Ctrl+C 可以停止服务
echo.

REM 启动Web服务器 (模式 5: Web Control Panel)
%PYTHON_EXE% main.py 5

pause
