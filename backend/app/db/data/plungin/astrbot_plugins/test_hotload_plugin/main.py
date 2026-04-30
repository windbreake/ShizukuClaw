from astrbot.api.star import Star, Context
from astrbot.api.event import AstrMessageEvent, command


class TestHotloadPlugin(Star):
    """Test plugin for hot loading."""
    
    def __init__(self, context: Context):
        super().__init__(context)
        print("[TestHotloadPlugin] Initialized")
    
    async def initialize(self):
        """Called when plugin is loaded."""
        print("[TestHotloadPlugin] Plugin initialized")
    
    async def terminate(self):
        """Called when plugin is unloaded."""
        print("[TestHotloadPlugin] Plugin terminated")
    
    @command("test_hotload")
    async def test_command(self, event: AstrMessageEvent):
        """Test command for hot loaded plugin."""
        await event.plain_result("热加载测试成功！插件正常工作。")
