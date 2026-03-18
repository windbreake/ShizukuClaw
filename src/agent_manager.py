# -*- coding: utf-8 -*-
import json
import os
import sys

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_memory import AgentMemory, AgentPlanner
from src.agent_sandbox import AgentSandbox
from src.config import CONFIG

class AgentManager:
    """Core manager for Agent functionality"""
    def __init__(self, ai_chat_system=None):
        self.ai_chat_system = ai_chat_system
        self.memory = AgentMemory(ai_chat_system)
        self.planner = AgentPlanner()
        # Define sandbox root: project_root/agent_datas
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sandbox_root = os.path.join(project_root, 'agent_datas')
        self.sandbox = AgentSandbox(sandbox_root)

    def get_agent_context(self):
        """Builds context string for the LLM"""
        try:
            plan = self.planner.load_plan()
            long_term = self.memory.load_long_term()
            
            context = f"""
[Agent Capabilities]
You have autonomous agent capabilities restricted to the './agent_datas/' workspace.
You can read/write files and execute Python code within this sandbox.

[Current Plan]
{plan}

[Long Term Memory / Summary]
{long_term}
"""
            return context
        except Exception as e:
            return f"[Agent Context Error: {str(e)}]"

    def execute_tool(self, tool_name, args, is_admin=False):
        """Execute a tool call from the LLM"""
        
        # Permission check
        # Non-admins (e.g. QQ bot) can ONLY read, not write or execute
        if not is_admin:
            if tool_name in ['write_file', 'exec_python', 'update_plan']:
                 return "Error: Permission Denied. You are not authorized to perform file modifications or code execution from this interface."

        try:
            if tool_name == 'read_file':
                return self.sandbox.read_file(args.get('path'))
            
            elif tool_name == 'write_file':
                return self.sandbox.write_file(args.get('path'), args.get('content'))
            
            elif tool_name == 'list_dir':
                return self.sandbox.list_dir(args.get('path', '.'))
            
            elif tool_name == 'exec_python':
                return self.sandbox.execute_python(args.get('code'), args.get('filename', 'script.py'))
            
            elif tool_name == 'update_plan':
                self.planner.update_plan(args.get('content'))
                return "Success: Plan updated."
            
            else:
                return f"Error: Unknown tool '{tool_name}'"
                
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"
    
    def record_action(self, role, content):
        self.memory.append_short_term(role, content)

    def get_tools_definitions(self, is_admin=False):
        """Return the list of available tools based on permission"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read file content from the agent workspace (agent_datas)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to file"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path (default .)"}
                        }
                    }
                }
            }
        ]

        if is_admin:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "description": "Write content to a file in the agent workspace",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Relative path to file"},
                                "content": {"type": "string", "description": "Content to write"}
                            },
                            "required": ["path", "content"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "exec_python",
                        "description": "Execute a python script in the workspace",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Python code to execute"},
                                "filename": {"type": "string", "description": "Filename to save script as"}
                            },
                            "required": ["code"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "update_plan",
                        "description": "Update the Plan.md file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "New content for the plan"}
                            },
                            "required": ["content"]
                        }
                    }
                }
            ])
            
        return tools
