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
from app.core.config import CONFIG, PROJECT_ROOT

# 添加项目根目录到 sys.path
sys.path.insert(0, PROJECT_ROOT)

from app.agent.agent_memory import AgentMemory, AgentPlanner
from app.agent.agent_sandbox import AgentSandbox

class AgentManager:
    """Core manager for Agent functionality"""
    def __init__(self, ai_chat_system=None, persona_filename=None):
        self.ai_chat_system = ai_chat_system
        self.memory = AgentMemory(ai_chat_system, persona_filename=persona_filename)
        self.planner = AgentPlanner()
        # Define sandbox root: project_root/agent_datas/workspace
        project_root = PROJECT_ROOT
        sandbox_root = os.path.join(project_root, 'agent_datas', 'workspace')
        self.sandbox = AgentSandbox(sandbox_root)

    def set_persona_context(self, persona_filename=None, bootstrap_from_legacy=False):
        return self.memory.set_persona_context(persona_filename, bootstrap_from_legacy=bootstrap_from_legacy)

    def get_agent_context(self, persona_filename=None):
        """Builds context string for the LLM"""
        try:
            if persona_filename is not None:
                self.set_persona_context(persona_filename)
            plan = self.planner.load_plan()
            memory_packet = self.memory.build_context_packet(persona_filename=persona_filename)
            
            context = f"""
[Agent Capabilities]
You have autonomous agent capabilities restricted to the './agent_datas/workspace/' workspace.
You can read/write/delete files and execute Python code within this sandbox.
External file access can be requested but requires explicit user approval when enabled.

[Output Format Requirements]
- Do NOT use DSML, XML, or any markup language format in your responses
- Do NOT use < | DSML | ... > format
- Return plain text, JSON, or natural language only
- When calling tools, use the standard function call format provided by the system
- After tool execution, respond in natural conversational language without any special markup

[Tool Selection Policy]
When the user's intent is to delete, remove, or clear a file in the workspace, always prefer the delete_file tool first.
When the user's intent is to append, add, or continue writing content in an existing file, prefer append_file_content instead of write_file.
Use write_file mainly for full file replacement or initial file creation.
When the user's intent is to delete part of a file, remove a segment, or delete content by position and length, prefer delete_file_content first.
In partial deletion tasks, do not guess and rewrite the whole file unless delete_file_content is not applicable.
When inserting content into an existing file, first read the file, calculate the exact character position, and then call append_file_content with that position.
Do not guess the insertion point when the user asks to write content at a specific location.
Do not use exec_python just to delete a file or to check whether a file exists before deletion.
Use exec_python only when file deletion requires more complex logic that cannot be handled by delete_file.
When creating or converting Office/PDF files (.docx/.pptx/.xlsx/.pdf), do NOT use write_file.
Always use create_document or convert_document for these formats.
When the user explicitly asks to run/execute/debug/check a project, script, or command, you MUST execute it in the sandbox first.
Do not stop at providing sample code or command suggestions only.
Your final answer must include actual execution result (success/failure, output, return code, and next fix if failed).
When the user asks to clone/pull a GitHub repository, use git_clone_repo instead of writing ad-hoc subprocess code in exec_python.
When the user asks to verify GitHub MCP works, use github_mcp_action_test for a real MCP call.
For clone/download status responses, do not output diagnostic code snippets. Report sandbox-relative path, `cd` + `ls` steps, and concise file summary.

[Current Plan]
{plan}

[Memory Packet]
{memory_packet}
"""
            return context
        except Exception as e:
            return f"[Agent Context Error: {str(e)}]"

    def execute_tool(self, tool_name, args, is_admin=False, frontend_source='control_panel', user_input=''):
        """Execute a tool call from the LLM"""
        
        # 模式检查
        work_mode_cfg = CONFIG.get('work_mode', {})
        global_work_mode = bool(work_mode_cfg.get('enabled', False))
        sandbox_work_mode = bool(work_mode_cfg.get('sandbox_enabled', False))
        features = work_mode_cfg.get('features', {})
        chat_settings = work_mode_cfg.get('chat_settings', {})
        source = (frontend_source or '').strip().lower()
        sandbox_agent_autonomous = bool(chat_settings.get('sandbox_agent_autonomous', True))
        sandbox_autonomous_mode = bool(source == 'sandbox' and sandbox_agent_autonomous)
        work_mode = global_work_mode or (sandbox_work_mode and source == 'sandbox') or sandbox_autonomous_mode
        plugin_command_requires_work_mode = bool(features.get('plugin_command_requires_work_mode', False))
        plugin_dev_tools_require_work_mode = bool(features.get('plugin_dev_tools_require_work_mode', True))
        plugin_dev_tools = ['plugin_list', 'plugin_reload', 'plugin_toggle', 'plugin_get_config', 'plugin_set_config']

        # 1. 娱乐模式限制 (Entertainment Mode)
        # 仅允许只读操作和安全操作 (包括 ask_coder)。禁用写操作和 Python 执行。
        if not work_mode:
            if tool_name == 'plugin_command' and plugin_command_requires_work_mode:
                return "Error: plugin_command is restricted to Work Mode by settings."
            if tool_name in plugin_dev_tools and plugin_dev_tools_require_work_mode:
                return "Error: Plugin developer tools are restricted to Work Mode by settings."

            allowed_tools = ['read_file', 'list_dir', 'ask_coder', 'plugin_command']
            if tool_name not in allowed_tools:
                return "Error: System is in Entertainment Mode. Write operations and code execution are disabled for safety. Please switch to Work Mode to perform these actions."

        # 1.1 工作模式功能开关限制
        tool_feature_map = {
            'write_file': 'allow_file_write',
            'append_file_content': 'allow_file_write',
            'delete_file_content': 'allow_file_write',
            'delete_file': 'allow_file_write',
            'create_document': 'allow_file_write',
            'convert_document': 'allow_file_write',
            'exec_python': 'allow_code_exec',
            'git_clone_repo': 'allow_code_exec',
            'github_mcp_action_test': 'allow_code_exec',
            'run_project_debug': 'allow_code_exec',
            'start_web_preview': 'allow_code_exec',
            'generate_data_chart': 'allow_code_exec',
            'update_plan': 'allow_plan_update',
            'ask_coder': 'allow_coder_tool'
        }
        feature_name = tool_feature_map.get(tool_name)
        if feature_name and not features.get(feature_name, True):
            return f"Error: Feature '{feature_name}' is disabled in Work Mode settings."

        # 2. 权限检查 (Permission Check)
        # 非管理员只能进行读取操作 (即使在工作模式下，也需要管理员权限才能执行危险操作)
        if not is_admin:
            if tool_name in [
                'write_file', 'append_file_content', 'delete_file_content', 'delete_file',
                'exec_python', 'git_clone_repo', 'update_plan', 'run_project_debug', 'start_web_preview',
                'github_mcp_action_test',
                'generate_data_chart', 'generate_markdown_diagram', 'resolve_external_approval'
            ]:
                return "Error: Permission Denied. You are not authorized to perform file modifications or code execution."

        # 2.1 强制策略：当用户明确要求“添加/追加/后面写入”时，禁用 write_file，仅允许 append_file_content
        normalized_user_input = str(user_input or '')
        append_intent_keywords = ['添加', '追加', '后面写入']
        if tool_name == 'write_file' and any(k in normalized_user_input for k in append_intent_keywords):
            return "Error: Append intent detected from user message. write_file is blocked by policy. Use append_file_content instead."

        # 3. 危险操作三重验证 (Hazardous Operation Verification)
        if tool_name == 'exec_python':
            code = args.get('code', '')
            # For admin, we trust their judgment but block extreme malice
            if 'rm -rf /' in code or 'format c:' in code.lower():
                return "Error: Extremely dangerous command detected and blocked."


        try:
            if tool_name == 'read_file':
                return self.sandbox.read_file(
                    args.get('path'),
                    external_approval_id=args.get('external_approval_id', '')
                )
            
            elif tool_name == 'write_file':
                return self.sandbox.write_file(
                    args.get('path'),
                    args.get('content'),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'append_file_content':
                return self.sandbox.append_file_content(
                    args.get('path'),
                    args.get('content'),
                    args.get('position'),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'delete_file_content':
                return self.sandbox.delete_file_content(
                    args.get('path'),
                    args.get('position'),
                    args.get('length'),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'delete_file':
                return self.sandbox.delete_file(
                    args.get('path'),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'create_document':
                return self.sandbox.create_document(
                    args.get('output_path'),
                    args.get('content', ''),
                    fmt=args.get('format'),
                    title=args.get('title', ''),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'convert_document':
                return self.sandbox.convert_document(
                    args.get('source_path'),
                    args.get('target_path'),
                    target_format=args.get('target_format'),
                    title=args.get('title', ''),
                    external_approval_id=args.get('external_approval_id', '')
                )
            
            elif tool_name == 'list_dir':
                return self.sandbox.list_dir(
                    args.get('path', '.'),
                    external_approval_id=args.get('external_approval_id', '')
                )
            
            elif tool_name == 'exec_python':
                return self.sandbox.execute_python(args.get('code'), args.get('filename', 'script.py'))

            elif tool_name == 'git_clone_repo':
                return self.sandbox.git_clone_repo(
                    repo_url=args.get('repo_url', ''),
                    target_dir=args.get('target_dir', ''),
                    branch=args.get('branch', ''),
                    depth=args.get('depth', 1),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'github_mcp_action_test':
                return self.sandbox.github_mcp_action_test(
                    owner=args.get('owner', 'modelcontextprotocol'),
                    repo=args.get('repo', 'servers')
                )

            elif tool_name == 'run_project_debug':
                return self.sandbox.run_project_debug(
                    target=args.get('target', '.'),
                    run_tests=bool(args.get('run_tests', True)),
                    start_app=bool(args.get('start_app', False)),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'generate_data_chart':
                return self.sandbox.generate_data_chart(
                    source_path=args.get('source_path'),
                    output_image_path=args.get('output_image_path', 'analysis_chart.png'),
                    chart_type=args.get('chart_type', 'line'),
                    x_column=args.get('x_column', ''),
                    y_column=args.get('y_column', ''),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'generate_markdown_diagram':
                return self.sandbox.generate_markdown_diagram(
                    output_path=args.get('output_path'),
                    diagram_type=args.get('diagram_type', 'flowchart'),
                    title=args.get('title', 'Diagram'),
                    content=args.get('content', '')
                )

            elif tool_name == 'start_web_preview':
                return self.sandbox.start_web_preview(
                    serve_path=args.get('serve_path', '.'),
                    port=args.get('port', 8765),
                    external_approval_id=args.get('external_approval_id', '')
                )

            elif tool_name == 'list_external_approvals':
                return json.dumps(
                    self.sandbox.list_external_approvals(
                        status=args.get('status', 'pending'),
                        limit=args.get('limit', 100)
                    ),
                    ensure_ascii=False,
                    indent=2
                )

            elif tool_name == 'resolve_external_approval':
                return json.dumps(
                    self.sandbox.resolve_external_approval(
                        request_id=args.get('request_id'),
                        approve=bool(args.get('approve', False)),
                        reason=args.get('reason', '')
                    ),
                    ensure_ascii=False,
                    indent=2
                )
            
            elif tool_name == 'update_plan':
                self.planner.update_plan(args.get('content'))
                return "Success: Plan updated."
            
            elif tool_name == 'ask_coder':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                # Coder is allowed in entertainment mode as it returns text/code suggestion only
                return self.ai_chat_system.coder_agent(args.get('task'), args.get('context', ''))

            elif tool_name == 'plugin_list':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                return json.dumps(self.ai_chat_system.get_plugin_status(), ensure_ascii=False, indent=2)

            elif tool_name == 'plugin_reload':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                return json.dumps(self.ai_chat_system.reload_plugins(), ensure_ascii=False, indent=2)

            elif tool_name == 'plugin_toggle':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                plugin_name = args.get('plugin_name') or ''
                enabled = bool(args.get('enabled', True))
                policy = {'enabled': enabled}
                return json.dumps(self.ai_chat_system.update_plugin_policy(plugin_name, policy), ensure_ascii=False, indent=2)

            elif tool_name == 'plugin_get_config':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                plugin_name = args.get('plugin_name') or ''
                return json.dumps(self.ai_chat_system.get_plugin_runtime_config(plugin_name), ensure_ascii=False, indent=2)

            elif tool_name == 'plugin_set_config':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                plugin_name = args.get('plugin_name') or ''
                config_data = args.get('config', {})
                return json.dumps(self.ai_chat_system.update_plugin_runtime_config(plugin_name, config_data), ensure_ascii=False, indent=2)

            elif tool_name == 'plugin_command':
                if not self.ai_chat_system:
                    return "Error: Chat system not initialized."
                command_text = args.get('command_text') or ''
                return json.dumps(self.ai_chat_system.run_plugin_command(command_text, is_admin=is_admin, frontend_source=frontend_source), ensure_ascii=False, indent=2)

            elif tool_name == 'get_long_term_memory':
                persona_filename = (args.get('persona_filename') or '').strip() or None
                include_meta = bool(args.get('include_meta', True))
                payload = self.memory.get_long_term_memory_view(persona_filename=persona_filename, include_meta=include_meta)
                return json.dumps(payload, ensure_ascii=False, indent=2)
            
            else:
                return f"Error: Unknown tool '{tool_name}'"
                
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"
    
    def record_action(self, role, content, persona_filename=None):
        self.memory.append_short_term(role, content, persona_filename=persona_filename)

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
                            "path": {"type": "string", "description": "Relative path to file"},
                            "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
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
                            "path": {"type": "string", "description": "Directory path (default .)"},
                            "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "plugin_command",
                    "description": "Invoke a plugin command string like /plugins, /echo hello, /kemono_crawl <url>",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command_text": {"type": "string", "description": "Command text to run"}
                        },
                        "required": ["command_text"]
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
                                "content": {"type": "string", "description": "Content to write"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["path", "content"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "append_file_content",
                        "description": "Insert content into a file in the agent workspace at a given character position; if position is omitted, append to the end",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Relative path to file"},
                                "content": {"type": "string", "description": "Content to insert"},
                                "position": {"type": "integer", "description": "Character offset where content should be inserted"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["path", "content"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_file_content",
                        "description": "Delete content from a file by character position and length",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Relative path to file"},
                                "position": {"type": "integer", "description": "Character offset where deletion starts"},
                                "length": {"type": "integer", "description": "Number of characters to delete"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["path", "position", "length"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_file",
                        "description": "Delete a file in the agent workspace",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Relative path to file"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_document",
                        "description": "Create text/office/pdf files safely. Supports txt, md, py, json, docx, pptx, xlsx, pdf.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "output_path": {"type": "string", "description": "Relative output file path"},
                                "format": {"type": "string", "description": "Target format, e.g. docx/pptx/xlsx/pdf/txt/md/json/py"},
                                "title": {"type": "string", "description": "Optional title for document formats"},
                                "content": {"description": "Document content. String or JSON object/array for json", "oneOf": [{"type": "string"}, {"type": "object"}, {"type": "array"}]},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["output_path", "content"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "convert_document",
                        "description": "Convert among txt/md/py/json/docx/pptx/xlsx/pdf in workspace.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "source_path": {"type": "string", "description": "Relative source file path"},
                                "target_path": {"type": "string", "description": "Relative target file path"},
                                "target_format": {"type": "string", "description": "Optional explicit target format, inferred from target_path if omitted"},
                                "title": {"type": "string", "description": "Optional title for target document formats"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["source_path", "target_path"]
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
                        "name": "git_clone_repo",
                        "description": "Clone a Git repository into the agent workspace. Prefer this over exec_python for pull/clone tasks.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "repo_url": {"type": "string", "description": "Repository URL (https://..., git@..., ssh://...)"},
                                "target_dir": {"type": "string", "description": "Optional target directory under workspace"},
                                "branch": {"type": "string", "description": "Optional branch name"},
                                "depth": {"type": "integer", "description": "Clone depth, default 1"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["repo_url"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "github_mcp_action_test",
                        "description": "Run a real GitHub MCP test: initialize, tools/list, and one read-only tools/call action.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string", "description": "GitHub owner/org, default modelcontextprotocol"},
                                "repo": {"type": "string", "description": "GitHub repo name, default servers"}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "run_project_debug",
                        "description": "Run compile/test diagnostics in the workspace to iterate debugging until project becomes runnable.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string", "description": "Project directory path, default '.'"},
                                "run_tests": {"type": "boolean", "description": "Whether to run pytest after py_compile"},
                                "start_app": {"type": "boolean", "description": "For runnable projects, attempt to start app after successful build."},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "generate_data_chart",
                        "description": "Analyze csv/json/xlsx data and generate chart image in workspace.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "source_path": {"type": "string", "description": "Input data file path"},
                                "output_image_path": {"type": "string", "description": "Output image path (.png recommended)"},
                                "chart_type": {"type": "string", "description": "line/bar/scatter"},
                                "x_column": {"type": "string", "description": "X axis column name"},
                                "y_column": {"type": "string", "description": "Y axis columns, comma-separated"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            },
                            "required": ["source_path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "generate_markdown_diagram",
                        "description": "Generate markdown file with Mermaid diagram (flowchart/pie/mindmap).",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "output_path": {"type": "string", "description": "Output markdown path"},
                                "diagram_type": {"type": "string", "description": "flowchart/pie/mindmap"},
                                "title": {"type": "string", "description": "Diagram title"},
                                "content": {"type": "string", "description": "Mermaid content body"}
                            },
                            "required": ["output_path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "start_web_preview",
                        "description": "Start local static web preview server for deployment/debug and return URL.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "serve_path": {"type": "string", "description": "Directory to serve"},
                                "port": {"type": "integer", "description": "Port for preview server"},
                                "external_approval_id": {"type": "string", "description": "Approval id for external path access"}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "list_external_approvals",
                        "description": "List external path access approval requests.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "description": "pending/approved/rejected/all"},
                                "limit": {"type": "integer", "description": "Max items"}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "resolve_external_approval",
                        "description": "Approve or reject an external path access request.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "request_id": {"type": "string", "description": "Approval request id"},
                                "approve": {"type": "boolean", "description": "true approve, false reject"},
                                "reason": {"type": "string", "description": "Optional reason"}
                            },
                            "required": ["request_id", "approve"]
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
                },
                {
                    "type": "function",
                    "function": {
                        "name": "plugin_list",
                        "description": "List installed plugins and their current status",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "plugin_reload",
                        "description": "Reload all plugins from disk",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "plugin_toggle",
                        "description": "Enable or disable a plugin",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "plugin_name": {"type": "string", "description": "Plugin name"},
                                "enabled": {"type": "boolean", "description": "Whether the plugin is enabled"}
                            },
                            "required": ["plugin_name", "enabled"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "plugin_get_config",
                        "description": "Read plugin runtime config JSON",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "plugin_name": {"type": "string", "description": "Plugin name"}
                            },
                            "required": ["plugin_name"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "plugin_set_config",
                        "description": "Write plugin runtime config JSON",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "plugin_name": {"type": "string", "description": "Plugin name"},
                                "config": {"type": "object", "description": "Full runtime config object"}
                            },
                            "required": ["plugin_name", "config"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_long_term_memory",
                        "description": "Read agent long-term memory content so users can inspect persistent memory.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "persona_filename": {"type": "string", "description": "Optional persona filename to scope memory"},
                                "include_meta": {"type": "boolean", "description": "Whether to include memory metadata"}
                            }
                        }
                    }
                }
            ])

        return tools
