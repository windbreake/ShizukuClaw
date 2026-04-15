# Shizuku Sandbox 隔离执行指南

## 概述

Shizuku 现在包含多层隔离沙箱，用于安全执行 AI 生成的代码：

- **Python 代码**: Docker 容器 (python:3.12-alpine) + 严格安全限制
- **JavaScript 代码**: amala-sandbox VM + Docker 容器 (node:20-alpine)

## 快速开始

### 1. 安装依赖

#### 本地开发环境

```bash
# 主项目依赖
pip install -r requirements.txt

# amala-sandbox 运行时
cd src/runtimes/amala-sandbox
npm install
cd ../../..
```

#### Docker 环境 (推荐生产)

```bash
# 构建 Docker 镜像
docker build -t shizuku-bot:latest .

# 构建 amala-sandbox 镜像
docker build -t shizuku-js-sandbox:latest src/runtimes/amala-sandbox/

# 使用 docker-compose
docker-compose up -d
```

### 2. 执行 Python 代码

```python
from src.agent.agent_sandbox import AgentSandbox

sandbox = AgentSandbox('agent_datas/workspace')

# 执行 Python 代码 (自动选择 Docker > 本地)
result = sandbox.execute_python_with_details("""
    print('Hello from sandbox!')
    result = sum([1, 2, 3])
    print(f'Sum: {result}')
""", filename="test_script.py")

print(result['combined_output'])
```

### 3. 执行 JavaScript 代码

```python
# 执行 JavaScript 代码 (通过 amala-sandbox)
result = sandbox.execute_python_with_details("""
    console.log('Hello from amala-sandbox!');
    const result = [1, 2, 3].reduce((a, b) => a + b, 0);
    console.log('Sum:', result);
""", filename="test_script.js")

print(result['combined_output'])
```

## 安全隔离详解

### Python 执行沙箱

#### 本地模式 (开发)
```
┌─────────────────────┐
│   Subprocess 隔离   │
├─────────────────────┤
│ 环境: PYTHONNOUSERSITE=1
│ 超时: 30 秒
│ 工作目录: workspace/
└─────────────────────┘
```

**限制**:
- 禁用用户 site-packages
- 仅限于 workspace 目录
- 无网络访问 (系统级)

#### Docker 模式 (生产)
```
┌──────────────────────────────────┐
│  Docker 容器隔离 (Alpine)         │
├──────────────────────────────────┤
│ 镜像: python:3.12-alpine
│ 超时: 45 秒
│ 内存: 256 MB 硬限制
│ CPU: 1.0 核心限制
│ PID 上限: 64 个进程
├──────────────────────────────────┤
│ 安全特性:
│ - Capabilities: DROP ALL
│ - Root FS: 只读 (除 /tmp)
│ - /tmp: noexec / nosuid
│ - 网络: --network none (完全隔离)
│ - 权限: no-new-privileges
└──────────────────────────────────┘
```

### JavaScript 执行沙箱

```
┌────────────────────────────────────────┐
│    amala-sandbox 虚拟机隔离             │
├────────────────────────────────────────┤
│ 超时: 30 秒 (本地) / 45 秒 (Docker)
│ 递归深度限制: 100
├────────────────────────────────────────┤
│ 禁用 API:
│ ✗ require()              (无外部模块)
│ ✗ process                (无进程访问)
│ ✗ eval() / Function()    (无动态代码)
│ ✗ global / globalThis
│ ✗ __dirname / __filename
│ ✗ setTimeout/setInterval
├────────────────────────────────────────┤
│ 允许 API:
│ ✓ console (捕获输出)
│ ✓ Math, JSON
│ ✓ Array/Object/String/Number/Boolean
│ ✓ Date
└────────────────────────────────────────┘
```

#### 可选: Docker + amala-sandbox (双层隔离)
```
┌────────────────────────────────────────┐
│   Docker 容器 (node:20-alpine)         │
├────────────────────────────────────────┤
│   ↓
├────────────────────────────────────────┤
│   amala-sandbox 虚拟机                  │
├────────────────────────────────────────┤
│ 内存: 256 MB
│ CPU: 1.0 核心
│ PID 上限: 32 个进程
│ 用户: uid=1000 (非 root)
│ Signal 处理: dumb-init
└────────────────────────────────────────┘
```

## 文件系统隔离

### Workspace 目录

所有执行代码的文件操作限制在 `agent_datas/workspace/` 目录内：

```
agent_datas/workspace/
├── temp_script_*.py        (临时 Python 脚本)
├── temp_script_*.js        (临时 JavaScript)
├── output.json
├── chart_*.png
└── data_*.csv
```

### 外部文件访问

**政策**: 默认拒绝 (Deny by default)

步骤：
1. 代码请求外部文件访问
2. 生成随机批准 ID，请求存储为"待定"状态
3. **安全弹窗显示** (与现有 UI 一致)
4. 管理员审查并批准/拒绝
5. 代码执行被阻止直到获得批准
6. 批准记录存储在 `data/sandbox_external_approvals.json`

#### 弹窗样式一致性

新的外部文件访问弹窗确保与现有 control_panel.html 弹窗风格匹配：

