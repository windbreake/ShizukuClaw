# -*- coding: utf-8 -*-
"""
AstrBot Event and Filter Compatibility

Provides event handling and command filtering for AstrBot plugins.
"""

import functools


class AstrMessageEvent:
    """Simulated AstrBot message event."""
    
    def __init__(self, message_obj=None, context=None):
        self.message_obj = message_obj
        self.context = context
        self._result = None
    
    def get_sender_name(self) -> str:
        """Get sender name from message."""
        if self.message_obj and hasattr(self.message_obj, 'sender'):
            sender = self.message_obj.sender
            if isinstance(sender, dict):
                return sender.get('name', 'Unknown')
            elif hasattr(sender, 'name'):
                return sender.name
        return 'Unknown'
    
    @property
    def message_str(self) -> str:
        """Get plain text message content."""
        if self.message_obj and hasattr(self.message_obj, 'message_str'):
            return self.message_obj.message_str
        return ""
    
    async def plain_result(self, text: str):
        """Return plain text result."""
        self._result = {'type': 'text', 'content': text}
        return self._result
    
    async def image_result(self, url: str):
        """Return image result."""
        self._result = {'type': 'image', 'url': url}
        return self._result
    
    def get_result(self):
        """Get the result set by handler."""
        return self._result


class MessageEventResult:
    """Result object for message events."""
    
    def __init__(self):
        self.messages = []
    
    def message(self, text: str):
        """Add a text message."""
        self.messages.append({'type': 'text', 'content': text})
        return self
    
    def image(self, url: str):
        """Add an image message."""
        self.messages.append({'type': 'image', 'url': url})
        return self


class MessageType:
    """Message type constants."""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"


class EventMessageType:
    """Event message type constants."""
    ALL = "all"
    GROUP = "group"
    PRIVATE = "private"


class CommandFilter:
    """Command decorator for registering command handlers."""
    
    def __init__(self, command_name: str):
        self.command_name = command_name
    
    def __call__(self, func):
        """Decorate the function."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Attach command metadata
        wrapper._command_name = self.command_name
        wrapper._is_command_handler = True
        
        return wrapper


def command(command_name: str):
    """Decorator to register a command handler.
    
    Usage:
        @filter.command("helloworld")
        async def helloworld(self, event: AstrMessageEvent):
            yield event.plain_result("Hello!")
    """
    return CommandFilter(command_name)


def event_message_type(message_type: str):
    """Decorator to filter by message type.
    
    Usage:
        @filter.event_message_type(EventMessageType.ALL)
        async def on_message(self, event: AstrMessageEvent):
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._message_type = message_type
        return wrapper
    
    return decorator


# Export commonly used items
__all__ = [
    'AstrMessageEvent',
    'MessageEventResult',
    'MessageType',
    'EventMessageType',
    'command',
    'event_message_type',
]
