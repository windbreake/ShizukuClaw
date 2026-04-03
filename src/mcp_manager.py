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
        self.storage_dir = storage_dir
        self.servers_file = os.path.join(storage_dir, 'servers.json')
        self.resources_file = os.path.join(storage_dir, 'resources.json')
        self.tools_file = os.path.join(storage_dir, 'tools.json')
        
        self.servers: Dict[str, MCPServer] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.tools: Dict[str, MCPTool] = {}
        
        # 创建存储目录
        os.makedirs(storage_dir, exist_ok=True)
        
        # 加载已保存的数据
        self._load_data()
    
    def _load_data(self):
        """加载MCP数据"""
        try:
            if os.path.exists(self.servers_file):
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    for server_dict in json.load(f):
                        server = MCPServer(**server_dict)
                        self.servers[server.id] = server
            
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
            with open(self.servers_file, 'w', encoding='utf-8') as f:
                data = [s.to_dict() for s in self.servers.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.resources_file, 'w', encoding='utf-8') as f:
                data = [r.to_dict() for r in self.resources.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.tools_file, 'w', encoding='utf-8') as f:
                data = [t.to_dict() for t in self.tools.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving MCP data: {e}")
    
    # ===== Server 管理 =====
    
    def add_server(self, server: MCPServer) -> str:
        """添加MCP服务器"""
        self.servers[server.id] = server
        self._save_data()
        return server.id
    
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """获取MCP服务器"""
        return self.servers.get(server_id)
    
    def list_servers(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列表查询服务器"""
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
