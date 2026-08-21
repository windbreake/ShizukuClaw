from src.graph.state import State
from src.graph.nodes.router_node import RouterNode
from src.graph.nodes.tool_executor_node import ToolExecutorNode
from src.graph.nodes.response_node import ResponseNode


class AgentGraph:
    def __init__(self):
        self.state = State()
        # 初始化节点（依赖注入）
        # self.router = RouterNode(...)

    def build(self) -> 'AgentGraph':
        # 构建图的连接逻辑
        # 例如：Start -> Router -> (Tools | Response) -> End
        print("Building Graph...")
        return self

    def invoke(self, input_data: dict) -> State:
        # 执行图的遍历
        current_state = State(**input_data)

        # 模拟流程
        # 1. Router
        # next_node = self.router.route(current_state)

        # 2. Execute based on route
        print("Invoking Graph flow...")

        return current_state