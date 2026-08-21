from abc import ABC, abstractmethod

class Tool(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, args: dict) -> str:
        pass