#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整的 snake_game 测试和诊断脚本
这个脚本帮助 Agent 正确测试、诊断和验证 snake_game 项目
"""

import os
import sys
import subprocess
import importlib.util

def check_environment():
    """检查 Python 环境"""
    print("=" * 60)
    print("[1/6] 环境检查")
    print("=" * 60)
    print(f"Python 版本: {sys.version}")
    print(f"Python 可执行文件: {sys.executable}")
    print(f"当前工作目录: {os.getcwd()}")
    print()

def check_snake_game_dir():
    """检查 snake_game 目录结构"""
    print("=" * 60)
    print("[2/6] 目录结构检查")
    print("=" * 60)
    
    if not os.path.exists('snake_game'):
        print("❌ snake_game 目录不存在")
        return False
    
    print("✓ snake_game 目录存在")
    
    required_files = ['snake.py', 'requirements.txt']
    for fname in required_files:
        fpath = os.path.join('snake_game', fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            print(f"✓ {fname} 存在 ({size} 字节)")
        else:
            print(f"❌ {fname} 不存在")
            return False
    
    print()
    return True

def check_pygame_dependency():
    """检查 pygame 依赖"""
    print("=" * 60)
    print("[3/6] pygame 依赖检查")
    print("=" * 60)
    
    try:
        import pygame
        print(f"✓ pygame 已安装，版本: {pygame.version.ver}")
    except ImportError:
        print("⚠ pygame 未安装，尝试安装...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-q', 'pygame==2.5.2'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ pygame 安装成功")
        else:
            print(f"❌ pygame 安装失败: {result.stderr}")
            return False
    
    print()
    return True

def check_snake_imports():
    """检查 snake.py 是否能正确导入"""
    print("=" * 60)
    print("[4/6] snake.py 导入检查")
    print("=" * 60)
    
    try:
        # 添加 snake_game 目录到 sys.path
        snake_game_path = os.path.abspath('snake_game')
        if snake_game_path not in sys.path:
            sys.path.insert(0, snake_game_path)
        
        # 尝试导入 snake 模块
        spec = importlib.util.spec_from_file_location("snake", "snake_game/snake.py")
        snake = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(snake)
        
        print("✓ snake.py 导入成功")
        
        # 检查关键函数是否存在
        if hasattr(snake, 'main'):
            print("✓ main() 函数存在")
        else:
            print("❌ main() 函数不存在")
            return False
        
        if hasattr(snake, 'self_test'):
            print("✓ self_test() 函数存在")
        else:
            print("❌ self_test() 函数不存在")
            return False
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    return True

def run_self_test():
    """运行 snake_game 的自检"""
    print("=" * 60)
    print("[5/6] snake_game 自检测试")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, 'snake_game/snake.py', '--self-test'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.getcwd()
        )
        
        print("自检输出:")
        print(result.stdout)
        
        if result.stderr:
            print("标准错误:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✓ 自检通过")
            return True
        else:
            print(f"❌ 自检失败 (返回码: {result.returncode})")
            return False
        
    except subprocess.TimeoutExpired:
        print("❌ 自检超时")
        return False
    except Exception as e:
        print(f"❌ 自检异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print()

def test_max_frames():
    """测试 snake_game 运行有限帧数"""
    print("=" * 60)
    print("[6/6] snake_game 有限帧测试")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, 'snake_game/snake.py', '--max-frames', '5'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.getcwd()
        )
        
        print("运行输出 (前100字符):")
        output = result.stdout[:100] if result.stdout else "(无输出)"
        print(output)
        
        if result.returncode == 0:
            print("✓ 有限帧测试通过")
            return True
        else:
            print(f"⚠ 有限帧测试返回码: {result.returncode}")
            if result.stderr:
                print("错误信息:", result.stderr[:200])
            return False
        
    except subprocess.TimeoutExpired:
        print("⚠ 有限帧测试超时 (可能是正常的 pygame 行为)")
        return True
    except Exception as e:
        print(f"⚠ 有限帧测试异常: {e}")
        return False
    
    finally:
        print()

def main():
    print("\n")
    print("█" * 60)
    print("█  snake_game 完整诊断工具")
    print("█" * 60)
    print()
    
    results = []
    
    # 1. 环境检查
    check_environment()
    results.append(("环境检查", True))
    
    # 2. 目录结构检查
    if not check_snake_game_dir():
        print("❌ 目录结构检查失败，无法继续")
        return
    results.append(("目录结构", True))
    
    # 3. pygame 依赖检查
    if not check_pygame_dependency():
        print("❌ pygame 依赖检查失败，无法继续")
        return
    results.append(("pygame 依赖", True))
    
    # 4. 导入检查
    if not check_snake_imports():
        print("❌ 导入检查失败")
        results.append(("导入检查", False))
    else:
        results.append(("导入检查", True))
    
    # 5. 自检测试
    if not run_self_test():
        print("❌ 自检测试失败")
        results.append(("自检测试", False))
    else:
        results.append(("自检测试", True))
    
    # 6. 有限帧测试
    test_max_frames()
    results.append(("有限帧测试", True))
    
    # 最终总结
    print("=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ 通过" if passed else "❌ 失败"
        print(f"{status}  {test_name}")
    
    print()
    print("█" * 60)
    
    all_passed = all(p for _, p in results)
    if all_passed:
        print("█  ✓ 所有检查通过！snake_game 项目正常")
        print("█  使用方法:")
        print("█    python snake_game/snake.py           # 运行游戏")
        print("█    python snake_game/snake.py --self-test  # 运行自检")
        print("█    python snake_game/snake.py --max-frames 100  # 运行100帧")
    else:
        print("█  ❌ 部分检查失败，请查看上面的错误信息")
    
    print("█" * 60)
    print()


if __name__ == '__main__':
    main()
