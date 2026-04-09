@echo off
REM Shizuku Sandbox Setup Script (Windows)
REM 初始化以及增强沙箱环境

setlocal enabledelayedexpansion

echo.
echo 🚀 Shizuku 沙箱初始化脚本 (Windows)
echo ==================================
echo.

REM 检查环境
echo [1/5] 检查系统环境...

REM 检查 Docker
docker --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Docker 已安装
    docker --version
) else (
    echo [WARNING] Docker 未安装
    echo 建议安装 Docker for Windows 以使用生产级隔离
)

REM 检查 Node.js
node --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Node.js 已安装
    node --version
) else (
    echo [WARNING] Node.js 未安装
    echo 如需 JavaScript 执行，请从 nodejs.org 安装 Node.js 16+
)

REM 检查 Python
python --version >nul 2>&1
if !errorlevel! neq 0 (
    python3 --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Python3 未安装
        exit /b 1
    )
)
echo [OK] Python3 已安装
python --version 2>nul || python3 --version

REM 安装 Python 依赖
echo.
echo [2/5] 安装 Python 依赖...
pip install -q -r requirements.txt
if !errorlevel! equ 0 (
    echo [OK] Python 依赖安装完成
) else (
    echo [ERROR] Python 依赖安装失败
    exit /b 1
)

REM 设置 amala-sandbox 运行时
echo.
echo [3/5] 初始化 amala-sandbox 运行时...
if not exist "src\runtimes\amala-sandbox\package.json" (
    echo 创建 amala-sandbox 目录...
    if not exist "src\runtimes" mkdir src\runtimes
    if not exist "src\runtimes\amala-sandbox" mkdir src\runtimes\amala-sandbox
)

where node >nul 2>&1
if !errorlevel! equ 0 (
    if not exist "src\runtimes\amala-sandbox\node_modules" (
        echo 安装 Node.js 依赖...
        cd src\runtimes\amala-sandbox
        call npm install --quiet
        if !errorlevel! equ 0 (
            echo [OK] amala-sandbox 依赖安装完成
        ) else (
            echo [WARNING] amala-sandbox 安装失败，可能需要手动 npm install
        )
        cd ..\..\..
    ) else (
        echo [OK] amala-sandbox 依赖已存在
    )
) else (
    echo [WARNING] Node.js 不可用，跳过 amala-sandbox 设置
)

REM 创建必要的目录
echo.
echo [4/5] 创建沙箱目录结构...
if not exist "agent_datas\workspace" mkdir agent_datas\workspace
if not exist "data\sandbox_logs" mkdir data\sandbox_logs
if not exist "logs" mkdir logs

echo [OK] 目录结构创建完成

REM Docker 镜像设置
echo.
echo [5/5] Docker 镜像设置 (可选)...
where docker >nul 2>&1
if !errorlevel! equ 0 (
    echo.
    set /p BUILD_DOCKER="是否现在构建 Docker 镜像？(y/n): "
    if /i "!BUILD_DOCKER!"=="y" (
        echo 构建主应用镜像...
        docker build -t shizuku-bot:latest .
        if !errorlevel! equ 0 (
            echo [OK] 主应用镜像构建完成
        ) else (
            echo [ERROR] 主应用镜像构建失败
        )
        
        if exist "src\runtimes\amala-sandbox\Dockerfile" (
            echo 构建 amala-sandbox 镜像...
            docker build -t shizuku-js-sandbox:latest src\runtimes\amala-sandbox\
            if !errorlevel! equ 0 (
                echo [OK] amala-sandbox 镜像构建完成
            ) else (
                echo [WARNING] amala-sandbox 镜像构建失败
            )
        )
    )
) else (
    echo [WARNING] Docker 不可用，跳过镜像构建
)

REM 创建初始化完成文件
echo version: 1.0 > .sandbox-initialized

echo.
echo ==================================
echo [SUCCESS] 沙箱初始化完成！
echo ==================================
echo.
echo 下一步：
echo 1. 查看沙箱指南: type SANDBOX_GUIDE.md
echo 2. 运行应用: python main.py
echo 3. 或使用 Docker Compose: docker-compose up -d
echo.
echo 可选：
echo - 查看安全策略: type src\agent\sandbox_security_policy.json
echo.

endlocal
