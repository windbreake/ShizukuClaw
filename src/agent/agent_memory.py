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
import re
import time
from datetime import datetime
from src.core.config import PROJECT_ROOT

# 定义文件路径
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace')
MEMORY_ROOT = os.path.join(WORKSPACE_ROOT, 'memory')
PERSONA_MEMORY_ROOT = os.path.join(MEMORY_ROOT, 'personas')
PERSONA_CONFIG_ROOT = os.path.join(PROJECT_ROOT, 'data', 'personas')
PLAN_PATH = os.path.join(WORKSPACE_ROOT, 'plan.md')
LEGACY_MEMORY_ROOT = os.path.join(PROJECT_ROOT, 'agent_datas', 'memory')
LEGACY_PLAN_PATH = os.path.join(PROJECT_ROOT, 'agent_datas', 'plan.md')

GLOBAL_SHORT_TERM_PATH = os.path.join(MEMORY_ROOT, 'short_term.json')
GLOBAL_SHORT_TERM_MD_PATH = os.path.join(MEMORY_ROOT, 'short_term.md')
GLOBAL_MID_TERM_PATH = os.path.join(MEMORY_ROOT, 'mid_term.md')
GLOBAL_LONG_TERM_PATH = os.path.join(MEMORY_ROOT, 'long_term.md')
GLOBAL_CONTEXT_COMPRESSION_PATH = os.path.join(MEMORY_ROOT, 'context_compression.md')
GLOBAL_MEMORY_RULES_PATH = os.path.join(MEMORY_ROOT, 'memory_rules.md')

MAX_SHORT_TERM_TOKENS = 3000
SHORT_TERM_WINDOW = 20
MID_TERM_MAX_CHARS = 12000
LONG_TERM_MAX_CHARS = 20000
CONTEXT_PACKET_MAX_CHARS = 5000
MEMORY_LAYER_DISABLED = True