```javascript
// chat-sandbox.html - 现有批准框
<div class="approval-box">
  <div class="approval-header">
    ⚠️ 需要外部文件访问权限
  </div>
  <div class="approval-content">
    <div class="request-details">
      <p><strong>文件路径:</strong> /home/user/data.csv</p>
      <p><strong>访问类型:</strong> 读取</p>
      <p><strong>代码片段:</strong> <code>open('/home/user/data.csv')</code></p>
      <p><strong>风险等级:</strong> <span style="color: red;">中等</span></p>
    </div>
  </div>
  <div class="approval-buttons">
    <button onclick="approveAccess('abc123')">批准一次</button>
    <button onclick="approveForever('abc123')">始终批准</button>
    <button onclick="rejectAccess('abc123')">拒绝</button>
  </div>
</div>
```

## 资源限制详解

### 内存管理

| 执行环境 | 限制 | 实施方式 |
|---------|-----|---------|
| 本地 Python | 系统默认 | 无硬限制 |
| Docker Python | 256 MB | cgroups memory.limit_in_bytes |
| Docker JavaScript | 256 MB | cgroups memory.limit_in_bytes |

### CPU 管理

| 执行环境 | 限制 | 实施方式 |
|---------|-----|---------|
| 本地 Python | 无限制 | 系统默认 |
| Docker | 1.0 核心 | cgroups cpuset |

### 时间限制

| 执行环境 | 超时 | 实施方式 |
|---------|-----|---------|
| 本地 Python | 30 秒 | subprocess timeout |
| Docker Python | 45 秒 | subprocess timeout |
| 本地 JavaScript | 30 秒 | amala-sandbox timeout |
| Docker JavaScript | 45 秒 | subprocess timeout |

### 进程限制

| 执行环境 | 最大进程数 | 实施方式 |
|---------|----------|---------|
| 本地 | 无限制 | 系统默认 |
| Docker Python | 64 | cgroups pids.max |
| Docker JavaScript | 32 | cgroups pids.max |

## 监控和日志

### 执行日志

每次代码执行记录：

```json
{
  "timestamp": "2026-04-10T12:34:56.789Z",
  "code_hash": "sha256_of_code",
  "engine": "docker-python:3.12-alpine",
  "return_code": 0,
  "duration_ms": 1234,
  "memory_used_mb": 45,
  "cpu_percent": 15,
  "timed_out": false,
  "stdout_length": 256,
  "stderr_length": 0
}
```

位置: `data/sandbox_execution_logs.jsonl`

### 安全事件

异常记录：

```json
{
  "event_type": "path_traversal_blocked",
  "timestamp": "2026-04-10T12:34:56.789Z",
  "attempted_path": "../../etc/passwd",
  "sandbox_user": "ai_agent",
  "severity": "high"
}
```

位置: `data/sandbox_security_events.log`

## 威胁模型和防御

### 识别的威胁

| 威胁 | 防御 | 状态 |
|-----|------|------|
| 代码注入 | VM + Docker 多层隔离 | ✅ 缓解 |
| 权限提升 | DROP ALL capabilities, 非 root | ✅ 缓解 |
| 资源耗尽 | Memory/CPU/PID 限制 | ✅ 缓解 |
| 文件系统滥用 | Read-only root, workspace 限制 | ✅ 缓解 |
| 网络利用 | --network none | ✅ 防止 |
| Symlink 攻击 | Symlink 解析并验证在 sandbox 内 | ✅ 缓解 |

### 已知限制

⚠️ **该沙箱防止大多数常见攻击，但不是 100% 安全的。** 建议：

1. 对敏感操作启用人工审查
2. 在隔离的主机/VM 中运行 Shizuku
3. 定期更新基础镜像 (python:3.12, node:20)
4. 监控异常的资源使用
5. 定期审计外部文件访问批准

## 故障排除

### Docker 不可用

```python
# 自动降级到本地 Python
result = sandbox.execute_python_with_details(code)
# ⚠️ 警告: 使用本地运行时，隔离较弱
```

### Node.js 不可用

```python
# JavaScript 执行失败并显示有用的错误
result = sandbox.execute_python_with_details(js_code, filename="test.js")
# 错误: Node.js not found. Install Node.js 16+ or enable Docker runtime.
```

### amala-sandbox 未初始化

```bash
# 初始化 amala-sandbox
cd src/runtimes/amala-sandbox
npm install
# 确保 runner.js 存在于该目录
```

### 超时错误

```python
# 代码执行超过限制
# 本地: 30 秒
# Docker: 45 秒
# 确保代码在这些限制内完成
```

## 配置

编辑 `src/agent/sandbox_security_policy.json` 调整：

- timeout_seconds
- memory_limit_mb
- max_execution_depth (JS)
- 批准流程行为
- 审计日志等级

## 最佳实践

✅ **做:**
- 启用 Docker 用于生产代码执行
- 定期审查外部文件访问请求
- 监控资源使用和异常
- 保持基础镜像最新

❌ **不要:**
- 在非容器化环境中运行不受信任的代码
- 给予代码外部文件系统访问权限而不审查
- 禁用安全特性 (下降能力等) 来"加速"
- 信任所有 AI 生成的代码而不检查

## 联系支持

如有问题，请查看：
- 日志: `logs/*.log`
- 安全事件: `data/sandbox_security_events.log`
- 执行日志: `data/sandbox_execution_logs.jsonl`
