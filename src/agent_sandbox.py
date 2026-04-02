# -*- coding: utf-8 -*-
"""
Agent 沙箱环境模块 (Agent Sandbox)

功能描述:
    为 AI 智能体通过代码执行任务提供隔离环境。
    支持在安全受控的环境中运行 Python 脚本或命令行工具，
    并捕获执行结果返回给智能体。
"""
"""Sandbox execution module for the AI agent"""

import os
import sys
import subprocess
import shutil

class SandboxError(Exception):
    pass

class AgentSandbox:
    def __init__(self, root_dir):
        # Allow operations ONLY within this 'root_dir'
        self.root_dir = os.path.abspath(root_dir)
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)

        # root_dir itself is the workspace root
        self.workspace_dir = self.root_dir

    def validate_path(self, path):
        """Ensure path is within the sandbox root"""
        # If path is absolute, check if it's inside root_dir
        if os.path.isabs(path):
            abs_path = os.path.abspath(path)
        else:
            # If relative, join with root_dir
            abs_path = os.path.abspath(os.path.join(self.root_dir, path))
            
        if not abs_path.startswith(self.root_dir):
            raise SandboxError(f"Access Denied: Path '{path}' resolves to '{abs_path}' which is outside sandbox '{self.root_dir}'")
        return abs_path

    def read_file(self, path):
        safe_path = self.validate_path(path)
        if not os.path.exists(safe_path):
            return f"Error: File not found: {path}"
        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def write_file(self, path, content):
        safe_path = self.validate_path(path)
        try:
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Success: Wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def append_file_content(self, path, content, position=None):
        safe_path = self.validate_path(path)
        try:
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            if not os.path.exists(safe_path):
                if position not in (None, 0):
                    return "Error: position must be 0 when creating a new file"
                with open(safe_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Success: Appended to {path}"

            with open(safe_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            insert_at = len(original_content) if position is None else int(position)
            if insert_at < 0:
                return "Error: position must be non-negative"
            if insert_at > len(original_content):
                return "Error: position is out of range"

            updated_content = original_content[:insert_at] + content + original_content[insert_at:]

            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            return f"Success: Appended to {path} at position {insert_at}"
        except Exception as e:
            return f"Error appending file: {str(e)}"

    def delete_file_content(self, path, position, length):
        safe_path = self.validate_path(path)
        try:
            if not os.path.exists(safe_path):
                return f"Error: File not found: {path}"
            if os.path.isdir(safe_path):
                return f"Error: Path is a directory, not a file: {path}"

            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()

            start = int(position)
            delete_length = int(length)
            if start < 0 or delete_length < 0:
                return "Error: position and length must be non-negative"
            if start > len(content):
                return "Error: position is out of range"

            end = min(start + delete_length, len(content))
            updated_content = content[:start] + content[end:]

            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            return f"Success: Deleted content from {path}"
        except ValueError:
            return "Error: position and length must be integers"
        except Exception as e:
            return f"Error deleting file content: {str(e)}"

    def delete_file(self, path):
        safe_path = self.validate_path(path)
        try:
            if not os.path.exists(safe_path):
                return f"Error: File not found: {path}"
            if os.path.isdir(safe_path):
                return f"Error: Path is a directory, not a file: {path}"
            os.remove(safe_path)
            return f"Success: Deleted {path}"
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    def list_dir(self, path='.'):
        target = os.path.join(self.workspace_dir, path)
        safe_path = self.validate_path(target)
        try:
            return str(os.listdir(safe_path))
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def execute_python(self, code_str, filename="temp_script.py"):
        """Execute Python code in the sandboxed environment (restricted paths)"""
        # Note: This is a weak sandbox (just path checks), but fits the requirement.
        script_path = os.path.join(self.workspace_dir, filename)
        try:
            self.write_file(script_path, code_str)
            
            # Execute in subprocess, setting CWD to workspace
            cwd = self.workspace_dir
            result = subprocess.run(
                [sys.executable, filename],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30 # 30s timeout
            )
            output = f"Output:\n{result.stdout}"
            if result.stderr:
                output += f"\nErrors:\n{result.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        except Exception as e:
            return f"Error executing code: {str(e)}"