class AgentMemory:
    def __init__(self, ai_chat_system=None, persona_filename=None):
        self.ai_chat_system = ai_chat_system
        if not os.path.exists(MEMORY_ROOT):
            os.makedirs(MEMORY_ROOT, exist_ok=True)
        os.makedirs(PERSONA_MEMORY_ROOT, exist_ok=True)
        self.current_persona_filename = None
        self.current_persona_key = 'default'
        self.current_persona_label = 'default'
        self.short_term_path = GLOBAL_SHORT_TERM_PATH
        self.short_term_md_path = GLOBAL_SHORT_TERM_MD_PATH
        self.mid_term_path = GLOBAL_MID_TERM_PATH
        self.long_term_path = GLOBAL_LONG_TERM_PATH
        self.context_compression_path = GLOBAL_CONTEXT_COMPRESSION_PATH
        self.memory_rules_path = GLOBAL_MEMORY_RULES_PATH
        self.temp_memory_dir = os.path.join(MEMORY_ROOT, 'temp')
        os.makedirs(self.temp_memory_dir, exist_ok=True)
        self._ensure_global_memory_scaffold()
        self._bootstrap_persona_memory_scaffolds()
        active_persona = persona_filename or self._default_persona_filename()
        self.set_persona_context(active_persona, bootstrap_from_legacy=True)

    def _default_persona_filename(self):
        try:
            from src.core.config import CONFIG
            return str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip() or 'shizuku.json'
        except Exception:
            return 'shizuku.json'

    @staticmethod
    def _normalize_persona_key(persona_filename: str) -> str:
        filename = str(persona_filename or '').strip()
        if not filename:
            return 'default'
        filename = os.path.basename(filename)
        if filename.lower().endswith('.json'):
            filename = filename[:-5]
        filename = re.sub(r'[^A-Za-z0-9_.-]+', '_', filename).strip('._-')
        return filename.lower() or 'default'

    def _scope_paths(self, persona_filename: str = None):
        target_filename = persona_filename if persona_filename is not None else self.current_persona_filename
        key = self._normalize_persona_key(target_filename)
        base_dir = os.path.join(PERSONA_MEMORY_ROOT, key)
        return {
            'key': key,
            'dir': base_dir,
            'short_term_path': os.path.join(base_dir, 'short_term.json'),
            'short_term_md_path': os.path.join(base_dir, 'short_term.md'),
            'mid_term_path': os.path.join(base_dir, 'mid_term.md'),
            'long_term_path': os.path.join(base_dir, 'long_term.md'),
            'context_compression_path': os.path.join(base_dir, 'context_compression.md'),
            'memory_rules_path': os.path.join(base_dir, 'memory_rules.md'),
            'temp_memory_dir': os.path.join(base_dir, 'temp'),
        }

    def _ensure_global_memory_scaffold(self):
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

    def _ensure_persona_scaffold(self, persona_filename: str = None, bootstrap_from_legacy: bool = False):
        paths = self._scope_paths(persona_filename)
        os.makedirs(paths['dir'], exist_ok=True)
        os.makedirs(paths['temp_memory_dir'], exist_ok=True)

        legacy_files = {
            'short_term.json': GLOBAL_SHORT_TERM_PATH,
            'short_term.md': GLOBAL_SHORT_TERM_MD_PATH,
            'mid_term.md': GLOBAL_MID_TERM_PATH,
            'long_term.md': GLOBAL_LONG_TERM_PATH,
            'context_compression.md': GLOBAL_CONTEXT_COMPRESSION_PATH,
            'memory_rules.md': GLOBAL_MEMORY_RULES_PATH,
        }

        defaults = {
            'short_term.json': '[]\n',
            'short_term.md': '# Short Term Memory\n\n暂无短期记忆。\n',
            'mid_term.md': '# Mid Term Memory\n\n暂无中期记忆。\n',
            'long_term.md': '# Long Term Memory\n\n暂无长期记忆。\n',
            'context_compression.md': '# Context Compression Snapshot\n\n暂无压缩上下文。\n',
            'memory_rules.md': "# Memory System Rules\n\n## Layering\n- Short-term memory: keep recent turns and active task details.\n- Mid-term memory: keep episodic summaries of completed blocks and unresolved threads.\n- Long-term memory: keep durable facts, user preferences, and stable decisions.\n\n## Compression Policy\n- Trigger compaction when short-term exceeds token budget.\n- Summarize old chunks into mid-term memory without deleting key facts.\n- Consolidate oversized mid-term memory into long-term memory periodically.\n\n## Quality Rules\n- Prefer factual points over wording style.\n- Preserve unresolved tasks and explicit user requirements.\n- Do not store sensitive secrets unless explicitly required by user.\n",
        }

        for filename, target_path in [
            ('short_term.json', paths['short_term_path']),
            ('short_term.md', paths['short_term_md_path']),
            ('mid_term.md', paths['mid_term_path']),
            ('long_term.md', paths['long_term_path']),
            ('context_compression.md', paths['context_compression_path']),
            ('memory_rules.md', paths['memory_rules_path']),
        ]:
            if os.path.exists(target_path):
                continue
            if bootstrap_from_legacy and os.path.exists(legacy_files[filename]):
                try:
                    with open(legacy_files[filename], 'r', encoding='utf-8') as src:
                        content = src.read()
                    with open(target_path, 'w', encoding='utf-8') as dst:
                        dst.write(content)
                    continue
                except Exception:
                    pass
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(defaults[filename])

    def _bootstrap_persona_memory_scaffolds(self):
        persona_files = []
        if os.path.exists(PERSONA_CONFIG_ROOT):
            try:
                persona_files = [item for item in os.listdir(PERSONA_CONFIG_ROOT) if item.endswith('.json')]
            except Exception:
                persona_files = []
        if not persona_files:
            persona_files = [self._default_persona_filename()]

        for filename in persona_files:
            try:
                self._ensure_persona_scaffold(filename, bootstrap_from_legacy=False)
            except Exception:
                pass

    def set_persona_context(self, persona_filename: str = None, bootstrap_from_legacy: bool = False):
        persona_filename = persona_filename or self._default_persona_filename()
        self.current_persona_filename = persona_filename
        self.current_persona_key = self._normalize_persona_key(persona_filename)
        self.current_persona_label = self.current_persona_key

        paths = self._scope_paths(persona_filename)
        self.short_term_path = paths['short_term_path']
        self.short_term_md_path = paths['short_term_md_path']
        self.mid_term_path = paths['mid_term_path']
        self.long_term_path = paths['long_term_path']
        self.context_compression_path = paths['context_compression_path']
        self.memory_rules_path = paths['memory_rules_path']
        self.temp_memory_dir = paths['temp_memory_dir']
        os.makedirs(self.temp_memory_dir, exist_ok=True)
        self._ensure_persona_scaffold(persona_filename, bootstrap_from_legacy=bootstrap_from_legacy)
        return paths

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

    def build_context_packet(self, persona_filename: str = None):
        if MEMORY_LAYER_DISABLED:
            return "[Persona Scope]\n" + str(self.current_persona_filename or 'default') + "\n\n[Memory]\n记忆层（短/中/长期）已禁用。"
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
        rules = self._read_text(self.memory_rules_path, '')
        compressed = self._read_text(self.context_compression_path, '')
        if not compressed.strip():
            self._refresh_context_compression()
            compressed = self._read_text(self.context_compression_path, '')

        chunks = [
            '[Persona Scope]',
            self.current_persona_filename or self.current_persona_key or 'default',
            '',
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

    def load_short_term(self, persona_filename: str = None):
        if MEMORY_LAYER_DISABLED:
            return []
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
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

    def save_short_term(self, data, persona_filename: str = None):
        if MEMORY_LAYER_DISABLED:
            return
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
        with open(self.short_term_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._write_text(self.short_term_md_path, self._format_short_term_markdown(data))

    def load_long_term(self, persona_filename: str = None):
        if MEMORY_LAYER_DISABLED:
            return "记忆层（短/中/长期）已禁用。"
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
        if os.path.exists(self.long_term_path):
            with open(self.long_term_path, 'r', encoding='utf-8') as f:
                return f.read()
        legacy_long = os.path.join(LEGACY_MEMORY_ROOT, 'long_term.md')
        if os.path.exists(legacy_long):
            with open(legacy_long, 'r', encoding='utf-8') as f:
                return f.read()
        return "暂无长期记忆。"

    def save_long_term(self, content, persona_filename: str = None):
        if MEMORY_LAYER_DISABLED:
            return
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
        with open(self.long_term_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def append_short_term(self, role, content, persona_filename: str = None):
        """添加消息到短期记忆，并在必要时压缩"""
        if MEMORY_LAYER_DISABLED:
            return
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
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

    def summarize_memory(self, messages, persona_filename: str = None):
        """短期记忆压缩到中期记忆，并在必要时晋升长期记忆"""
        if MEMORY_LAYER_DISABLED:
            return
        if persona_filename is not None:
            self.set_persona_context(persona_filename)
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
