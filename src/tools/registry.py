from src.tools.base_tool import Tool

"""
    用于登记工具的类
"""

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def execute(self, name: str, args: dict) -> str:
        if name in self.tools:
            raise  ValueError(f"Tool {name} not found")
        return self.tools[name].run(args)