# -*- coding: utf-8 -*-
"""Plugin framework package."""

from .base import PluginContext, PluginMeta, PluginResult
from .manager import PluginManager

__all__ = [
    "PluginContext",
    "PluginMeta",
    "PluginResult",
    "PluginManager",
]
