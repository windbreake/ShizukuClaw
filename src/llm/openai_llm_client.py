from typing import List
from .base_client import LLMClient


class OpenAILLMClient(LLMClient):
    """
    OpenAI 客户端
    """
    def __init__(self, model: str):
        self.model = model
        print(f"初始化 OpenAI 客户端，模型: {self.model}")

    def chat(self, messages: List[dict]) -> str:
        # TODO: 这里编写调用 OpenAI API 的具体逻辑
        return f"[OpenAI {self.model}] 回复: 这是一个模拟的 OpenAI 回复。"

    def embed(self, text: str) -> list:
        # TODO: 这里编写调用 Embedding API 的具体逻辑
            return [0.1, 0.2, 0.3]

