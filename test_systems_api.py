#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统API测试脚本 - 用于测试所有新增系统的API接口
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

BASE_URL = "http://localhost:8888/api/systems"

class APITester:
    """API测试工具类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.test_results = []
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = requests.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = requests.post(url, **kwargs)
            elif method.upper() == 'PUT':
                response = requests.put(url, **kwargs)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, **kwargs)
            else:
                return {'error': f'Unsupported method: {method}'}
            
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def test_logs(self):
        """测试日志API"""
        print("\n" + "=" * 60)
        print("🧪 测试日志系统API")
        print("=" * 60)
        
        # 获取日志
        print("\n1️⃣  获取日志...")
        result = self._request('GET', '/logs?limit=5')
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        if result.get('code') == 0:
            print(f"   日志条数: {result.get('count', 0)}")
        
        return result.get('code') == 0
    
    def test_tasks(self):
        """测试任务系统API"""
        print("\n" + "=" * 60)
        print("🧪 测试定时任务系统API")
        print("=" * 60)
        
        # 列表任务
        print("\n1️⃣  列表任务...")
        result = self._request('GET', '/tasks')
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        if result.get('code') == 0:
            print(f"   任务数: {result.get('count', 0)}")
        
        # 创建任务
        print("\n2️⃣  创建测试任务...")
        tomorrow_3pm = (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0)
        
        task_data = {
            'name': '测试提醒任务',
            'description': '这是一个测试任务',
            'task_type': 'one_time',
            'scheduled_time': tomorrow_3pm.isoformat(),
            'command': 'test_reminder',
            'args': {'message': '这是测试消息'},
            'enabled': False
        }
        
        result = self._request('POST', '/tasks', json=task_data)
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        
        if result.get('code') == 0:
            task_id = result['data']['id']
            print(f"   任务ID: {task_id}")
            
            # 获取任务详情
            print("\n3️⃣  获取任务详情...")
            result = self._request('GET', f'/tasks/{task_id}')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            if result.get('code') == 0:
                task = result['data']
                print(f"   任务名称: {task['name']}")
                print(f"   任务状态: {task['status']}")
            
            # 获取任务结果
            print("\n4️⃣  获取任务执行结果...")
            result = self._request('GET', f'/tasks/{task_id}/results')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            print(f"   结果条数: {result.get('count', 0)}")
            
            # 删除任务
            print("\n5️⃣  删除测试任务...")
            result = self._request('DELETE', f'/tasks/{task_id}')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            
            return True
        
        return False
    
    def test_knowledge_base(self):
        """测试知识库API"""
        print("\n" + "=" * 60)
        print("🧪 测试知识库系统API")
        print("=" * 60)
        
        # 获取分类
        print("\n1️⃣  获取知识库分类...")
        result = self._request('GET', '/knowledge/categories')
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        if result.get('code') == 0:
            categories = result['data']
            print(f"   分类数: {len(categories)}")
        
        # 创建知识条目
        print("\n2️⃣  创建知识库条目...")
        entry_data = {
            'title': '测试知识条目',
            'content': '这是一个测试知识条目的内容',
            'type': 'knowledge',
            'category': '测试',
            'tags': ['test', 'demo'],
            'keywords': ['测试', '演示'],
            'priority': 5
        }
        
        result = self._request('POST', '/knowledge/entries', json=entry_data)
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        
        if result.get('code') == 0:
            entry_id = result['data']['id']
            print(f"   条目ID: {entry_id}")
            
            # 搜索条目
            print("\n3️⃣  搜索知识库条目...")
            result = self._request('GET', '/knowledge/entries/search?q=测试&limit=10')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            print(f"   搜索结果数: {result.get('count', 0)}")
            
            # 获取条目详情
            print("\n4️⃣  获取条目详情...")
            result = self._request('GET', f'/knowledge/entries/{entry_id}')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            if result.get('code') == 0:
                print(f"   条目标题: {result['data']['title']}")
                print(f"   访问次数: {result['data']['access_count']}")
            
            # 删除条目
            print("\n5️⃣  删除测试条目...")
            result = self._request('DELETE', f'/knowledge/entries/{entry_id}')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            
            return True
        
        return False
    
    def test_instructions(self):
        """测试指令系统API"""
        print("\n" + "=" * 60)
        print("🧪 测试自定义指令系统API")
        print("=" * 60)
        
        # 列表人格
        print("\n1️⃣  列表人格配置...")
        result = self._request('GET', '/personalities')
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        if result.get('code') == 0:
            print(f"   人格数: {result.get('count', 0)}")
        
        # 创建人格
        print("\n2️⃣  创建测试人格...")
        personality_data = {
            'name': '测试人格',
            'description': '这是一个测试人格',
            'tone': 'casual',
            'traits': {
                'cheerfulness': 0.7,
                'helpfulness': 0.8
            },
            'emoji_usage': True
        }
        
        result = self._request('POST', '/personalities', json=personality_data)
        print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
        
        if result.get('code') == 0:
            personality_id = result['data']['id']
            print(f"   人格ID: {personality_id}")
            
            # 列表指令
            print("\n3️⃣  列表系统指令...")
            result = self._request('GET', '/instructions?type=system_prompt')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            print(f"   指令数: {result.get('count', 0)}")
            
            # 列表行为规则
            print("\n4️⃣  列表行为规则...")
            result = self._request('GET', '/behavior-rules')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            print(f"   规则数: {result.get('count', 0)}")
            
            # 删除人格
            print("\n5️⃣  删除测试人格...")
            result = self._request('DELETE', f'/personalities/{personality_id}')
            print(f"   状态: {'✅' if result.get('code') == 0 else '❌'}")
            
            return True
        
        return False
    
    def test_system_status(self):
        """测试系统状态API"""
        print("\n" + "=" * 60)
        print("🧪 测试系统状态API")
        print("=" * 60)
        
        print("\n获取系统状态...")
        result = self._request('GET', '/system-status')
        print(f"状态: {'✅' if result.get('code') == 0 else '❌'}")
        
        if result.get('code') == 0:
            data = result['data']
            print("\n📊 系统统计:")
            print(f"   📝 日志条目: {data['logging']['log_entries']}")
            print(f"   ⏰ 定时任务: {data['task_scheduler']['total_tasks']}")
            print(f"   🔌 MCP服务器: {data['mcp']['servers']}")
            print(f"   📚 知识库条目: {data['knowledge_base']['entries']}")
            print(f"   🎭 系统指令: {data['instructions']['instructions']}")
            
            return True
        
        return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n")
        print("╔" + "=" * 58 + "╗")
        print("║" + "系统API综合测试".center(58) + "║")
        print("╚" + "=" * 58 + "╝")
        
        results = {
            '📝 日志系统': self.test_logs(),
            '⏰ 任务系统': self.test_tasks(),
            '📚 知识库系统': self.test_knowledge_base(),
            '🎭 指令系统': self.test_instructions(),
            '📊 系统状态': self.test_system_status()
        }
        
        # 打印测试总结
        print("\n" + "=" * 60)
        print("📋 测试总结")
        print("=" * 60)
        
        passed = 0
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n总计: {passed}/{len(results)} 个测试通过")
        
        if passed == len(results):
            print("\n🎉 所有测试通过！系统运行正常。")
        else:
            print("\n⚠️  部分测试失败，请检查服务器状态。")
        
        return passed == len(results)


def main():
    """主函数"""
    import sys
    
    print("🚀 开始系统API测试...\n")
    
    # 检查服务器连接
    print("🔍 检查服务器连接...")
    try:
        response = requests.get(f"{BASE_URL}/system-status", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器连接成功\n")
        else:
            print("❌ 服务器返回错误，请确保web服务器已启动")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保web服务器已启动在 http://localhost:8888")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        sys.exit(1)
    
    # 运行测试
    tester = APITester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
