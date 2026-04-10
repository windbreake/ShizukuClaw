# Agent 工作指南 - 项目完成和验证流程

## 问题：为什么 Agent 在处理 snake_game 项目时遇到了困难？

您的 Agent 在处理 snake_game 项目时出现了以下问题：

1. **诊断能力不足**：Agent 提供了诊断命令，但没有实际执行并完整展示结果
2. **理解不够深入**：Agent 没有充分理解项目已经是完整的，而是一直在尝试"修复"
3. **执行反馈缺失**：Agent 提供的代码样本没有被真正执行以验证有效性

## 解决方案：正确的 Agent 工作流程

### 第一步：快速诊断

当收到"完成 X 项目"的请求时，Agent 应该：

```python
# 1. 检查项目目录是否存在
# 2. 列举所有文件
# 3. 读取关键文件的摘要来判断完整性
# 4. 运行自检或验证脚本
```

**正确做法示例：**

```python
import os
import subprocess

# 检查目录
if os.path.exists('snake_game'):
    files = os.listdir('snake_game')
    print("snake_game 目录内容:", files)
    
    # 检查关键文件
    if 'snake.py' in files:
        with open('snake_game/snake.py', 'r') as f:
            content = f.read()
            if 'def main' in content and 'def self_test' in content:
                print("✓ 项目包含关键函数，尝试运行自检...")
                
                # 执行自检
                result = subprocess.run(
                    ['python', 'snake_game/snake.py', '--self-test'],
                    capture_output=True, text=True, timeout=10
                )
                print(f"自检结果: {result.stdout}")
```

### 第二步：验证完整性

使用已准备的验证脚本：

```bash
# 快速验证两个项目
python validate_projects.py

# 或验证单个项目
python test_snake_complete.py
```

**验证脚本检查的内容：**

- ✓ 所有必需文件是否存在
- ✓ 文件大小是否合理（不是空的或太小）
- ✓ 关键函数/类是否存在
- ✓ 代码是否能实际执行
- ✓ 输出是否符合预期

### 第三步：生成完整的真实结果报告

当运行验证失败或找到问题时，**必须包含：**

1. **执行的命令** - 确切的 Python/Shell 命令
2. **完整的输出** - stdout 和 stderr
3. **返回码** - 进程的退出代码
4. **分析** - 输出的含义解释
5. **下一步行动** - 具体的修复方案或结论

**正确的报告格式：**

```
命令: python snake_game/snake.py --self-test
返回码: 0 (成功)
输出:
pygame 2.5.2 (SDL 2.28.3, Python 3.12.3)
[SELF-TEST] pygame_init=ok, snake_move=True, food=(12, 6)

分析: 自检通过，说明项目已完全可用
结论: ✓ snake_game 项目完整，无需修复
```

## Agent 应该避免的错误

### ❌ 错误 1: 提供代码而不执行

```python
# 不要这样做:
print("这是诊断代码:")
print("""
import subprocess
result = subprocess.run([sys.executable, 'snake.py', '--self-test'], ...)
print(result.stdout)
""")
print("(这会运行代码)")
```

**应该这样做：**

```python
# 应该这样:
import subprocess
result = subprocess.run(
    [sys.executable, 'snake_game/snake.py', '--self-test'],
    capture_output=True, text=True, timeout=10
)
print(f"执行结果:\n{result.stdout}")
```

### ❌ 错误 2: 假设项目已解决

如果提供的诊断代码没有被执行或没有看到结果，**不要声称问题已解决**。

总是**验证最终状态**：

```python
# 在任何"已完成"声明前，必须验证
if validate_project_state() == SUCCESS:
    print("✓ 项目已通过验证，任务完成")
else:
    print("❌ 项目仍有问题，继续调试")
```

### ❌ 错误 3: 忽略错误信息

当代码返回非零退出码时，**必须**查看 stderr：

```python
result = subprocess.run(..., capture_output=True, text=True)

if result.returncode != 0:
    print(f"❌ 执行失败!")
    print(f"错误信息: {result.stderr}")
    # 根据错误信息提供解决方案
```

## Agent 应该遵循的最佳实践

### 1. 使用诊断-验证循环

```
诊断 → 运行检查 → 分析结果 → 采取行动 → 再次验证
```

### 2. 保存完整的执行日志

```python
logs = []
logs.append({
    'timestamp': datetime.now().isoformat(),
    'command': cmd,
    'return_code': result.returncode,
    'stdout': result.stdout,
    'stderr': result.stderr,
    'analysis': analysis_text
})
```

### 3. 提供明确的成功/失败标志

```python
# 在报告末尾明确说明
if all_checks_passed:
    print("\n" + "█" * 50)
    print("█  ✓ 任务完成：所有检查通过")
    print("█" * 50)
else:
    print("\n" + "█" * 50)
    print("█  ❌ 任务未完成：存在以下问题:")
    for issue in issues:
        print(f"█    - {issue}")
    print("█" * 50)
```

## 项目完成检查清单

当 Agent 完成一个项目时，应该确保：

- [ ] 所有必需的文件都已创建
- [ ] 文件内容符合规范（不是空的、大小合理）
- [ ] 已运行完整的诊断/验证脚本
- [ ] **真实的执行结果已被获取并显示**
- [ ] 如果有失败，已尝试修复并重新验证
- [ ] 最终报告包含明确的成功/失败标志

## Agent 执行任务的建议流程

```python
def complete_project_task(project_name):
    """Agent 完成项目任务的标准流程"""
    
    # 1. 诊断阶段
    print(f"开始诊断 {project_name}...")
    diagnosis_result = run_diagnosis(project_name)
    
    if diagnosis_result['ok']:
        print(f"✓ {project_name} 已完整，运行最后验证...")
        
        # 2. 验证阶段
        validation_result = run_validation(project_name)
        
        if validation_result['all_passed']:
            print(f"✓✓ {project_name} 通过所有检查，任务完成!")
            return SUCCESS
    
    # 3. 如果有问题，采取修复措施
    print(f"❌ 发现问题，尝试修复...")
    fix_result = apply_fixes(project_name)
    
    # 4. 重新验证
    final_result = run_validation(project_name)
    
    if final_result['all_passed']:
        print(f"✓ {project_name} 修复成功!")
        return SUCCESS
    else:
        print(f"❌ {project_name} 修复未成功，详见日志")
        return FAILURE
```

## 对于当前问题的总结

✅ **现状**：
- snake_game 项目已完全完成并验证通过
- image_card_project 项目已完全完成并验证通过
- 两个项目都包含完整的 README 文档
- 提供了自动验证脚本供快速检查

❌ **之前的问题**：
- Agent 没有实际执行诊断命令
- Agent 没有验证代码是否真的能运行
- Agent 对项目的完整性认识不清

✅ **解决方案**：
- 使用 `validate_projects.py` 进行快速完整性检查
- 使用 `test_snake_complete.py` 进行详细的 snake_game 诊断
- 始终运行验证脚本并展示真实结果，而不是仅提供代码样本

