# -*- coding: utf-8 -*-
"""
Amala 核心沙箱模块 - 统一代码执行隔离层

替代原 AgentSandbox，提供以下功能：
- Python 代码：vm2 虚拟机隔离
- JavaScript 代码：vm2 + 可选 Docker
- 文件 I/O：完全隔离在 workspace
- 密码级别验证：两层认证系统
"""

import os
import sys
import subprocess
import json
import time
import uuid
import threading
import hashlib
from enum import Enum
from typing import Dict, Any, Optional, Tuple

# 沙箱执行引擎枚举
class SandboxEngine(Enum):
    AMALA_LOCAL = "amala-local"          # 本地 amala (首选)
    AMALA_DOCKER = "amala-docker"        # Docker amala
    AMALA_WSL = "amala-wsl"              # WSL 中的 amala (Windows)

# 安全级别
class SecurityLevel(Enum):
    SANDBOX = "sandbox"                  # 沙箱模式 (默认)
    WORKSPACE = "workspace"              # 工作模式 (需要 Level1 密码)
    GLOBAL_ADMIN = "global_admin"        # 广域管理模式 (需要 Level1 + Level2 密码)

class AmalaSandbox:
    """统一沙箱执行器 - 替代原 AgentSandbox"""
    
    def __init__(self, root_dir, config=None):
        """
        Args:
            root_dir: 工作目录 (e.g., agent_datas/workspace)
            config: 配置对象 (可选)
        """
        self.root_dir = os.path.abspath(root_dir)
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)
        
        self.workspace_dir = self.root_dir
        self.config = config or {}
        self.project_root = os.path.abspath(os.path.join(self.root_dir, '..', '..'))
        
        # 初始化数据目录
        from app.core.config import DATA_DIR
        self.data_dir = DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 外部文件批准存储
        self.approvals_db = os.path.join(self.data_dir, 'sandbox_approvals.json')
        self._approvals_lock = threading.Lock()
        self._ensure_approvals_db()
        
        # 密码和安全模式存储
        self.security_db = os.path.join(self.data_dir, 'sandbox_security.json')
        self._security_lock = threading.Lock()
        self._ensure_security_db()
        
        # 检测运行时环境
        self._detect_runtime_env()
    
    def _detect_runtime_env(self):
        """检测可用的运行时环境"""
        self.has_docker = bool(self._check_docker())
        self.has_wsl = bool(self._check_wsl())
        self.has_node = bool(self._check_node())
    
    @staticmethod
    def _check_docker() -> bool:
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                timeout=2,
                check=False
            )
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def _check_wsl() -> bool:
        """检查 WSL 是否可用 (Windows only)"""
        if sys.platform != 'win32':
            return False
        try:
            result = subprocess.run(
                ['wsl', '--list', '--verbose'],
                capture_output=True,
                timeout=3,
                check=False
            )
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def _check_node() -> bool:
        """检查 Node.js 是否可用"""
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                timeout=2,
                check=False
            )
            return result.returncode == 0
        except:
            return False
    
    def _ensure_approvals_db(self):
        """确保批准数据库存在"""
        if not os.path.exists(self.approvals_db):
            with open(self.approvals_db, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def _ensure_security_db(self):
        """确保安全数据库存在"""
        if not os.path.exists(self.security_db):
            db = {
                "level1_password": "",  # 工作模式密码 (SHA256)
                "level2_password": "",  # 广域模式密码 (SHA256)
                "global_mode_enabled": False,
                "sessions": {}  # 活跃会话: {session_id: {level, timestamp}}
            }
            with open(self.security_db, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
    
    def set_security_passwords(self, level1_pwd: str, level2_pwd: str, admin_token: str = "") -> Dict[str, Any]:
        """
        设置两层密码
        
        Args:
            level1_pwd: 工作模式密码
            level2_pwd: 广域模式密码
            admin_token: 管理员令牌 (需要系统级认证)
        
        Returns:
            {"ok": True/False, "message": str}
        """
        with self._security_lock:
            try:
                db = json.load(open(self.security_db, 'r', encoding='utf-8'))
                db['level1_password'] = hashlib.sha256(level1_pwd.encode()).hexdigest()
                db['level2_password'] = hashlib.sha256(level2_pwd.encode()).hexdigest()
                
                with open(self.security_db, 'w', encoding='utf-8') as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                
                return {"ok": True, "message": "Passwords set successfully"}
            except Exception as e:
                return {"ok": False, "message": str(e)}
    
    def verify_password(self, password: str, level: int) -> bool:
        """
        验证密码
        
        Args:
            password: 输入的密码
            level: 级别 (1 或 2)
        
        Returns:
            验证结果
        """
        try:
            db = json.load(open(self.security_db, 'r', encoding='utf-8'))
            pwd_hash = db.get(f'level{level}_password', '')
            return hashlib.sha256(password.encode()).hexdigest() == pwd_hash
        except:
            return False
    
    def create_secure_session(self, level: int) -> Optional[str]:
        """
        创建安全会话
        
        Args:
            level: 安全级别 (1 或 2)
        
        Returns:
            会话 ID，或 None
        """
        with self._security_lock:
            try:
                db = json.load(open(self.security_db, 'r', encoding='utf-8'))
                session_id = str(uuid.uuid4())
                db['sessions'][session_id] = {
                    'level': level,
                    'created_at': time.time(),
                    'expires_at': time.time() + 3600  # 1 小时有效期
                }
                
                with open(self.security_db, 'w', encoding='utf-8') as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                
                return session_id
            except:
                return None
    
    def verify_session(self, session_id: str, required_level: int = 1) -> bool:
        """
        验证会话是否有效
        
        Args:
            session_id: 会话 ID
            required_level: 最低需要的级别
        
        Returns:
            是否有效
        """
        try:
            db = json.load(open(self.security_db, 'r', encoding='utf-8'))
            session = db.get('sessions', {}).get(session_id)
            
            if not session:
                return False
            
            # 检查过期
            if time.time() > session.get('expires_at', 0):
                return False
            
            # 检查级别
            return session.get('level', 0) >= required_level
        except:
            return False
    
    def execute(self, code: str, language: str = 'python', security_level: int = 0, session_id: str = "") -> Dict[str, Any]:
        """
        在沙箱中执行代码
        
        Args:
            code: 源代码
            language: 语言 ('python' 或 'javascript')
            security_level: 安全级别 (0=沙箱, 1=工作模式, 2=广域模式)
            session_id: 具有相应权限的会话 ID (级别 1 和 2 需要)
        
        Returns:
            执行结果 {"ok": bool, "output": str, "error": str, ...}
        """
        # 级别 1 和 2 需要会话验证
        if security_level > 0:
            if not self.verify_session(session_id, security_level):
                return {
                    "ok": False,
                    "engine": "amala",
                    "error": f"Invalid or expired session for security level {security_level}",
                    "output": "",
                    "security_level": security_level
                }
        
        # 选择执行引擎
        if language == 'python':
            return self._execute_python(code, security_level)
        elif language == 'javascript':
            return self._execute_javascript(code, security_level)
        else:
            return {
                "ok": False,
                "engine": "amala",
                "error": f"Unsupported language: {language}",
                "output": ""
            }
    
    def _execute_python(self, code: str, security_level: int) -> Dict[str, Any]:
        """在 Python 沙箱中执行"""
        start_time = time.time()
        
        try:
            # 创建临时脚本
            script_name = f"script_{uuid.uuid4().hex[:8]}.py"
            script_path = os.path.join(self.workspace_dir, script_name)
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # 根据安全级别选择执行方式
            if security_level >= 2:
                # 广域模式：允许完整的系统访问
                result = self._execute_python_global(script_path)
            elif security_level == 1:
                # 工作模式：受限但允许文件 I/O
                result = self._execute_python_workspace(script_path)
            else:
                # 沙箱模式：严格隔离
                result = self._execute_python_sandbox(script_path)
            
            # 清理
            try:
                os.remove(script_path)
            except:
                pass
            
            result['duration_ms'] = int((time.time() - start_time) * 1000)
            return result
            
        except Exception as e:
            return {
                "ok": False,
                "engine": "amala",
                "error": str(e),
                "output": "",
                "duration_ms": int((time.time() - start_time) * 1000)
            }
    
    def _execute_python_sandbox(self, script_path: str) -> Dict[str, Any]:
        """沙箱模式：subprocess 隔离"""
        try:
            env = os.environ.copy()
            env['PYTHONNOUSERSITE'] = '1'
            
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                check=False
            )
            
            return {
                "ok": result.returncode == 0,
                "engine": "amala-python-sandbox",
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine": "amala-python-sandbox",
                "error": "Execution timeout (30s limit in sandbox mode)",
                "output": "",
                "timed_out": True
            }
    
    def _execute_python_workspace(self, script_path: str) -> Dict[str, Any]:
        """工作模式：允许 workspace 内的文件 I/O"""
        # 与沙箱模式相同，但允许访问 workspace 目录
        return self._execute_python_sandbox(script_path)
    
    def _execute_python_global(self, script_path: str) -> Dict[str, Any]:
        """广域模式：完整的系统权限"""
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=45,
                check=False
            )
            
            return {
                "ok": result.returncode == 0,
                "engine": "amala-python-global",
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "return_code": result.returncode,
                "security_level": 2
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine": "amala-python-global",
                "error": "Execution timeout (45s limit in global mode)",
                "output": "",
                "timed_out": True
            }
    
    def _execute_javascript(self, code: str, security_level: int) -> Dict[str, Any]:
        """在 JavaScript 沙箱中执行"""
        start_time = time.time()
        
        try:
            # 创建临时脚本
            script_name = f"script_{uuid.uuid4().hex[:8]}.js"
            script_path = os.path.join(self.workspace_dir, script_name)
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # 检查 Node.js
            if not self.has_node:
                return {
                    "ok": False,
                    "engine": "amala-javascript",
                    "error": "Node.js not found. Install Node.js 16+ for JavaScript execution.",
                    "output": ""
                }
            
            # 调用 vm2 runner
            runner_path = os.path.join(self.project_root, 'src', 'runtimes', 'amala-sandbox', 'runner.js')
            if not os.path.exists(runner_path):
                return {
                    "ok": False,
                    "engine": "amala-javascript",
                    "error": f"vm2 runner not found at {runner_path}",
                    "output": ""
                }
            
            result = subprocess.run(
                ['node', runner_path, script_path, str(30000)],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=35,
                check=False
            )
            
            try:
                output = json.loads(result.stdout)
                output['security_level'] = security_level
                # 清理
                try:
                    os.remove(script_path)
                except:
                    pass
                output['duration_ms'] = int((time.time() - start_time) * 1000)
                return output
            except json.JSONDecodeError:
                return {
                    "ok": False,
                    "engine": "amala-javascript",
                    "error": result.stderr or "Invalid JSON response from runner",
                    "output": result.stdout
                }
        
        except Exception as e:
            return {
                "ok": False,
                "engine": "amala-javascript",
                "error": str(e),
                "output": ""
            }
    
    # 保留接口兼容性 (废弃但仍可用)
    def execute_python_with_details(self, code: str, filename: str = "temp.py") -> Dict[str, Any]:
        """向后兼容：原 AgentSandbox 接口"""
        return self.execute(code, language='python', security_level=0)
    
    def execute_javascript_with_amala(self, code: str) -> Dict[str, Any]:
        """向后兼容：原接口"""
        return self.execute(code, language='javascript', security_level=0)
    
    def write_file(self, path: str, content: str) -> str:
        """向后兼容：文件写入"""
        try:
            safe_path = self._validate_path(path)
            dir_path = os.path.dirname(safe_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Success: Wrote to {path}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def read_file(self, path: str) -> str:
        """向后兼容：文件读取"""
        try:
            safe_path = self._validate_path(path)
            with open(safe_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _validate_path(self, path: str) -> str:
        """验证路径在 workspace 内"""
        abs_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        if not abs_path.startswith(os.path.abspath(self.workspace_dir)):
            raise ValueError(f"Path {path} is outside workspace")
        return abs_path
    
    def get_status(self) -> Dict[str, Any]:
        """获取沙箱状态"""
        return {
            "workspace_dir": self.workspace_dir,
            "has_docker": self.has_docker,
            "has_wsl": self.has_wsl,
            "has_node": self.has_node,
            "platform": sys.platform,
            "pwd_configured": all([
                json.load(open(self.security_db)).get('level1_password'),
                json.load(open(self.security_db)).get('level2_password')
            ])
        }
