#!/bin/bash

# Shizuku Sandbox Setup Script
# 初始化以及增强沙箱环境

set -e

echo "🚀 Shizuku 沙箱初始化脚本"
echo "=================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查环境
echo -e "${YELLOW}[1/5] 检查系统环境...${NC}"

# 检查 Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker 已安装${NC} ($(docker --version))"
else
    echo -e "${RED}✗ Docker 未安装${NC}"
    echo "  建议安装 Docker 以使用生产级隔离"
fi

# 检查 Node.js
if command -v node &> /dev/null; then
    echo -e "${GREEN}✓ Node.js 已安装${NC} ($(node --version))"
else
    echo -e "${YELLOW}⚠ Node.js 未安装${NC}"
    echo "  如需 JavaScript 执行，请安装 Node.js 16+"
fi

# 检查 Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓ Python3 已安装${NC} ($(python3 --version))"
else
    echo -e "${RED}✗ Python3 未安装${NC}"
    exit 1
fi

# 安装 Python 依赖
echo -e "${YELLOW}[2/5] 安装 Python 依赖...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Python 依赖安装完成${NC}"

# 设置 amala-sandbox 运行时
echo -e "${YELLOW}[3/5] 初始化 amala-sandbox 运行时...${NC}"
if [ ! -f "src/runtimes/amala-sandbox/package.json" ]; then
    echo -e "${YELLOW}  创建 amala-sandbox 目录...${NC}"
    mkdir -p src/runtimes/amala-sandbox
fi

if command -v node &> /dev/null; then
    cd src/runtimes/amala-sandbox
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}  安装 Node.js 依赖...${NC}"
        npm install --quiet
        echo -e "${GREEN}✓ amala-sandbox 依赖安装完成${NC}"
    else
        echo -e "${GREEN}✓ amala-sandbox 依赖已存在${NC}"
    fi
    cd ../../..
else
    echo -e "${YELLOW}  ⚠ Node.js 不可用，跳过 amala-sandbox 设置${NC}"
fi

# 创建必要的目录
echo -e "${YELLOW}[4/5] 创建沙箱目录结构...${NC}"
mkdir -p agent_datas/workspace
mkdir -p data/sandbox_logs
mkdir -p logs

# 设置权限
chmod 755 agent_datas/workspace
chmod 755 data
chmod 755 logs

echo -e "${GREEN}✓ 目录结构创建完成${NC}"

# 构建 Docker 镜像 (可选)
echo -e "${YELLOW}[5/5] Docker 镜像设置...${NC}"
if command -v docker &> /dev/null; then
    read -p "是否现在构建 Docker 镜像？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}  构建主应用镜像...${NC}"
        docker build -t shizuku-bot:latest .
        echo -e "${GREEN}✓ 主应用镜像构建完成${NC}"
        
        if [ -f "src/runtimes/amala-sandbox/Dockerfile" ]; then
            echo -e "${YELLOW}  构建 amala-sandbox 镜像...${NC}"
            docker build -t shizuku-js-sandbox:latest src/runtimes/amala-sandbox/
            echo -e "${GREEN}✓ amala-sandbox 镜像构建完成${NC}"
        fi
    fi
else
    echo -e "${YELLOW}  Docker 不可用，跳过镜像构建${NC}"
fi

# 创建初始化完成文件
echo "version: 1.0" > .sandbox-initialized

echo ""
echo "=================================="
echo -e "${GREEN}✓ 沙箱初始化完成！${NC}"
echo ""
echo "下一步："
echo "1. 查看沙箱指南: cat SANDBOX_GUIDE.md"
echo "2. 运行应用: python main.py"
echo "3. 或使用 Docker Compose: docker-compose up -d"
echo ""
echo "可选："
echo "- 查看安全策略: cat src/agent/sandbox_security_policy.json"
echo "- 测试 Python 执行: python -c 'from src.agent.agent_sandbox import AgentSandbox; sb = AgentSandbox(\"agent_datas/workspace\"); print(sb.execute_python_with_details(\"print(2+2)\"))'"
