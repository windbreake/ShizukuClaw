# -*- coding: utf-8 -*-
"""Backward-compatible MCP manager import path."""

from app.frameworks.mcp_manager import MCPManager, MCPResource, MCPServer, MCPTool, get_mcp_manager

__all__ = ["MCPManager", "MCPServer", "MCPResource", "MCPTool", "get_mcp_manager"]
