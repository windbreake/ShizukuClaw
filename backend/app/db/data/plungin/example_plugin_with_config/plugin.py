# -*- coding: utf-8 -*-
"""Example plugin demonstrating the configuration schema system."""

import json
import os


class ExamplePlugin:
    """示例插件，展示如何使用配置schema系统。"""
    
    PLUGIN_META = {
        "name": "example_config_plugin",
        "version": "1.0.0",
        "description": "演示插件配置schema系统的示例插件",
        "author": "ShizukuClaw Team",
        "dependencies": []
    }
    
    def __init__(self):
        self.config = {}
    
    def on_load(self, manager):
        """插件加载时调用。"""
        plugin_name = self.PLUGIN_META["name"]
        
        # 加载配置
        self.config = manager.get_plugin_runtime_config(plugin_name)
        
        # 如果配置为空，使用默认值
        if not self.config:
            self.config = self._get_default_config()
            manager.update_plugin_runtime_config(plugin_name, self.config)
        
        print(f"[ExamplePlugin] Loaded with config: {self.config}")
    
    def on_command(self, context, command, args):
        """处理命令。"""
        if command == "show_config":
            return self._handle_show_config()
        elif command == "update_config":
            return self._handle_update_config(args)
        return None
    
    def _handle_show_config(self):
        """显示当前配置。"""
        config_str = json.dumps(self.config, ensure_ascii=False, indent=2)
        return f"当前配置:\n```json\n{config_str}\n```"
    
    def _handle_update_config(self, args):
        """更新配置（示例）。"""
        # 实际使用中，配置应该通过前端UI更新
        return "请使用设置页面修改配置"
    
    def _get_default_config(self):
        """获取默认配置。"""
        return {
            "enabled": True,
            "debug_mode": False,
            "api_key": "",
            "api_url": "https://api.example.com/v1",
            "timeout": 30,
            "default_source": "database",
            "max_results": 50,
            "cache_enabled": True,
            "cache_ttl": 300,
            "retry_count": 3,
            "user_agent": "ShizukuClaw/1.0",
            "theme_color": "#4CAF50",
            "custom_headers": ""
        }
    
    def get_config_schema(self):
        """返回配置schema（可选方法，用于动态获取schema）。"""
        # 通常schema定义在plugin.json中
        # 但也可以通过这个方法动态生成
        schema_path = os.path.join(os.path.dirname(__file__), "plugin.json")
        if os.path.exists(schema_path):
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get("config_schema", {})
            except Exception as e:
                print(f"[ExamplePlugin] Failed to load schema: {e}")
        return {}


# 创建插件实例
plugin_instance = ExamplePlugin()
