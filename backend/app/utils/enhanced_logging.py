# -*- coding: utf-8 -*-
"""
增强型日志系统 - 提供类似AstR的直观日志格式
"""

import logging
import json
import time
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import os


class LogLevel(Enum):
    """日志级别定义"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"  # 自定义成功级别


@dataclass
class LogEntry:
    """日志条目数据类"""
    timestamp: str
    level: str
    module: str
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    request_id: Optional[str] = None
    
    def to_dict(self):
        """转换为字典"""
        return asdict(self)


class EnhancedFormatter(logging.Formatter):
    """增强型日志格式化器 - 类似AstR风格"""
    
    COLOR_MAP = {
        logging.DEBUG: '\033[36m',     # Cyan
        logging.INFO: '\033[32m',      # Green
        logging.WARNING: '\033[33m',   # Yellow
        logging.ERROR: '\033[31m',     # Red
        logging.CRITICAL: '\033[1;31m',  # Bold Red
        'SUCCESS': '\033[1;32m',       # Bold Green
    }
    RESET = '\033[0m'
    
    def format(self, record):
        """格式化日志记录"""
        timestamp = self.formatTime(record, '%H:%M:%S.%f')[:-3]
        level = record.levelname
        module = record.name.split('.')[-1] if record.name else 'Core'
        
        # 构建日志行
        color = self.COLOR_MAP.get(record.levelno, self.COLOR_MAP[logging.INFO])
        log_line = (
            f"[{timestamp}] [{module}] [{color}{level}{self.RESET}] {record.getMessage()}"
        )
        
        # 添加额外信息
        if hasattr(record, 'request_id'):
            log_line += f" | Request: {record.request_id}"
        if hasattr(record, 'duration_ms'):
            log_line += f" | Duration: {record.duration_ms:.2f}ms"
            
        return log_line


class EnhancedLogger:
    """增强型日志管理器"""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        初始化增强型日志
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.log_entries: List[LogEntry] = []
        self.max_entries = 1000
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(EnhancedFormatter())
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(file_handler)
    
    def _add_entry(self, level: str, module: str, message: str, 
                   details: Optional[Dict] = None, duration_ms: Optional[float] = None):
        """添加日志条目到内存"""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            module=module,
            message=message,
            details=details,
            duration_ms=duration_ms
        )
        self.log_entries.append(entry)
        
        # 限制日志条目数量
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)
    
    def debug(self, message: str, **kwargs):
        """调试级别日志"""
        self.logger.debug(message)
        self._add_entry('DEBUG', self.logger.name, message, kwargs)
    
    def info(self, message: str, **kwargs):
        """信息级别日志"""
        self.logger.info(message)
        self._add_entry('INFO', self.logger.name, message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告级别日志"""
        self.logger.warning(message)
        self._add_entry('WARNING', self.logger.name, message, kwargs)
    
    def error(self, message: str, **kwargs):
        """错误级别日志"""
        self.logger.error(message)
        self._add_entry('ERROR', self.logger.name, message, kwargs)
    
    def critical(self, message: str, **kwargs):
        """严重错误级别日志"""
        self.logger.critical(message)
        self._add_entry('CRITICAL', self.logger.name, message, kwargs)
    
    def success(self, message: str, **kwargs):
        """成功级别日志（自定义）"""
        self.logger.info(f"✓ {message}")
        self._add_entry('SUCCESS', self.logger.name, message, kwargs)
    
    def get_entries(self, level: Optional[str] = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取日志条目
        
        Args:
            level: 过滤的日志级别
            limit: 限制条目数
            
        Returns:
            日志条目列表
        """
        entries = self.log_entries
        
        if level:
            entries = [e for e in entries if e.level == level]
        
        # 返回最近的entries
        return [e.to_dict() for e in entries[-limit:]]
    
    def clear_entries(self):
        """清除日志条目"""
        self.log_entries.clear()


# 全局日志实例
_logger_instance: Optional[EnhancedLogger] = None


def get_enhanced_logger(name: str = 'ShizukuBot', 
                       log_file: Optional[str] = None) -> EnhancedLogger:
    """获取或创建增强型日志实例"""
    global _logger_instance
    if _logger_instance is None:
        if log_file is None:
            log_file = 'logs/enhanced.log'
        _logger_instance = EnhancedLogger(name, log_file)
    return _logger_instance
