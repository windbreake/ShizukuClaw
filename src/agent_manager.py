# -*- coding: utf-8 -*-
"""
Agent 管理模块

功能描述:
    负责管理和协调 AI 智能体的核心组件，包括：
    - 规划任务 (AgentPlanner)
    - 管理长期和短期记忆 (AgentMemory)
    - 在沙箱环境中执行代码 (AgentSandbox)
    - 处理任务分解与执行流程
"""
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

    def execute_tool(self, tool_name, args, is_admin=False, frontend_source='control_panel'):
        """Execute a tool call from the LLM"""
        
        # 模式检查
        work_mode_cfg = CONFIG.get('work_mode', {})
        global_work_mode = bool(work_mode_cfg.get('enabled', False))
        sandbox_work_mode = bool(work_mode_cfg.get('sandbox_enabled', False))
        features = work_mode_cfg.get('features', {})
        source = (frontend_source or '').strip().lower()
        work_mode = global_work_mode or (sandbox_work_mode and source == 'sandbox')

        # 1. 娱乐模式限制 (Entertainment Mode)
        # 仅允许只读操作和安全操作 (包括 ask_coder)。禁用写操作和 Python 执行。
        if not work_mode:
            allowed_tools = ['read_file', 'list_dir', 'ask_coder']
            if tool_name not in allowed_tools:
                return "Error: System is in Entertainment Mode. Write operations and code execution are disabled for safety. Please switch to Work Mode to perform these actions."

        # 1.1 工作模式功能开关限制
        tool_feature_map = {
            'write_file': 'allow_file_write',
            'exec_python': 'allow_code_exec',
            'update_plan': 'allow_plan_update',
            'ask_coder': 'allow_coder_tool'
        }
        feature_name = tool_feature_map.get(tool_name)
        if feature_name and not features.get(feature_name, True):
            return f"Error: Feature '{feature_name}' is disabled in Work Mode settings."

        # 2. 权限检查 (Permission Check)
        # 非管理员只能进行读取操作 (即使在工作模式下，也需要管理员权限才能执行危险操作)
        if not is_admin:
            if tool_name in ['write_file', 'exec_python', 'update_plan']:
                 return "Error: Permission Denied. You are not authorized to perform file modifications or code execution."

        # 3. 危险操作三重验证 (Hazardous Operation Verification)
        if tool_name == 'exec_python':
            code = args.get('code', '')
            # For admin, we trust their judgment but block extreme malice
            if 'rm -rf /' in code or 'format c:' in code.lower():
                 return "Error: Extremely dangerous command detected and blocked."


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
            
            elif tool_name == 'ask_coder':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                # Coder is allowed in entertainment mode as it returns text/code suggestion only
                return self.ai_chat_system.coder_agent(args.get('task'), args.get('context', ''))
            
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
                                "filename": {"type": "string", "description": "Filename to save script as"},
                                "confirmation_token": {"type": "string", "description": "Verification token for dangerous operations"}
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
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_coder",
                        "description": "Consult a specialized Coder Agent (e.g. Kimi Coder) for code generation or review.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "Description of the coding task"},
                                "context": {"type": "string", "description": "Existing code context or file content"}
                            },
                            "required": ["task"]
                        }
                    }
                }
            ])
            
        return tools
