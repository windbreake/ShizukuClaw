from abc import ABC, abstractmethod
from typing import List, Any


class LLMClient(ABC):
    """
    大语言模型客户端的通用接口定义
    """

    @abstractmethod
    def chat(self, messages: List[dict]) -> str:
        """
        对话方法
        :param messages: 消息列表
        :return: 回复的字符串
        """
        pass

    @abstractmethod
    def embed(self, text: str) -> list:
        """
        向量化/嵌入方法
        :param text: 输入文本
        :return: 向量列表
        """
        pass