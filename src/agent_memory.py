# -*- coding: utf-8 -*-
"""
Agent 记忆与规划模块

功能描述:
    管理 AI 智能体的记忆系统，包括：
    - 短期记忆 (Short-term memory): 存储当前会话上下文
    - 长期记忆 (Long-term memory): 存储持久化知识和经验
    - 任务规划 (AgentPlanner): 负责任务的分解、进度追踪与更新
"""
import json
import os
import time

# 定义文件路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace')
MEMORY_ROOT = os.path.join(WORKSPACE_ROOT, 'memory')
PLAN_PATH = os.path.join(WORKSPACE_ROOT, 'plan.md')
LEGACY_MEMORY_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'memory')
LEGACY_PLAN_PATH = os.path.join(PROJECT_ROOT, 'agent_datas', 'plan.md')

MAX_SHORT_TERM_TOKENS = 3000

class AgentMemory:
    def __init__(self, ai_chat_system=None):
        self.ai_chat_system = ai_chat_system
        if not os.path.exists(MEMORY_ROOT):
            os.makedirs(MEMORY_ROOT, exist_ok=True)
        self.short_term_path = os.path.join(MEMORY_ROOT, 'short_term.json')
        self.long_term_path = os.path.join(MEMORY_ROOT, 'long_term.md')

    def load_short_term(self):
        try:
            if os.path.exists(self.short_term_path):
                with open(self.short_term_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            legacy_short = os.path.join(LEGACY_MEMORY_ROOT, 'short_term.json')
            if os.path.exists(legacy_short):
                with open(legacy_short, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except:
            return []

    def save_short_term(self, data):
        with open(self.short_term_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_long_term(self):
        if os.path.exists(self.long_term_path):
            with open(self.long_term_path, 'r', encoding='utf-8') as f:
                return f.read()
        legacy_long = os.path.join(LEGACY_MEMORY_ROOT, 'long_term.md')
        if os.path.exists(legacy_long):
            with open(legacy_long, 'r', encoding='utf-8') as f:
                return f.read()
        return "暂无长期记忆。"

    def save_long_term(self, content):
        with open(self.long_term_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def append_short_term(self, role, content):
        """添加消息到短期记忆，并在必要时压缩"""
        st = self.load_short_term()
        # 记录时间戳
        st.append({"role": role, "content": content, "timestamp": time.time()})
        
        # 简单估算 token (字符数 / 3)
        total_chars = sum(len(str(m.get('content', ''))) for m in st)
        if total_chars > MAX_SHORT_TERM_TOKENS * 3:
            self.summarize_memory(st)
        else:
            self.save_short_term(st)

    def summarize_memory(self, messages):
        """总结旧消息并并入长期记忆"""
        if not self.ai_chat_system:
            # 如果没有系统引用，只做简单的截断保存，防止无限增长
            self.save_short_term(messages[-50:])
            return

        # 取前50%的消息进行总结
        split_idx = len(messages) // 2
        to_summarize = messages[:split_idx]
        remaining = messages[split_idx:]
        
        text_block = "\n".join([f"{m.get('role','unknown')}: {m.get('content','...')}" for m in to_summarize])
        current_long_term = self.load_long_term()
        
        # 构造Prompt
        prompt = f"""请将以下新的对话片段总结为简洁的Markdown要点，并将其合并到现有的长期记忆中。保留关键事实、决策和未完成的任务。

[现有长期记忆]:
{current_long_term}

[需归档的对话片段]:
{text_block}

[合并后的长期记忆]:"""

        try:
            # 这是一个同步调用，可能会阻塞
            summary = self.ai_chat_system.simple_chat(prompt)
            self.save_long_term(summary)
            self.save_short_term(remaining)
        except Exception as e:
            print(f"Memory summarization failed: {e}")
            # 如果失败，仅保存全部消息防止丢失
            self.save_short_term(messages)

class AgentPlanner:
    def __init__(self):
        dir_path = os.path.dirname(PLAN_PATH)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            
    def load_plan(self):
        if os.path.exists(PLAN_PATH):
            with open(PLAN_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        if os.path.exists(LEGACY_PLAN_PATH):
            with open(LEGACY_PLAN_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        return "# 项目计划\n暂无计划。"

    def update_plan(self, content):
        with open(PLAN_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
