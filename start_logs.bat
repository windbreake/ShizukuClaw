@echo off
set PORT=8888
set URL=http://localhost:%PORT%/logs_page

REM 启动Web服务器
cd /d "%~dp0"
REM 使用模式5启动Web服务器，并设置默认页面
start "LogsServer" cmd /c "set DEFAULT_PAGE=/logs_page&& python main.py 5"

REM 等待服务器启动
timeout /t 5 /nobreak >nul

REM 打开日志页面
start "" %URL%
