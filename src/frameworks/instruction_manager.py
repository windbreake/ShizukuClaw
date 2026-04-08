# -*- coding: utf-8 -*-
"""
自定义指令系统 - Agent行为设定、人格配置等（参考AstR BOT）
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import os


def _repo_root_from_here() -> str:
    # instruction_manager.py 位于 src/frameworks/，向上两级到项目根目录
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _resolve_storage_dir(storage_dir: str) -> str:
    repo_root = _repo_root_from_here()
    canonical_data_dir = os.path.join(repo_root, 'data')
    legacy_data_dir = os.path.join(repo_root, 'src', 'data')

    if os.path.isabs(storage_dir):
        normalized_abs = os.path.normpath(storage_dir)
        if normalized_abs == legacy_data_dir or normalized_abs.startswith(legacy_data_dir + os.sep):
            rel = os.path.relpath(normalized_abs, legacy_data_dir)
            return canonical_data_dir if rel == '.' else os.path.join(canonical_data_dir, rel)
        return normalized_abs

    normalized = storage_dir.replace('\\', '/').lstrip('./')
    if normalized.startswith('src/data/'):
        normalized = normalized[len('src/data/'):]
    elif normalized == 'src/data':
        normalized = ''
    elif normalized.startswith('data/'):
        normalized = normalized[len('data/'):]

    return canonical_data_dir if not normalized else os.path.join(canonical_data_dir, normalized)


class InstructionType(Enum):
    """指令类型"""
    SYSTEM_PROMPT = "system_prompt"      # 系统指令
    PERSONALITY = "personality"          # 人格设定
    BEHAVIOR = "behavior"               # 行为规则
    TRIGGER = "trigger"                 # 触发规则
    RESPONSE_TEMPLATE = "response_template"  # 回复模板


@dataclass
class AgentInstruction:
    """Agent自定义指令"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    instruction_type: str = InstructionType.SYSTEM_PROMPT.value
    
    # 指令内容
    content: str = ""
    
    # 应用范围
    target_agents: List[str] = field(default_factory=list)  # 空列表表示全局
    
    # 优先级（越高越优先）
    priority: int = 0
    
    # 应用条件
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    enabled: bool = True
    
    # 版本控制
    version: str = "1.0"
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Personality:
    """Agent人格配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    
    # 基础特性
    traits: Dict[str, float] = field(default_factory=dict)  # {trait: score (0-1)}
    # 例如: {"cheerfulness": 0.8, "professionalism": 0.6, "humor": 0.7}
    
    # 语言风格
    tone: str = "neutral"
    speaking_style: str = ""  # 例如: "casual", "formal", "humorous"
    
    # 偏好设置
    preferences: Dict[str, Any] = field(default_factory=dict)
    response_length: str = "medium"  # short, medium, long
    emoji_usage: bool = True
    
    # 禁用项
    disabled_features: List[str] = field(default_factory=list)
    
    # 状态
    enabled: bool = True
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BehaviorRule:
    """行为规则"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    
    # 触发条件
    trigger_pattern: str = ""  # 正则表达式或关键字
    trigger_type: str = "keyword"  # keyword, regex, intent
    
    # 执行动作
    action_type: str = "response"  # response, command, function
    action_content: str = ""
    
    # 参数
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 优先级和权重
    priority: int = 0
    weight: float = 1.0
    
    # 限制条件
    conditions: Dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int = 0
    max_trigger_per_day: Optional[int] = None
    
    # 状态
    enabled: bool = True
    
    # 统计信息
    trigger_count: int = 0
    last_triggered: Optional[str] = None
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InstructionManager:
    """指令管理器"""
    
    def __init__(self, storage_dir: str = 'data/instructions'):
        """
        初始化指令管理器
        
        Args:
            storage_dir: 指令存储目录
        """
        resolved_storage_dir = _resolve_storage_dir(storage_dir)

        self.storage_dir = resolved_storage_dir
        self.instructions_file = os.path.join(resolved_storage_dir, 'instructions.json')
        self.personalities_file = os.path.join(resolved_storage_dir, 'personalities.json')
        self.behavior_rules_file = os.path.join(resolved_storage_dir, 'behavior_rules.json')
        
        self.instructions: Dict[str, AgentInstruction] = {}
        self.personalities: Dict[str, Personality] = {}
        self.behavior_rules: Dict[str, BehaviorRule] = {}
        
        # 创建存储目录
        os.makedirs(resolved_storage_dir, exist_ok=True)
        
        # 加载已保存的数据
        self._load_data()
    
    def _load_data(self):
        """加载指令数据"""
        try:
            if os.path.exists(self.instructions_file):
                with open(self.instructions_file, 'r', encoding='utf-8') as f:
                    for instr_dict in json.load(f):
                        instr = AgentInstruction(**instr_dict)
                        self.instructions[instr.id] = instr
            
            if os.path.exists(self.personalities_file):
                with open(self.personalities_file, 'r', encoding='utf-8') as f:
                    for pers_dict in json.load(f):
                        pers = Personality(**pers_dict)
                        self.personalities[pers.id] = pers
            
            if os.path.exists(self.behavior_rules_file):
                with open(self.behavior_rules_file, 'r', encoding='utf-8') as f:
                    for rule_dict in json.load(f):
                        rule = BehaviorRule(**rule_dict)
                        self.behavior_rules[rule.id] = rule
        except Exception as e:
            print(f"Error loading instruction data: {e}")
    
    def _save_data(self):
        """保存指令数据"""
        try:
            with open(self.instructions_file, 'w', encoding='utf-8') as f:
                data = [i.to_dict() for i in self.instructions.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.personalities_file, 'w', encoding='utf-8') as f:
                data = [p.to_dict() for p in self.personalities.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.behavior_rules_file, 'w', encoding='utf-8') as f:
                data = [r.to_dict() for r in self.behavior_rules.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving instruction data: {e}")
    
    # ===== Instruction 管理 =====
    
    def add_instruction(self, instruction: AgentInstruction) -> str:
        """添加指令"""
        self.instructions[instruction.id] = instruction
        self._save_data()
        return instruction.id
    
    def get_instruction(self, instruction_id: str) -> Optional[AgentInstruction]:
        """获取指令"""
        return self.instructions.get(instruction_id)
    
    def list_instructions(self, instruction_type: Optional[str] = None,
                         agent_id: Optional[str] = None,
                         enabled_only: bool = True) -> List[Dict[str, Any]]:
        """列表查询指令"""
        instructions = list(self.instructions.values())
        
        if instruction_type:
            instructions = [i for i in instructions if i.instruction_type == instruction_type]
        
        if agent_id:
            instructions = [
                i for i in instructions 
                if not i.target_agents or agent_id in i.target_agents
            ]
        
        if enabled_only:
            instructions = [i for i in instructions if i.enabled]
        
        # 按优先级排序
        instructions.sort(key=lambda x: -x.priority)
        
        return [i.to_dict() for i in instructions]
    
    def update_instruction(self, instruction_id: str, 
                          updates: Dict[str, Any]) -> Optional[AgentInstruction]:
        """更新指令"""
        instruction = self.instructions.get(instruction_id)
        if not instruction:
            return None
        
        for key, value in updates.items():
            if hasattr(instruction, key):
                setattr(instruction, key, value)
        
        instruction.updated_at = datetime.now().isoformat()
        self._save_data()
        return instruction
    
    def delete_instruction(self, instruction_id: str) -> bool:
        """删除指令"""
        if instruction_id in self.instructions:
            del self.instructions[instruction_id]
            self._save_data()
            return True
        
        return False
    
    def get_agent_instructions(self, agent_id: str) -> str:
        """获取Agent的完整指令集（用于系统提示）"""
        instructions = self.list_instructions(agent_id=agent_id, enabled_only=True)
        
        # 按指令类型分组
        system_prompts = [i for i in instructions if i['instruction_type'] == InstructionType.SYSTEM_PROMPT.value]
        behaviors = [i for i in instructions if i['instruction_type'] == InstructionType.BEHAVIOR.value]
        
        # 组合指令
        prompt_parts = []
        
        for prompt in system_prompts:
            prompt_parts.append(prompt['content'])
        
        for behavior in behaviors:
            prompt_parts.append(f"行为规则: {behavior['content']}")
        
        return "\n\n".join(prompt_parts)
    
    # ===== Personality 管理 =====
    
    def add_personality(self, personality: Personality) -> str:
        """添加人格"""
        self.personalities[personality.id] = personality
        self._save_data()
        return personality.id
    
    def get_personality(self, personality_id: str) -> Optional[Personality]:
        """获取人格"""
        return self.personalities.get(personality_id)
    
    def list_personalities(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """列表查询人格"""
        personalities = list(self.personalities.values())
        
        if enabled_only:
            personalities = [p for p in personalities if p.enabled]
        
        return [p.to_dict() for p in personalities]
    
    def update_personality(self, personality_id: str,
                          updates: Dict[str, Any]) -> Optional[Personality]:
        """更新人格"""
        personality = self.personalities.get(personality_id)
        if not personality:
            return None
        
        for key, value in updates.items():
            if hasattr(personality, key):
                setattr(personality, key, value)
        
        personality.updated_at = datetime.now().isoformat()
        self._save_data()
        return personality
    
    def delete_personality(self, personality_id: str) -> bool:
        """删除人格"""
        if personality_id in self.personalities:
            del self.personalities[personality_id]
            self._save_data()
            return True
        
        return False
    
    # ===== BehaviorRule 管理 =====
    
    def add_behavior_rule(self, rule: BehaviorRule) -> str:
        """添加行为规则"""
        self.behavior_rules[rule.id] = rule
        self._save_data()
        return rule.id
    
    def get_behavior_rule(self, rule_id: str) -> Optional[BehaviorRule]:
        """获取行为规则"""
        return self.behavior_rules.get(rule_id)
    
    def list_behavior_rules(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """列表查询行为规则"""
        rules = list(self.behavior_rules.values())
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        # 按优先级排序
        rules.sort(key=lambda x: (-x.priority, -x.weight))
        
        return [r.to_dict() for r in rules]
    
    def update_behavior_rule(self, rule_id: str,
                            updates: Dict[str, Any]) -> Optional[BehaviorRule]:
        """更新行为规则"""
        rule = self.behavior_rules.get(rule_id)
        if not rule:
            return None
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        rule.updated_at = datetime.now().isoformat()
        self._save_data()
        return rule
    
    def delete_behavior_rule(self, rule_id: str) -> bool:
        """删除行为规则"""
        if rule_id in self.behavior_rules:
            del self.behavior_rules[rule_id]
            self._save_data()
            return True
        
        return False
    
    def check_behavior_rules(self, message: str, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """检查匹配的行为规则"""
        import re
        
        matching_rules = []
        
        for rule in self.list_behavior_rules(enabled_only=True):
            if rule['trigger_type'] == 'keyword':
                if rule['trigger_pattern'].lower() in message.lower():
                    matching_rules.append(rule)
            
            elif rule['trigger_type'] == 'regex':
                try:
                    if re.search(rule['trigger_pattern'], message, re.IGNORECASE):
                        matching_rules.append(rule)
                except:
                    pass
        
        return matching_rules


# 全局指令管理器实例
_instr_manager_instance: Optional[InstructionManager] = None


def get_instruction_manager() -> InstructionManager:
    """获取或创建指令管理器实例"""
    global _instr_manager_instance
    if _instr_manager_instance is None:
        _instr_manager_instance = InstructionManager()
    return _instr_manager_instance
