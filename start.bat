@echo off
REM 设置控制台为UTF-8编码
chcp 65001 > nul

title 傲娇猫娘小雫 - 启动器
color 0B
cls

REM 确保使用正确的Python解释器路径
set PYTHON_EXE=python

REM 检查依赖是否安装 - 使用英文提示避免编码问题
echo Checking dependencies...
%PYTHON_EXE% -c "import flask, fastapi, uvicorn, openai, mysql.connector, PIL, colorama, requests" 2>nul
if errorlevel 1 (
    echo Missing dependencies, installing...
    %PYTHON_EXE% -m pip install flask fastapi uvicorn openai mysql-connector-python pillow colorama requests
)

:main_menu
cls                                  :: 在每次显示主菜单前清屏
echo.
echo ==============================================
echo   🐱 ShizukuNyaBotLauncher- 运行模式选择
echo ==============================================
echo.
echo   0: 映射至Koishi (OpenAI API兼容)
echo   1: 终端聊天模式
echo   2: 沙箱聊天模式 (Web界面)
echo   3: 运行服务诊断
echo   4: 数据库维护工具
echo   5: Start Web Controler
echo   6: 创建数据库和表
echo.
echo ==============================================
echo.
goto get_choice

:get_choice
set /p choice="请选择模式 (0/1/2/3/4/5/6): "

if "%choice%"=="0" goto run_koishi
if "%choice%"=="1" goto run_terminal
if "%choice%"=="2" goto run_sandbox
if "%choice%"=="3" goto run_diagnosis
if "%choice%"=="4" goto run_cleanup
if "%choice%"=="5" goto open_panel
if "%choice%"=="6" goto create_database

echo.
echo 无效选择，请重新输入!
echo.
goto get_choice

:run_koishi
REM 同时启动 Koishi 映射和统一API服务
(
    echo.
    echo 🚀 启动映射模式...
    start "Koishi Server" cmd /k "%PYTHON_EXE% main.py 0"
    if errorlevel 1 (
        echo 警告: Koishi服务启动可能需要一些时间
    ) else (
        echo 启动成功! 日志已在新窗口中显示
    )

    echo.
    echo 🚀 启动统一API服务...
    start "Unified API Server" cmd /k "%PYTHON_EXE% src/unified_api.py"
    if errorlevel 1 (
        echo 警告: 统一API服务启动可能需要一些时间
    ) else (
        echo 启动成功! 日志已在新窗口中显示
    )
)
REM 自动继续，无需按键
goto main_menu

:run_terminal
echo.
echo 🐱 启动终端聊天模式...
start "Terminal Chat" cmd /k "%PYTHON_EXE% main.py 1"
echo 终端聊天模式已在新窗口中启动
REM 自动继续，无需按键
goto main_menu

:run_sandbox
echo.
echo 🌐 启动沙箱聊天模式...
REM 检查端口是否已被占用
%PYTHON_EXE% -c "import socket;s=socket.socket(socket.AF_INET, socket.SOCK_STREAM);result=s.connect_ex(('localhost', 8888));s.close();exit(result)" >nul
if %errorlevel% equ 0 (
    echo 端口8888已被占用，直接打开浏览器
    start "" http://localhost:8888/sandbox
) else (
    start "Sandbox Server" cmd /k "set DEFAULT_PAGE=/sandbox&&set WERKZEUG_RUN_MAIN=true&&%PYTHON_EXE% main.py 2"
    echo 沙箱聊天模式启动命令已执行，请查看新窗口中的日志
    timeout /t 2 /nobreak >nul
    start "" http://localhost:8888/sandbox
)
goto main_menu

:run_diagnosis
echo.
echo 🩺 运行服务诊断...
start "Diagnosis" cmd /k "%PYTHON_EXE% main.py 3"
echo 服务诊断已在新窗口中启动
REM 自动继续，无需按键
goto main_menu

:run_cleanup
echo.
echo 🛠 启动数据库维护工具...
start "数据库维护工具" cmd /k "start_cleanup.bat"
echo 数据库维护工具已在新窗口中启动
REM 自动继续，无需按键
goto main_menu

:create_database
echo.
echo 🛠 创建数据库和表...
start "Create Database" cmd /k "%PYTHON_EXE% src/create_database.py"
echo 数据库创建已在新窗口中启动
REM 自动继续，无需按键
goto main_menu

:open_panel
echo.
echo 🌐 启动 Web 控制面板服务...
REM 检查端口是否已被占用
%PYTHON_EXE% -c "import socket;s=socket.socket(socket.AF_INET, socket.SOCK_STREAM);result=s.connect_ex(('localhost', 8888));s.close();exit(result)" >nul
if %errorlevel% equ 0 (
    echo 端口8888已被占用，直接打开浏览器
    start "" http://localhost:8888/control_panel
) else (
    start "Web Control Panel" cmd /k "set DEFAULT_PAGE=/control_panel&&set WERKZEUG_RUN_MAIN=true&&%PYTHON_EXE% main.py 5"
    echo Web控制面板服务启动命令已执行，请查看新窗口中的日志
    timeout /t 2 /nobreak >nul
    start "" http://localhost:8888/control_panel
)
goto main_menu

:end
echo.
echo 程序已退出...
pause