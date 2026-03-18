#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
搜索API调试脚本
用于诊断搜索API的问题
"""

import json
import os
import sys

import requests

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置
from .config import CONFIG
from .shared_utils import should_search


def debug_search_api():
    """调试搜索API"""
    print("=== 搜索API调试 ===")
    
    # 显示配置信息
    print(f"API密钥: {CONFIG['search_api']['key']}")
    print(f"API地址: {CONFIG['search_api']['base_url']}")
    
    # 测试查询
    query = "人工智能"
    print(f"\n测试查询: {query}")
    
    # 测试是否应该触发搜索
    should_trigger = should_search(query)
    print(f"是否应该触发搜索: {should_trigger}")
    
    # 构建请求
    headers = {
        "Authorization": f"Bearer {CONFIG['search_api']['key']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query,
        "count": 10
    }
    
    print(f"请求头: {headers}")
    print(f"请求体: {payload}")
    
    try:
        # 发送请求
        response = requests.post(
            CONFIG['search_api']['base_url'],
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 检查数据结构
                if "data" in data:
                    if "web_pages" in data["data"]:
                        if "value" in data["data"]["web_pages"]:
                            results = data["data"]["web_pages"]["value"]
                            print(f"\n找到 {len(results)} 个搜索结果")
                            for i, item in enumerate(results[:3]):  # 只显示前3个
                                print(f"结果 {i+1}:")
                                print(f"  标题: {item.get('name', 'N/A')}")
                                print(f"  摘要: {item.get('snippet', 'N/A')}")
                                print(f"  URL: {item.get('url', 'N/A')}")
                        else:
                            print("错误: data.web_pages中没有value字段")
                    else:
                        print("错误: data中没有web_pages字段")
                else:
                    print("错误: 响应中没有data字段")
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                print(f"响应内容: {response.text[:500]}...")
        else:
            print(f"请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
    except Exception as e:
        print(f"其他错误: {e}")
        # 打印详细的错误信息
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    debug_search_api()


if __name__ == "__main__":
    main()