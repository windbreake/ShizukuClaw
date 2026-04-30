# -*- coding: utf-8 -*-
"""Core models for the plugin framework."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PluginMeta:
    """Metadata for plugin dependency and lifecycle management."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)


@dataclass
class PluginContext:
    """Shared runtime context passed to plugins."""

    user_input: str
    is_admin: bool = False
    frontend_source: str = "control_panel"
    attachments: Optional[list] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    chat_system: Any = None


@dataclass
class PluginResult:
    """Result returned by plugins."""

    handled: bool = False
    response: Optional[str] = None
    rewritten_input: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
