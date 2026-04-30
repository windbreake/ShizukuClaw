# -*- coding: utf-8 -*-
"""
AstrBot Logger Compatibility

Provides a logger interface compatible with AstrBot's logging system.
"""

import logging


class AstrBotLogger:
    """Simulated AstrBot logger."""
    
    def __init__(self, name: str = "astrbot"):
        self.logger = logging.getLogger(name)
    
    def info(self, msg: str):
        """Log info message."""
        print(f"[AstrBot] INFO: {msg}")
        self.logger.info(msg)
    
    def warning(self, msg: str):
        """Log warning message."""
        print(f"[AstrBot] WARNING: {msg}")
        self.logger.warning(msg)
    
    def error(self, msg: str):
        """Log error message."""
        print(f"[AstrBot] ERROR: {msg}")
        self.logger.error(msg)
    
    def debug(self, msg: str):
        """Log debug message."""
        print(f"[AstrBot] DEBUG: {msg}")
        self.logger.debug(msg)


# Create default logger instance
logger = AstrBotLogger()
