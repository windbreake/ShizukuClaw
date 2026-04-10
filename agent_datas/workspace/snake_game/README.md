# snake_game - Pygame 贪吃蛇游戏

## 项目概述

这是一个使用 Pygame 开发的经典贪吃蛇游戏，支持多种运行模式和调试选项。

## 项目结构

```
snake_game/
├── snake.py          # 主游戏代码（6975 字节）
└── requirements.txt  # 依赖配置
```

## 技术栈

- **Python 3.x** - 编程语言
- **pygame==2.5.2** - 游戏开发库

## 功能特性

1. **经典贪吃蛇游戏**
   - 使用方向键控制蛇的移动
   - 吃食物增长，碰到边界或自身游戏结束
   - 实时计分和最高分记录

2. **多种运行模式**
   - **游戏模式**：交互式游戏界面
   - **自检模式**：无显示的自动测试
   - **调试模式**：限制帧数的测试运行

3. **核心类**
   - `Snake`：蛇的逻辑和状态管理
   - `Food`：食物的生成和碰撞检测

## 安装和运行

### 安装依赖

```bash
cd snake_game
pip install -r requirements.txt
```

或手动安装：

```bash
pip install pygame==2.5.2
```

### 运行游戏

**启动交互式游戏：**
```bash
python snake.py
```

**运行自检测试（无窗口）：**
```bash
python snake.py --self-test
```

输出示例：
```
pygame 2.5.2 (SDL 2.28.3, Python 3.12.3)
[SELF-TEST] pygame_init=ok, snake_move=True, food=(12, 6)
```

**运行有限帧数测试（调试用）：**
```bash
python snake.py --max-frames 100
```

## 游戏操作

- **方向键 (↑↓←→)**：控制蛇的移动方向
- **R 键**：游戏结束后重新开始
- **Q 键**：游戏结束后退出游戏
- **关闭窗口**：退出游戏

## 代码架构

### Snake 类
```python
class Snake:
    - __init__()         # 初始化蛇
    - move()            # 移动蛇
    - turn(direction)   # 改变方向
    - grow()            # 增长蛇身
    - reset()           # 重置蛇的状态
    - get_head_position()  # 获取蛇头位置
```

### Food 类
```python
class Food:
    - __init__()        # 初始化食物
    - randomize_position()  # 随机生成位置（避开蛇身）
    - position          # 当前食物位置 (x, y)
```

### 全局参数
```python
WIDTH = 600           # 游戏窗口宽度
HEIGHT = 600          # 游戏窗口高度
GRID_SIZE = 20        # 网格大小
GRID_WIDTH = 30       # 网格列数
GRID_HEIGHT = 30      # 网格行数
FPS = 10              # 游戏帧率
```

## 验证和测试

项目已通过以下测试：

✅ 项目结构检查
✅ Pygame 依赖检查
✅ 模块导入检查
✅ 自检功能测试
✅ 游戏运行测试

要运行完整诊断，使用：
```bash
python ../test_snake_complete.py
```

## 常见问题

### Q: pygame 安装失败怎么办？
**A:** 尝试以下方案：
1. 更新 pip：`pip install --upgrade pip`
2. 使用清华源：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pygame==2.5.2`
3. 如果在 Linux 上，先安装系统依赖：`sudo apt-get install libsdl2-dev`

### Q: 游戏窗口无法打开？
**A:** 检查：
1. 是否在无图形界面的环境（如 SSH）中运行
2. 使用 `--self-test` 模式测试
3. 检查 SDL 库是否正确安装

### Q: 自检返回值非零？
**A:** 这表示 pygame 初始化或蛇的移动有问题，请：
1. 检查 pygame 版本
2. 尝试重新安装 pygame
3. 查看错误消息获取更多信息

## 许可证

MIT License

## 作者

开发者：Shizuku
创建日期：2026-04-10
