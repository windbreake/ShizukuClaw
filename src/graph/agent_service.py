from src.graph.agent_graph import AgentGraph
from src.memory.memory_store import MemoryStore
from src.config import Config  # 假设你有一个加载配置的模块


class AgentService:
    def __init__(self, config_path: str):
        self.config = Config(config_path)
        self.memory_store = MemoryStore(session_id="default")
        self.graph = AgentGraph()

    def run(self, question: str) -> str:
        # 1. Load history from memory
        # 2. Build graph if needed
        self.graph.build()

        # 3. Invoke
        final_state = self.graph.invoke({"messages": [question]})

        # 4. Save to memory
        # self.memory_store.save(...)

        return final_state.messages[-1] if final_state.messages else ""

    def reset_session(self):
        self.memory_store = MemoryStore(session_id="new_id")