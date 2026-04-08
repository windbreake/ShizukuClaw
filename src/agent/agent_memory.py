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
from datetime import datetime
from src.core.config import PROJECT_ROOT

# 定义文件路径
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace')
MEMORY_ROOT = os.path.join(WORKSPACE_ROOT, 'memory')
PLAN_PATH = os.path.join(WORKSPACE_ROOT, 'plan.md')
LEGACY_MEMORY_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'memory')
LEGACY_PLAN_PATH = os.path.join(PROJECT_ROOT, 'agent_datas', 'plan.md')

MAX_SHORT_TERM_TOKENS = 3000
SHORT_TERM_WINDOW = 20
MID_TERM_MAX_CHARS = 12000
LONG_TERM_MAX_CHARS = 20000
CONTEXT_PACKET_MAX_CHARS = 5000

class AgentMemory:
    def __init__(self, ai_chat_system=None):
        self.ai_chat_system = ai_chat_system
        if not os.path.exists(MEMORY_ROOT):
            os.makedirs(MEMORY_ROOT, exist_ok=True)
        self.short_term_path = os.path.join(MEMORY_ROOT, 'short_term.json')
        self.short_term_md_path = os.path.join(MEMORY_ROOT, 'short_term.md')
        self.mid_term_path = os.path.join(MEMORY_ROOT, 'mid_term.md')
        self.long_term_path = os.path.join(MEMORY_ROOT, 'long_term.md')
        self.context_compression_path = os.path.join(MEMORY_ROOT, 'context_compression.md')
        self.memory_rules_path = os.path.join(MEMORY_ROOT, 'memory_rules.md')
        self.temp_memory_dir = os.path.join(MEMORY_ROOT, 'temp')
        os.makedirs(self.temp_memory_dir, exist_ok=True)
        self._ensure_memory_scaffold()

    def _ensure_memory_scaffold(self):
        if not os.path.exists(self.memory_rules_path):
            rules = """# Memory System Rules\n\n## Layering\n- Short-term memory: keep recent turns and active task details.\n- Mid-term memory: keep episodic summaries of completed blocks and unresolved threads.\n- Long-term memory: keep durable facts, user preferences, and stable decisions.\n\n## Compression Policy\n- Trigger compaction when short-term exceeds token budget.\n- Summarize old chunks into mid-term memory without deleting key facts.\n- Consolidate oversized mid-term memory into long-term memory periodically.\n\n## Quality Rules\n- Prefer factual points over wording style.\n- Preserve unresolved tasks and explicit user requirements.\n- Do not store sensitive secrets unless explicitly required by user.\n"""
            with open(self.memory_rules_path, 'w', encoding='utf-8') as f:
                f.write(rules)

        if not os.path.exists(self.short_term_md_path):
            with open(self.short_term_md_path, 'w', encoding='utf-8') as f:
                f.write("# Short Term Memory\n\n暂无短期记忆。\n")

        if not os.path.exists(self.mid_term_path):
            with open(self.mid_term_path, 'w', encoding='utf-8') as f:
                f.write("# Mid Term Memory\n\n暂无中期记忆。\n")

        if not os.path.exists(self.long_term_path):
            with open(self.long_term_path, 'w', encoding='utf-8') as f:
                f.write("# Long Term Memory\n\n暂无长期记忆。\n")

        if not os.path.exists(self.context_compression_path):
            with open(self.context_compression_path, 'w', encoding='utf-8') as f:
                f.write("# Context Compression Snapshot\n\n暂无压缩上下文。\n")

    def _read_text(self, path, fallback=''):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception:
            pass
        return fallback

    def _write_text(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _append_temp_snapshot(self, title, content):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(self.temp_memory_dir, f'context_{ts}.md')
        snapshot = f"# {title}\n\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n\n{content}\n"
        self._write_text(temp_path, snapshot)

    def _format_short_term_markdown(self, messages):
        if not messages:
            return "# Short Term Memory\n\n暂无短期记忆。\n"

        rows = ["# Short Term Memory", ""]
        recent = messages[-SHORT_TERM_WINDOW:]
        for item in recent:
            role = item.get('role', 'unknown')
            content = str(item.get('content', '')).strip()
            timestamp = item.get('timestamp')
            if timestamp:
                try:
                    ts_text = datetime.fromtimestamp(float(timestamp)).isoformat(timespec='seconds')
                except Exception:
                    ts_text = 'unknown-time'
            else:
                ts_text = 'unknown-time'
            rows.append(f"- [{ts_text}] {role}: {content}")
        rows.append("")
        return "\n".join(rows)

    def _summarize_block(self, text_block, objective='总结关键事实、决策与待办'):
        text_block = (text_block or '').strip()
        if not text_block:
            return "- 无可总结内容。"

        if self.ai_chat_system and hasattr(self.ai_chat_system, '_create_chat_completion_with_retry'):
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "你是记忆压缩助手。输出简洁Markdown要点，不要杜撰。"
                    },
                    {
                        "role": "user",
                        "content": f"目标：{objective}\n\n请总结以下内容：\n{text_block}"
                    }
                ]
                response, _ = self.ai_chat_system._create_chat_completion_with_retry(
                    {
                        "messages": messages,
                        "temperature": 0.1,
                        "timeout": 30,
                    }
                )
                summary = (response.choices[0].message.content or '').strip()
                if summary:
                    return summary
            except Exception:
                pass

        lines = [line.strip() for line in text_block.splitlines() if line.strip()]
        sampled = lines[:8]
        if not sampled:
            return "- 无可总结内容。"
        return "\n".join([f"- {line[:180]}" for line in sampled])

    def _append_mid_term(self, summary_markdown):
        current = self._read_text(self.mid_term_path, '# Mid Term Memory\n\n')
        ts = datetime.now().isoformat(timespec='seconds')
        entry = f"\n## Episode {ts}\n\n{summary_markdown.strip()}\n"
        if not current.strip():
            current = '# Mid Term Memory\n\n'
        current += entry
        self._write_text(self.mid_term_path, current)

    def _consolidate_mid_to_long(self):
        mid_text = self._read_text(self.mid_term_path, '')
        if len(mid_text) <= MID_TERM_MAX_CHARS:
            return

        split_idx = int(len(mid_text) * 0.6)
        to_merge = mid_text[:split_idx]
        remaining = "# Mid Term Memory\n\n" + mid_text[split_idx:].lstrip()

        current_long = self.load_long_term()
        merged = self._summarize_block(
            f"[现有长期记忆]\n{current_long}\n\n[新增中期记忆]\n{to_merge}",
            objective='合并为长期记忆，保留稳定事实、偏好、长期任务'
        )

        if len(merged) > LONG_TERM_MAX_CHARS:
            merged = merged[:LONG_TERM_MAX_CHARS] + "\n\n- (长期记忆已按上限截断)"

        self.save_long_term(merged)
        self._write_text(self.mid_term_path, remaining)

    def _refresh_context_compression(self):
        short_md = self._read_text(self.short_term_md_path, '')
        mid_md = self._read_text(self.mid_term_path, '')
        long_md = self.load_long_term()

        packet = [
            '# Context Compression Snapshot',
            '',
            f'Generated: {datetime.now().isoformat(timespec="seconds")}',
            '',
            '## Recent Short-Term',
            short_md[-1800:] if short_md else '暂无',
            '',
            '## Mid-Term Highlights',
            mid_md[-1800:] if mid_md else '暂无',
            '',
            '## Long-Term Core',
            long_md[-1200:] if long_md else '暂无',
            ''
        ]
        content = "\n".join(packet)
        if len(content) > CONTEXT_PACKET_MAX_CHARS:
            content = content[:CONTEXT_PACKET_MAX_CHARS] + "\n\n(上下文压缩包已截断)"
        self._write_text(self.context_compression_path, content)

    def build_context_packet(self):
        rules = self._read_text(self.memory_rules_path, '')
        compressed = self._read_text(self.context_compression_path, '')
        if not compressed.strip():
            self._refresh_context_compression()
            compressed = self._read_text(self.context_compression_path, '')

        chunks = [
            '[Memory Rules]',
            rules.strip() or 'No rules',
            '',
            '[Compressed Context]',
            compressed.strip() or 'No compressed context'
        ]
        text = "\n".join(chunks)
        if len(text) > CONTEXT_PACKET_MAX_CHARS:
            text = text[:CONTEXT_PACKET_MAX_CHARS] + "\n\n(记忆上下文已压缩截断)"
        return text

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
        self._write_text(self.short_term_md_path, self._format_short_term_markdown(data))

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
            self._refresh_context_compression()

    def summarize_memory(self, messages):
        """短期记忆压缩到中期记忆，并在必要时晋升长期记忆"""
        split_idx = len(messages) // 2
        to_summarize = messages[:split_idx]
        remaining = messages[split_idx:]

        try:
            text_block = "\n".join([f"{m.get('role','unknown')}: {m.get('content','...')}" for m in to_summarize])
            summary = self._summarize_block(
                text_block,
                objective='提炼阶段性记忆：关键事实、决策、未完成任务'
            )

            self._append_mid_term(summary)
            self.save_short_term(remaining)
            self._consolidate_mid_to_long()
            self._refresh_context_compression()
            self._append_temp_snapshot('Memory Compression Event', summary)
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
