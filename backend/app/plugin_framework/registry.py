# -*- coding: utf-8 -*-
"""Registry for commands, regex rules and response hooks."""

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Pattern

from .base import PluginContext, PluginResult

CommandHandler = Callable[[PluginContext, str], PluginResult]
RuleHandler = Callable[[PluginContext, re.Match], PluginResult]
ResponseHandler = Callable[[PluginContext, str], str]
MessageHandler = Callable[[PluginContext], PluginResult]
StartupHandler = Callable[[], None]
ShutdownHandler = Callable[[], None]
ErrorHandler = Callable[[PluginContext, Exception], None]


@dataclass
class RegexRule:
    pattern: Pattern
    handler: RuleHandler
    priority: int
    plugin_name: str


class PluginRegistry:
    """In-memory plugin registration center."""

    def __init__(self):
        self.command_handlers: Dict[str, tuple[CommandHandler, str]] = {}
        self.regex_rules: List[RegexRule] = []
        self.response_handlers: List[tuple[ResponseHandler, str]] = []
        self.message_handlers: List[tuple[MessageHandler, str, int]] = []
        self.startup_handlers: List[tuple[StartupHandler, str]] = []
        self.shutdown_handlers: List[tuple[ShutdownHandler, str]] = []
        self.error_handlers: List[tuple[ErrorHandler, str]] = []

    def register_command(self, command: str, handler: CommandHandler, plugin_name: str) -> None:
        cmd = (command or "").strip().lower()
        if not cmd:
            raise ValueError("command cannot be empty")
        self.command_handlers[cmd] = (handler, plugin_name)

    def register_regex_rule(self, pattern: str, handler: RuleHandler, plugin_name: str, flags: int = 0, priority: int = 100) -> None:
        compiled = re.compile(pattern, flags)
        self.regex_rules.append(RegexRule(compiled, handler, int(priority), plugin_name))
        self.regex_rules.sort(key=lambda x: x.priority)

    def register_response_handler(self, handler: ResponseHandler, plugin_name: str) -> None:
        self.response_handlers.append((handler, plugin_name))

    def register_message_handler(self, handler: MessageHandler, plugin_name: str, priority: int = 100) -> None:
        self.message_handlers.append((handler, plugin_name, int(priority)))
        self.message_handlers.sort(key=lambda x: x[2])

    def register_startup_handler(self, handler: StartupHandler, plugin_name: str) -> None:
        self.startup_handlers.append((handler, plugin_name))

    def register_shutdown_handler(self, handler: ShutdownHandler, plugin_name: str) -> None:
        self.shutdown_handlers.append((handler, plugin_name))

    def register_error_handler(self, handler: ErrorHandler, plugin_name: str) -> None:
        self.error_handlers.append((handler, plugin_name))
