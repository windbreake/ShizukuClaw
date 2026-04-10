# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 系统 - 管理系统上下文和集成
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field
import os
from glob import glob
import re

import requests


def _repo_root_from_here() -> str:
    # mcp_manager.py 位于 src/frameworks/，向上两级到项目根目录
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _resolve_storage_dir(storage_dir: str) -> str:
    repo_root = _repo_root_from_here()
    canonical_data_dir = os.path.join(repo_root, 'data')
    legacy_data_dir = os.path.join(repo_root, 'src', 'data')

    if os.path.isabs(storage_dir):
        normalized_abs = os.path.normpath(storage_dir)
        if normalized_abs == legacy_data_dir or normalized_abs.startswith(legacy_data_dir + os.sep):
            rel = os.path.relpath(normalized_abs, legacy_data_dir)
            return canonical_data_dir if rel == '.' else os.path.join(canonical_data_dir, rel)
        return normalized_abs

    normalized = storage_dir.replace('\\', '/').lstrip('./')
    if normalized.startswith('src/data/'):
        normalized = normalized[len('src/data/'):]
    elif normalized == 'src/data':
        normalized = ''
    elif normalized.startswith('data/'):
        normalized = normalized[len('data/'):]

    return canonical_data_dir if not normalized else os.path.join(canonical_data_dir, normalized)


