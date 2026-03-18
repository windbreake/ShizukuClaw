#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI搜索功能测试脚本
用于测试AI搜索网页查找信息的能力
"""

import os
import sys

from .ai_chat_system import AIChatSystem
from .shared_utils import should_search

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_ai_search():
    """测试AI搜索功能"""
    print("=== AI搜索功能测试 ===")
    
    # 初始化AI聊天系统
    ai_system = AIChatSystem()
    
    # 测试用例
    test_cases = [
        "什么是人工智能？",
        "今天天气怎么样？",
        "Python编程语言的最新发展",
        "搜索最近的科技新闻",
        "你知道TensorFlow吗？"
    ]
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {query}")
        print("-" * 40)
        
        # 检查是否应该触发搜索
        should_search_result = ai_system.should_search(query)
        print(f"是否触发搜索: {should_search_result}")
        
        # 使用共享工具检查是否应该触发搜索
        shared_should_search = should_search(query)
        print(f"共享工具是否触发搜索: {shared_should_search}")
        
        if should_search_result:
            # 执行搜索
            search_result = ai_system.search_with_ai_search(query)
            result_preview = (f"搜索结果预览:\n{search_result[:200]}..." 
                           if len(search_result) > 200 else search_result)
            print(result_preview)
            
            # 模拟完整对话流程
            response = ai_system.chat(query)
            print(f"AI回复: {response}")
        else:
            print("该查询不会触发搜索功能")


if __name__ == "__main__":
    test_ai_search()
