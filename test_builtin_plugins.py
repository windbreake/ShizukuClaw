# -*- coding: utf-8 -*-
"""Test script for builtin plugins."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.plugin_framework.base import PluginContext
from src.plugin_framework.manager import PluginManager
from src.plugin_framework.builtin_plugins import register as register_builtin


def test_builtin_plugins():
    """Test builtin plugins."""
    
    print("=" * 60)
    print("测试 Builtin 插件")
    print("=" * 60)
    
    # Create manager (which contains registry)
    print("\n[1] 初始化插件管理器...")
    manager = PluginManager(chat_system=None)
    registry = manager.registry
    
    # Register builtin plugins
    print("[2] 注册builtin插件...")
    register_builtin(registry, manager)
    print("✓ Builtin插件已注册")
    
    # Create context
    admin_ctx = PluginContext(
        user_input="test",
        is_admin=True,
        frontend_source="test"
    )
    
    user_ctx = PluginContext(
        user_input="test",
        is_admin=False,
        frontend_source="test"
    )
    
    # Test 1: /plugins command (list plugins)
    print("\n[2] 测试 /plugins 命令...")
    plugins_handler, _ = registry.command_handlers.get("plugins", (None, None))
    if plugins_handler:
        result = plugins_handler(admin_ctx, "")
        print(f"响应: {result.response}")
        print("✓ /plugins 命令成功")
    else:
        print("✗ /plugins 命令未找到")
    
    # Test 2: /echo command
    print("\n[3] 测试 /echo 命令...")
    echo_handler, _ = registry.command_handlers.get("echo", (None, None))
    if echo_handler:
        test_msg = "Hello, World!"
        result = echo_handler(user_ctx, test_msg)
        assert result.response == test_msg, f"Echo failed: {result.response}"
        print(f"输入: '{test_msg}'")
        print(f"输出: '{result.response}'")
        print("✓ /echo 命令成功")
    else:
        print("✗ /echo 命令未找到")
    
    # Test 3: /echo command with empty input
    print("\n[4] 测试 /echo 命令（空输入）...")
    if echo_handler:
        result = echo_handler(user_ctx, "")
        expected = "(empty)"
        assert result.response == expected, f"Echo empty failed: {result.response}"
        print(f"输出: '{result.response}'")
        print("✓ /echo 空输入处理正确")
    
    # Test 4: Time regex rule
    print("\n[5] 测试时间规则 (正则表达式)...")
    time_tests = ["现在几点", "当前时间", "今天几号", "今天日期"]
    
    for test_input in time_tests:
        matched = False
        for regex_rule in registry.regex_rules:
            match = regex_rule.pattern.search(test_input)
            if match:
                result = regex_rule.handler(user_ctx, match)
                print(f"输入: '{test_input}' → {result.response}")
                matched = True
                break
        
        if not matched:
            print(f"✗ '{test_input}' 未匹配规则")
    
    print("✓ 时间规则测试完成")
    
    # Test 5: Response handler (trim spaces)
    print("\n[6] 测试响应处理器 (空格处理)...")
    response_handlers = registry.response_handlers
    if response_handlers:
        handler, _ = response_handlers[0]
        test_response = "Hello    world   \n  this   is    test"
        trimmed = handler(user_ctx, test_response)
        print(f"输入: '{test_response}'")
        print(f"输出: '{trimmed}'")
        print("✓ 响应处理器成功")
    else:
        print("⚠ 没有响应处理器")
    
    # Test 6: /plugins reload (admin only)
    print("\n[7] 测试 /plugins reload 命令...")
    if plugins_handler:
        # Try as non-admin
        result_user = plugins_handler(user_ctx, "reload")
        print(f"非管理员: {result_user.response}")
        assert "权限不足" in result_user.response, "应该拒绝非管理员"
        
        # Try as admin
        result_admin = plugins_handler(admin_ctx, "reload")
        print(f"管理员: {result_admin.response}")
        print("✓ /plugins reload 权限检查正确")
    
    print("\n" + "=" * 60)
    print("所有测试完成！✓")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_builtin_plugins()
    except (AssertionError, ImportError, RuntimeError, ValueError) as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
