from .base_client import LLMClient


class LocalLLMClient(LLMClient):
    """
    注意：根据图示，这个类必须同时实现 chat 和 embed，
    否则无法实例化。虽然图中只画了 chat，但在接口约束下必须补全 embed。
    """

    def chat(self, messages: list[dict]) -> str:
        # TODO: 这里编写调用本地模型(如 Ollama/Llama.cpp)的逻辑
        return "[Local Model] 回复: 这是一个模拟的本地模型回复。"

    def embed(self, text: str) -> list:
        # TODO: 这里编写本地向量化的逻辑
        return [0.9, 0.8, 0.7]