@dataclass
class MCPServer:
    """MCP服务器配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    protocol_version: str = "1.0"
    
    # 连接配置
    type: str = ""  # e.g., "stdio", "sse", "http"
    command: str = ""
    args: List[str] = field(default_factory=list)
    
    # HTTP配置
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    
    # 能力定义
    capabilities: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    enabled: bool = True
    status: str = "disconnected"  # connected, disconnected, error
    last_sync: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPResource:
    """MCP资源"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    server_id: str = ""
    name: str = ""
    uri: str = ""
    description: str = ""
    mime_type: str = "text/plain"
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPTool:
    """MCP工具定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    server_id: str = ""
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPManager:
    """MCP系统管理器"""
    
    def __init__(self, storage_dir: str = 'data/mcp'):
        """
        初始化MCP管理器
        
        Args:
            storage_dir: MCP数据存储目录
        """
        resolved_storage_dir = _resolve_storage_dir(storage_dir)

        self.storage_dir = resolved_storage_dir
        self.servers_file = os.path.join(resolved_storage_dir, 'servers.json')
        self.server_file_pattern = os.path.join(resolved_storage_dir, '*.server.json')
        self.resources_file = os.path.join(resolved_storage_dir, 'resources.json')
        self.tools_file = os.path.join(resolved_storage_dir, 'tools.json')
        
        self.servers: Dict[str, MCPServer] = {}
        self._server_sources: Dict[str, str] = {}
        self._known_server_files: set[str] = set()
        self.resources: Dict[str, MCPResource] = {}
        self.tools: Dict[str, MCPTool] = {}
        
        # 创建存储目录
        os.makedirs(resolved_storage_dir, exist_ok=True)
        
        # 加载已保存的数据
        self._load_data()
    
    def _load_data(self):
        """加载MCP数据"""
        try:
            self._known_server_files = {self.servers_file}

            def _load_servers_from_file(file_path: str):
                if not os.path.exists(file_path):
                    return
                with open(file_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    payload = [payload]
                if not isinstance(payload, list):
                    return
                self._known_server_files.add(file_path)
                for server_dict in payload:
                    if not isinstance(server_dict, dict):
                        continue
                    server = MCPServer(**server_dict)
                    self.servers[server.id] = server
                    self._server_sources[server.id] = file_path

            if os.path.exists(self.servers_file):
                _load_servers_from_file(self.servers_file)

            for extra_file in glob(self.server_file_pattern):
                _load_servers_from_file(extra_file)
            
            if os.path.exists(self.resources_file):
                with open(self.resources_file, 'r', encoding='utf-8') as f:
                    for res_dict in json.load(f):
                        res = MCPResource(**res_dict)
                        self.resources[res.id] = res
            
            if os.path.exists(self.tools_file):
                with open(self.tools_file, 'r', encoding='utf-8') as f:
                    for tool_dict in json.load(f):
                        tool = MCPTool(**tool_dict)
                        self.tools[tool.id] = tool
        except Exception as e:
            print(f"Error loading MCP data: {e}")
    
    def _save_data(self):
        """保存MCP数据"""
        try:
            grouped_servers: Dict[str, List[Dict[str, Any]]] = {}
            for server in self.servers.values():
                source_file = self._server_sources.get(server.id, self.servers_file)
                grouped_servers.setdefault(source_file, []).append(server.to_dict())

            files_to_write = set(self._known_server_files) | set(grouped_servers.keys())
            for server_file in files_to_write:
                with open(server_file, 'w', encoding='utf-8') as f:
                    json.dump(grouped_servers.get(server_file, []), f, ensure_ascii=False, indent=2)
            
            with open(self.resources_file, 'w', encoding='utf-8') as f:
                data = [r.to_dict() for r in self.resources.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.tools_file, 'w', encoding='utf-8') as f:
                data = [t.to_dict() for t in self.tools.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving MCP data: {e}")

    def _resolve_header_value(self, value: Any) -> Any:
        """解析头部里的环境变量占位符。"""
        if not isinstance(value, str):
            return value

        text = value
        if not text:
            return text

        def repl(match):
            raw = str(match.group(1) or '').strip()
            if raw.lower().startswith('env:'):
                raw = raw[4:].strip()
            resolved = os.environ.get(raw, '')
            if resolved:
                return resolved
            if raw in {'GITHUB_MCP_TOKEN', 'github_mcp_token'}:
                return os.environ.get('GITHUB_TOKEN', '') or os.environ.get('GH_TOKEN', '')
            return ''

        return re.sub(r'\$\{([^}]+)\}', repl, text)

    def _resolved_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """返回解析后的请求头。"""
        resolved = {}
        for key, value in (headers or {}).items():
            resolved_value = self._resolve_header_value(value)
            if resolved_value in (None, ''):
                continue
            h_key = str(key)
            h_val = str(resolved_value).strip()
            if not h_val:
                continue
            # requests/urllib3 最终要求 header key/value 可按 latin-1 编码。
            try:
                h_key.encode('latin-1')
                h_val.encode('latin-1')
            except UnicodeEncodeError:
                continue
            if h_key.lower() == 'authorization' and h_val.lower() in {'bearer', 'bearer ${github_mcp_token}'}:
                continue
            if h_key.lower() == 'authorization' and h_val.lower().startswith('bearer ') and len(h_val) <= 7:
                continue
            resolved[h_key] = h_val
        return resolved

    def _probe_server_status(self, server: MCPServer) -> str:
        """探测服务器连通性并返回状态。"""
        if not server.enabled:
            return 'disconnected'

        server_type = str(server.type or '').strip().lower()
        if server_type not in {'http', 'sse'}:
            return server.status or 'disconnected'

        target_url = str(server.url or '').strip()
        if not target_url:
            return 'error'

        try:
            headers = self._resolved_headers(server.headers or {})
            response = requests.get(
                target_url,
                timeout=5,
                allow_redirects=True,
                stream=True,
                headers=headers,
            )
            try:
                response.close()
            except Exception:
                pass
            return 'connected'
        except requests.RequestException:
            return 'disconnected'
        except Exception:
            return 'error'

    def _refresh_server_statuses(self, persist: bool = True):
        """刷新所有服务器状态。"""
        changed = False
        now = datetime.now().isoformat()

        for server in self.servers.values():
            new_status = self._probe_server_status(server)
            if new_status and new_status != server.status:
                server.status = new_status
                server.updated_at = now
                if new_status == 'connected':
                    server.last_sync = now
                changed = True

        if changed and persist:
            self._save_data()

        return changed
    
    # ===== Server 管理 =====
    
    def add_server(self, server: MCPServer) -> str:
        """添加MCP服务器"""
        self.servers[server.id] = server
        self._server_sources[server.id] = self.servers_file
        self._known_server_files.add(self.servers_file)
        self._save_data()
        return server.id
    
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """获取MCP服务器"""
        return self.servers.get(server_id)
    
    def list_servers(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列表查询服务器"""
        self._refresh_server_statuses(persist=True)
        servers = list(self.servers.values())
        
        if enabled_only:
            servers = [s for s in servers if s.enabled]
        
        return [s.to_dict() for s in servers]
    
    def update_server(self, server_id: str, updates: Dict[str, Any]) -> Optional[MCPServer]:
        """更新服务器配置"""
        server = self.servers.get(server_id)
        if not server:
            return None
        
        for key, value in updates.items():
            if hasattr(server, key):
                setattr(server, key, value)
        
        server.updated_at = datetime.now().isoformat()
        self._save_data()
        return server
    
    def delete_server(self, server_id: str) -> bool:
        """删除服务器"""
        if server_id in self.servers:
            del self.servers[server_id]
            self._server_sources.pop(server_id, None)
            
            # 删除关联的资源和工具
            self.resources = {
                rid: r for rid, r in self.resources.items() 
                if r.server_id != server_id
            }
            self.tools = {
                tid: t for tid, t in self.tools.items() 
                if t.server_id != server_id
            }
            
            self._save_data()
            return True
        
        return False
    
    # ===== Resource 管理 =====
    
    def add_resource(self, resource: MCPResource) -> str:
        """添加资源"""
        self.resources[resource.id] = resource
        self._save_data()
        return resource.id
    
    def get_resource(self, resource_id: str) -> Optional[MCPResource]:
        """获取资源"""
        return self.resources.get(resource_id)
    
    def list_resources(self, server_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列表查询资源"""
        resources = list(self.resources.values())
        
        if server_id:
            resources = [r for r in resources if r.server_id == server_id]
        
        return [r.to_dict() for r in resources]
    
    def update_resource(self, resource_id: str, updates: Dict[str, Any]) -> Optional[MCPResource]:
        """更新资源"""
        resource = self.resources.get(resource_id)
        if not resource:
            return None
        
        for key, value in updates.items():
            if hasattr(resource, key):
                setattr(resource, key, value)
        
        self._save_data()
        return resource
    
    def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        if resource_id in self.resources:
            del self.resources[resource_id]
            self._save_data()
            return True
        
        return False
    
    # ===== Tool 管理 =====
    
    def add_tool(self, tool: MCPTool) -> str:
        """添加工具"""
        self.tools[tool.id] = tool
        self._save_data()
        return tool.id
    
    def get_tool(self, tool_id: str) -> Optional[MCPTool]:
        """获取工具"""
        return self.tools.get(tool_id)
    
    def list_tools(self, server_id: Optional[str] = None, 
                   enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列表查询工具"""
        tools = list(self.tools.values())
        
        if server_id:
            tools = [t for t in tools if t.server_id == server_id]
        
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        
        return [t.to_dict() for t in tools]
    
    def update_tool(self, tool_id: str, updates: Dict[str, Any]) -> Optional[MCPTool]:
        """更新工具"""
        tool = self.tools.get(tool_id)
        if not tool:
            return None
        
        for key, value in updates.items():
            if hasattr(tool, key):
                setattr(tool, key, value)
        
        self._save_data()
        return tool
    
    def delete_tool(self, tool_id: str) -> bool:
        """删除工具"""
        if tool_id in self.tools:
            del self.tools[tool_id]
            self._save_data()
            return True
        
        return False


# 全局MCP管理器实例
_mcp_manager_instance: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """获取或创建MCP管理器实例"""
    global _mcp_manager_instance
    if _mcp_manager_instance is None:
        _mcp_manager_instance = MCPManager()
    return _mcp_manager_instance
