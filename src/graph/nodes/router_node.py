from src.graph.state import State
from src.llm.base_client import LLMClient

class RouterNode:
    def __init__(self, llm: LLMClient):
        self.name = "RouterNode"
        self.llm = llm

    def call(self, state: State) -> State:
        # TODO: 实际中可能调用 LLM 判断意图
        print(f"[{self.name}] Routing...")
        return state

    def route(self, state: State) -> str:
        # TODO: 返回下一个节点的名称，例如 "ToolExecutorNode" 或 "ResponseNode"
        return "ToolExecutorNode"