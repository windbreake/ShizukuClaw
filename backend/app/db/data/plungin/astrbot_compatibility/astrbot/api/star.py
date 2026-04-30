# -*- coding: utf-8 -*-
"""
AstrBot Star Base Class Compatibility

Provides the Star base class that AstrBot plugins inherit from.
"""


class Context:
    """Simulated AstrBot Context."""
    
    def __init__(self):
        self.config = {}
        self.plugin_manager = None
    
    def get_config(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value):
        """Set configuration value."""
        self.config[key] = value


class Star:
    """Base class for AstrBot plugins (Stars)."""
    
    def __init__(self, context: Context):
        """
        Initialize the Star plugin.
        
        Args:
            context: AstrBot context object containing system components
        """
        self.context = context
        self.name = self.__class__.__name__
        self.version = "1.0.0"
    
    async def initialize(self):
        """Called when plugin is loaded. Override this method to perform initialization."""
        pass
    
    async def terminate(self):
        """Called when plugin is unloaded. Override this method to perform cleanup."""
        pass
