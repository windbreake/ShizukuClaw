# -*- coding: utf-8 -*-
"""
AstrBot Hello World Example Plugin

This is a minimal AstrBot plugin that demonstrates the compatibility layer.
It will be loaded and executed by the ShizukuClaw AstrBot compatibility plugin.
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger


class HelloWorldPlugin(Star):
    """A simple Hello World plugin for AstrBot."""
    
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("HelloWorldPlugin initialized")
    
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """
        Hello World command handler.
        
        Usage: /helloworld
        Response: Hello, {user_name}!
        """
        user_name = event.get_sender_name()
        message_str = event.message_str
        
        logger.info(f"Triggered helloworld command from {user_name}")
        
        # Return plain text result
        yield event.plain_result(f"Hello, {user_name}! This is an AstrBot plugin running in ShizukuClaw!")
    
    @filter.command("astrbot_info")
    async def astrbot_info(self, event: AstrMessageEvent):
        """
        Display AstrBot compatibility info.
        
        Usage: /astrbot_info
        Response: Shows compatibility layer information
        """
        info_text = """
🤖 AstrBot 插件兼容层信息

✅ 兼容层状态: 运行中
📦 插件名称: Hello World 示例
🔧 版本: 1.0.0
🌐 运行环境: ShizukuClaw

这是一个在 ShizukuClaw 中运行的 AstrBot 插件示例。
        """.strip()
        
        yield event.plain_result(info_text)
    
    async def terminate(self):
        """Called when plugin is unloaded."""
        logger.info("HelloWorldPlugin terminated")
