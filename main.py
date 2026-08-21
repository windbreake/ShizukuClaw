from src.llm import LLMClient
from src.llm import OpenAILLMClient
from src.llm.local_llm_client import LocalLLMClient
from typing import List

# --- 测试代码 ---
if __name__ == "__main__":
    # 实例化 OpenAI 客户端
    openai_client = OpenAILLMClient(model="gpt-4")
    print(openai_client.chat([{"role": "user", "content": "你好"}]))

    print("-" * 30)

    # 实例化 本地 客户端
    local_client = LocalLLMClient()
    print(local_client.chat([{"role": "user", "content": "你好"}]))

    # 测试多态性：统一使用 LLMClient 类型调用
    clients: List[LLMClient] = [openai_client, local_client]
    for client in clients:
        # 无论底层是 OpenAI 还是 Local，都可以安全调用 chat
        print(f"调用结果: {client.chat([])}")
