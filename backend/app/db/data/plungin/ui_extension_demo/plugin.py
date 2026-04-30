# -*- coding: utf-8 -*-
"""Example plugin demonstrating UI extension capabilities."""

import json
import os
from app.plugin_framework.ui_extensions import (
    UIMenuItem, UIPage, UISettingSection, UIWidget, UIModal, ui_registry
)


class UIExtensionDemoPlugin:
    """演示插件UI扩展功能的示例插件。"""
    
    PLUGIN_META = {
        "name": "ui_extension_demo",
        "version": "1.0.0",
        "description": "演示如何安全地扩展UI（菜单、页面、设置等）",
        "author": "ShizukuClaw Team",
        "dependencies": []
    }
    
    def __init__(self):
        self.config = {}
    
    def on_load(self, manager):
        """插件加载时注册UI扩展。"""
        plugin_name = self.PLUGIN_META["name"]
        
        # 加载配置
        self.config = manager.get_plugin_runtime_config(plugin_name)
        if not self.config:
            self.config = self._get_default_config()
            manager.update_plugin_runtime_config(plugin_name, self.config)
        
        # 注册UI扩展
        self._register_ui_extensions()
        
        print(f"[UIExtensionDemo] Loaded and registered UI extensions")
    
    def _register_ui_extensions(self):
        """注册各种UI扩展元素。"""
        plugin_name = self.PLUGIN_META["name"]
        
        # 1. 注册菜单项
        menu_item = UIMenuItem(
            id="demo_page",
            label="演示页面",
            icon="fas fa-star",
            order=50,
            url="/plugins/ui_extension_demo/demo",
            parent_id=None
        )
        ui_registry.register_menu_item(menu_item, plugin_name)
        
        # 2. 注册子菜单项
        submenu_item = UIMenuItem(
            id="demo_settings",
            label="演示设置",
            icon="fas fa-cog",
            order=51,
            url="/plugins/ui_extension_demo/settings",
            parent_id="demo_page"
        )
        ui_registry.register_menu_item(submenu_item, plugin_name)
        
        # 3. 注册页面
        demo_page = UIPage(
            id="demo_page",
            title="演示页面",
            route="/demo",
            content_type="html",
            content=self._get_demo_page_html(),
            requires_auth=True
        )
        ui_registry.register_page(demo_page, plugin_name)
        
        # 4. 注册设置页面
        settings_page = UIPage(
            id="settings_page",
            title="演示设置",
            route="/settings",
            content_type="html",
            content=self._get_settings_page_html(),
            requires_auth=True
        )
        ui_registry.register_page(settings_page, plugin_name)
        
        # 5. 注册设置区块（会显示在系统设置页面中）
        setting_section = UISettingSection(
            id="demo_settings",
            title="演示插件设置",
            description="这是由插件添加的设置项",
            order=200,
            fields=[
                {
                    "key": "feature_enabled",
                    "type": "switch",
                    "label": "启用演示功能",
                    "default": True,
                    "description": "开启或关闭演示功能"
                },
                {
                    "key": "display_mode",
                    "type": "select",
                    "label": "显示模式",
                    "default": "normal",
                    "options": [
                        {"value": "normal", "label": "普通模式"},
                        {"value": "compact", "label": "紧凑模式"},
                        {"value": "expanded", "label": "展开模式"}
                    ]
                },
                {
                    "key": "custom_message",
                    "type": "text",
                    "label": "自定义消息",
                    "default": "Hello from plugin!",
                    "placeholder": "输入自定义消息"
                }
            ]
        )
        ui_registry.register_setting_section(setting_section, plugin_name)
        
        # 6. 注册仪表板小部件
        widget = UIWidget(
            id="stats_widget",
            title="演示统计",
            widget_type="stats",
            position="dashboard",
            order=10,
            config={
                "items": [
                    {"label": "总访问数", "value": "1234", "icon": "fas fa-eye", "color": "primary"},
                    {"label": "活跃用户", "value": "56", "icon": "fas fa-users", "color": "success"},
                    {"label": "今日新增", "value": "12", "icon": "fas fa-plus", "color": "info"}
                ]
            },
            data_source="/api/plugins/ui_extension_demo/stats",
            refresh_interval=60
        )
        ui_registry.register_widget(widget, plugin_name)
        
        # 7. 注册模态框
        modal = UIModal(
            id="demo_modal",
            title="演示模态框",
            size="lg",
            content_type="html",
            content=self._get_modal_content(),
            buttons=[
                {"label": "取消", "class": "btn-secondary", "action": "close"},
                {"label": "确认", "class": "btn-primary", "action": "submit"}
            ]
        )
        ui_registry.register_modal(modal, plugin_name)
        
        # 8. 注册钩子
        ui_registry.register_hook(
            "before_page_render",
            self._on_before_page_render,
            plugin_name
        )
    
    def _get_demo_page_html(self):
        """获取演示页面的HTML内容。"""
        return """
        <div class="container mt-4">
            <div class="row">
                <div class="col-12">
                    <h2><i class="fas fa-star text-warning me-2"></i>演示页面</h2>
                    <p class="text-muted">这是由插件动态添加的页面</p>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">功能一</h5>
                            <p class="card-text">这是一个示例功能卡片</p>
                            <button class="btn btn-primary" onclick="showDemoModal()">
                                打开模态框
                            </button>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">功能二</h5>
                            <p class="card-text">另一个示例功能</p>
                            <button class="btn btn-success">执行操作</button>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">功能三</h5>
                            <p class="card-text">第三个示例功能</p>
                            <button class="btn btn-info">查看详情</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        function showDemoModal() {
            // 调用注册的模态框
            console.log('Opening demo modal...');
            // 实际实现会由前端框架处理
        }
        </script>
        """
    
    def _get_settings_page_html(self):
        """获取设置页面的HTML内容。"""
        return """
        <div class="container mt-4">
            <h2><i class="fas fa-cog me-2"></i>演示设置</h2>
            <p class="text-muted">插件自定义设置页面</p>
            
            <div class="card mt-3">
                <div class="card-body">
                    <form id="plugin-settings-form">
                        <div class="mb-3">
                            <label class="form-label">设置项1</label>
                            <input type="text" class="form-control" placeholder="输入值">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">设置项2</label>
                            <select class="form-select">
                                <option>选项1</option>
                                <option>选项2</option>
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary">保存设置</button>
                    </form>
                </div>
            </div>
        </div>
        """
    
    def _get_modal_content(self):
        """获取模态框内容。"""
        return """
        <div class="modal-body">
            <p>这是一个由插件注册的模态框</p>
            <p>你可以在这里放置任何HTML内容</p>
            <form>
                <div class="mb-3">
                    <label class="form-label">输入内容</label>
                    <input type="text" class="form-control" placeholder="请输入...">
                </div>
            </form>
        </div>
        """
    
    def _on_before_page_render(self, page_id, context):
        """页面渲染前的钩子回调。"""
        print(f"[UIExtensionDemo] Before rendering page: {page_id}")
        # 可以在这里修改context或执行其他操作
        return context
    
    def _get_default_config(self):
        """获取默认配置。"""
        return {
            "feature_enabled": True,
            "display_mode": "normal",
            "custom_message": "Hello from plugin!"
        }
    
    def on_unload(self, manager):
        """插件卸载时清理UI扩展。"""
        plugin_name = self.PLUGIN_META["name"]
        ui_registry.unregister_plugin(plugin_name)
        print(f"[UIExtensionDemo] Unloaded and cleaned up UI extensions")


# 创建插件实例（旧版兼容）
plugin_instance = UIExtensionDemoPlugin()

# 新版插件入口（推荐）
def register(registry, manager):
    """插件注册入口（新版格式）"""
    plugin = UIExtensionDemoPlugin()
    plugin.on_load(manager)
    return plugin


class Plugin:
    """插件类入口（新版格式）"""
    def __init__(self):
        self.instance = UIExtensionDemoPlugin()
    
    def on_load(self, manager):
        return self.instance.on_load(manager)
    
    def on_unload(self, manager):
        return self.instance.on_unload(manager)
