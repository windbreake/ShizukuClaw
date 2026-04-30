# -*- coding: utf-8 -*-
"""AstrBot Message Components compatibility module.

Provides the same interface as astrbot.api.message_components
so that AstrBot plugins using message components can load.
"""

from typing import List, Optional


class Plain:
    """Plain text message component."""
    def __init__(self, text: str):
        self.text = str(text)
        self.type = "text"

    def __repr__(self):
        return f"Plain({self.text!r})"


class Image:
    """Image message component."""
    def __init__(self, file: str = "", url: str = ""):
        self.file = file
        self.url = url
        self.type = "image"

    @classmethod
    def fromFileSystem(cls, file_path: str):
        return cls(file=file_path)

    @classmethod
    def fromURL(cls, url: str):
        return cls(url=url)

    def __repr__(self):
        return f"Image(file={self.file!r}, url={self.url!r})"


class At:
    """@mention component."""
    def __init__(self, qq: str):
        self.qq = str(qq)
        self.type = "at"

    def __repr__(self):
        return f"At(qq={self.qq!r})"


class Reply:
    """Reply to message component."""
    def __init__(self, message_id: str = "", user_id: str = ""):
        self.message_id = str(message_id)
        self.user_id = str(user_id)
        self.type = "reply"

    def __repr__(self):
        return f"Reply(id={self.message_id!r})"


class Node:
    """Forward message node."""
    def __init__(self, uin: str = "", name: str = "", time: int = 0, content=None):
        self.uin = str(uin)
        self.name = str(name)
        self.time = int(time)
        self.content = content
        self.type = "node"

    def __repr__(self):
        return f"Node(uin={self.uin!r}, name={self.name!r})"


class Record:
    """Voice/record message component."""
    def __init__(self, file: str = "", url: str = ""):
        self.file = file
        self.url = url
        self.type = "record"

    @classmethod
    def fromFileSystem(cls, file_path: str):
        return cls(file=file_path)

    @classmethod
    def fromURL(cls, url: str):
        return cls(url=url)


class Video:
    """Video message component."""
    def __init__(self, file: str = "", url: str = ""):
        self.file = file
        self.url = url
        self.type = "video"

    @classmethod
    def fromFileSystem(cls, file_path: str):
        return cls(file=file_path)

    @classmethod
    def fromURL(cls, url: str):
        return cls(url=url)


class MessageChain:
    """Chain of message components."""
    def __init__(self, components: Optional[List] = None):
        self.chain = list(components or [])

    def __iter__(self):
        return iter(self.chain)

    def __len__(self):
        return len(self.chain)

    def __getitem__(self, index):
        return self.chain[index]

    def __repr__(self):
        return f"MessageChain({self.chain!r})"

    @staticmethod
    def create(*components) -> "MessageChain":
        """Create a MessageChain from component instances."""
        return MessageChain(list(components))

    def add(self, component) -> "MessageChain":
        """Add a component to the chain."""
        self.chain.append(component)
        return self


__all__ = [
    'Plain',
    'Image',
    'At',
    'Reply',
    'Node',
    'Record',
    'Video',
    'MessageChain',
]
