# Shizuku Sandbox 快速参考

## 🎯 快速使用

### Python 代码执行
```python
from src.agent.agent_sandbox import AgentSandbox

sandbox = AgentSandbox('agent_datas/workspace')

# 自动选择 Docker (推荐) > 本地运行时
result = sandbox.execute_python_with_details("""
    print('Hello Sandbox!')
    data = [1, 2, 3, 4, 5]
    print('Sum:', sum(data))
""", filename="my_script.py")

print("✓ 执行成功" if result['ok'] else "✗ 执行失败")
print("输出:", result['stdout'])
print("引擎:", result['engine'])
print("耗时:", result['duration_ms'], "ms")
```

### JavaScript 代码执行
```python
# 需要 Node.js 16+ 和 npm install 在 src/runtimes/amala-sandbox/

result = sandbox.execute_python_with_details("""
    console.log('Hello from vm2!');
    const data = [1, 2, 3, 4, 5];
    const sum = data.reduce((a, b) => a + b, 0);
    console.log('Sum:', sum);
""", filename="my_script.js")

print(result['combined_output'])
```

## 🐳 Docker 部署

### 构建
```bash
# 主应用
docker build -t shizuku-bot:latest .

# JavaScript 沙箱 (可选)
docker build -t shizuku-js-sandbox:latest src/runtimes/amala-sandbox/
```

### 运行 (推荐)
```bash
# 完整环境
docker-compose up -d

# 只运行主应用
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/agent_datas:/app/agent_datas \
  --name shizuku-bot \
  shizuku-bot:latest
```

## 📊 隔离保证

| 功能 | Python(本地) | Python(Docker) | JavaScript(vm2) |
|------|-------------|----------------|-----------------|
| 隔离级别 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 内存限制 | 无 | 256MB | 无 |
| CPU 限制 | 无 | 1.0 核 | 无 |
| 超时 | 30s | 45s | 30s |
| 网络 | 系统默认 | 禁用 | 禁用 |
| 文件 I/O | workspace | workspace | workspace |

## 🔧 配置

编辑 `src/core/config.py` → `work_mode`:
```python
'chat_settings': {
    'sandbox_use_docker_runtime': True,  # Docker > 本地
    'sandbox_show_agent_trace': True,    # 显示 AI 思考过程
}
```

## 📁 关键路径

```
工作目录:     agent_datas/workspace/
外部批准:     data/sandbox_external_approvals.json
执行日志:     data/sandbox_execution_logs.jsonl (可选)
安全事件:     data/sandbox_security_events.log
安全策略:     src/agent/sandbox_security_policy.json
运行时:       src/runtimes/amala-sandbox/
```

## ⚠️ 常见错误

| 错误 | 解决方案 |
|------|--------|
| `Node.js not found` | 安装 Node 16+ 或启用 Docker |
| `Docker connection refused` | 启动 Docker Desktop |
| `vm2 sandbox not initialized` | `npm install` 在 amala-sandbox 目录 |
| `Timeout` | 代码超过 30s (本地) 或 45s (Docker) |
| `No space in /tmp` | 增加 Docker tmpfs 或清理磁盘 |

## 🚨 文件访问提示

代码请求外部文件 → **弹窗显示** → 管理员批准/拒绝 → 执行继续

```
❌ 拒绝的操作:
  - 访问 /etc/passwd
  - 写入 C:\Windows\System32
  - 路径遍历 (../../etc/passwd)

✅ 允许的操作:
  - 读/写 workspace 内文件
  - 批准后访问外部文件
  - JSON/CSV 数据处理
```

## 📚 档文档

- **完整指南**: [SANDBOX_GUIDE.md](SANDBOX_GUIDE.md) (570 行)
- **集成报告**: [SANDBOX_INTEGRATION_REPORT.md](SANDBOX_INTEGRATION_REPORT.md)
- **安全策略**: [src/agent/sandbox_security_policy.json](src/agent/sandbox_security_policy.json)
- **运行时指南**: [src/runtimes/amala-sandbox/README.md](src/runtimes/amala-sandbox/README.md)

## 💾 实用命令

```bash
# 初始化 (首次运行)
Windows:  .\setup-sandbox.bat
Linux:    chmod +x setup-sandbox.sh && ./setup-sandbox.sh

# 测试 JavaScript 沙箱
node src/runtimes/amala-sandbox/runner.js --test

# 查看执行日志
tail -f data/sandbox_execution_logs.jsonl

# 检查安全事件
cat data/sandbox_security_events.log

# Docker 清理
docker system prune --volumes

# 查看资源使用
docker stats shizuku-bot
```

## 🎓 示例代码

### 数据处理
```python
result = sandbox.execute_python_with_details("""
import json
data = [1, 2, 3, 4, 5]
stats = {
    'sum': sum(data),
    'avg': sum(data) / len(data),
    'count': len(data)
}
print(json.dumps(stats))
""")
```

### 图表生成
```python
result = sandbox.create_data_chart(
    data=[[1, 10], [2, 20], [3, 15]],
    chart_type='line',
    output_path='agent_datas/workspace/chart.png'
)
```

### 文档转换
```python
result = sandbox.convert_document(
    source_file='agent_datas/workspace/input.md',
    source_format='md',
    target_format='pdf'
)
```

## 🤝 支持

遇到问题？
1. 查看日志: `logs/`, `data/sandbox_*.log`
2. 阅读指南: [SANDBOX_GUIDE.md](SANDBOX_GUIDE.md)
3. 检查配置: `src/core/config.py`
4. 测试隔离: `node src/runtimes/amala-sandbox/runner.js --test`

---

**最后更新**: 2026-04-10  
**版本**: 1.0 (生产就绪)  
**状态**: ✅ 通过所有测试
