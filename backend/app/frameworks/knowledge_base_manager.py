# -*- coding: utf-8 -*-
"""
知识库/词库系统 - 存储和管理知识库、词库、术语等
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import os


def _repo_root_from_here() -> str:
    # knowledge_base_manager.py 位于 app/frameworks/，向上一层到 app 根目录
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))


def _resolve_storage_dir(storage_dir: str) -> str:
    repo_root = _repo_root_from_here()
    canonical_data_dir = os.path.join(repo_root, 'db', 'data')
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
    elif normalized.startswith('db/data/'):
        normalized = normalized[len('db/data/'):]
    elif normalized == 'db/data':
        normalized = ''
    elif normalized.startswith('data/'):
        normalized = normalized[len('data/'):]

    return canonical_data_dir if not normalized else os.path.join(canonical_data_dir, normalized)


class EntryType(Enum):
    """条目类型"""
    KNOWLEDGE = "knowledge"    # 知识条目
    TERM = "term"             # 术语条目
    PHRASE = "phrase"         # 短语条目
    FACT = "fact"             # 事实条目
    RULE = "rule"             # 规则条目


@dataclass
class KnowledgeEntry:
    """知识库条目"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    content: str = ""
    entry_type: str = EntryType.KNOWLEDGE.value
    category: str = ""
    tags: List[str] = field(default_factory=list)
    
    # 关键字用于搜索
    keywords: List[str] = field(default_factory=list)
    
    # 关联
    related_ids: List[str] = field(default_factory=list)
    
    # 优先级和权重
    priority: int = 0
    weight: float = 1.0
    
    # 状态
    enabled: bool = True
    is_private: bool = False
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    author: str = ""
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def matches_query(self, query: str) -> bool:
        """检查是否匹配查询"""
        query_lower = query.lower()
        
        # 检查标题
        if query_lower in self.title.lower():
            return True
        
        # 检查内容
        if query_lower in self.content.lower():
            return True
        
        # 检查关键字
        for keyword in self.keywords:
            if query_lower in keyword.lower():
                return True
        
        # 检查标签
        for tag in self.tags:
            if query_lower in tag.lower():
                return True
        
        return False


@dataclass
class Glossary:
    """词库"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    language: str = "zh_CN"
    
    # 词条
    terms: Dict[str, str] = field(default_factory=dict)  # {word: definition}
    
    # 状态
    enabled: bool = True
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeBaseManager:
    """知识库管理器"""
    
    def __init__(self, storage_dir: str = 'data/knowledge_base'):
        """
        初始化知识库管理器
        
        Args:
            storage_dir: 知识库存储目录
        """
        resolved_storage_dir = _resolve_storage_dir(storage_dir)

        self.storage_dir = resolved_storage_dir
        self.entries_file = os.path.join(resolved_storage_dir, 'entries.json')
        self.glossaries_file = os.path.join(resolved_storage_dir, 'glossaries.json')
        self.index_file = os.path.join(resolved_storage_dir, 'index.json')
        
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.glossaries: Dict[str, Glossary] = {}
        self.search_index: Dict[str, List[str]] = {}  # {keyword: [entry_ids]}
        
        # 创建存储目录
        os.makedirs(resolved_storage_dir, exist_ok=True)
        
        # 加载已保存的数据
        self._load_data()
    
    def _load_data(self):
        """加载知识库数据"""
        try:
            if os.path.exists(self.entries_file):
                with open(self.entries_file, 'r', encoding='utf-8') as f:
                    for entry_dict in json.load(f):
                        entry = KnowledgeEntry(**entry_dict)
                        self.entries[entry.id] = entry
            
            if os.path.exists(self.glossaries_file):
                with open(self.glossaries_file, 'r', encoding='utf-8') as f:
                    for glossary_dict in json.load(f):
                        glossary = Glossary(**glossary_dict)
                        self.glossaries[glossary.id] = glossary
            
            # 重建索引
            self._rebuild_index()
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
    
    def _save_data(self):
        """保存知识库数据"""
        try:
            with open(self.entries_file, 'w', encoding='utf-8') as f:
                data = [e.to_dict() for e in self.entries.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open(self.glossaries_file, 'w', encoding='utf-8') as f:
                data = [g.to_dict() for g in self.glossaries.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 保存索引
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving knowledge base: {e}")
    
    def _rebuild_index(self):
        """重建搜索索引"""
        self.search_index = {}
        
        for entry in self.entries.values():
            # 索引标题
            for word in entry.title.split():
                if word not in self.search_index:
                    self.search_index[word] = []
                if entry.id not in self.search_index[word]:
                    self.search_index[word].append(entry.id)
            
            # 索引关键字
            for keyword in entry.keywords:
                if keyword not in self.search_index:
                    self.search_index[keyword] = []
                if entry.id not in self.search_index[keyword]:
                    self.search_index[keyword].append(entry.id)
            
            # 索引标签
            for tag in entry.tags:
                if tag not in self.search_index:
                    self.search_index[tag] = []
                if entry.id not in self.search_index[tag]:
                    self.search_index[tag].append(entry.id)
    
    # ===== Entry 管理 =====
    
    def add_entry(self, entry: KnowledgeEntry) -> str:
        """添加知识库条目"""
        self.entries[entry.id] = entry
        self._rebuild_index()
        self._save_data()
        return entry.id
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """获取条目"""
        entry = self.entries.get(entry_id)
        if entry:
            # 更新访问统计
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
            self._save_data()
        return entry
    
    def list_entries(self, category: Optional[str] = None,
                     entry_type: Optional[str] = None,
                     enabled_only: bool = True) -> List[Dict[str, Any]]:
        """列表查询条目"""
        entries = list(self.entries.values())
        
        if category:
            entries = [e for e in entries if e.category == category]
        
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        
        if enabled_only:
            entries = [e for e in entries if e.enabled]
        
        # 按权重和优先级排序
        entries.sort(key=lambda x: (-x.weight, -x.priority, -x.access_count))
        
        return [e.to_dict() for e in entries]
    
    def search_entries(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索条目"""
        results = []
        searched_ids = set()
        
        # 关键字匹配
        query_lower = query.lower()
        for entry in self.entries.values():
            if entry.id in searched_ids:
                continue
            
            if entry.matches_query(query):
                results.append(entry)
                searched_ids.add(entry.id)
        
        # 按相关性排序（权重、优先级、访问次数）
        results.sort(
            key=lambda x: (-x.weight, -x.priority, -x.access_count)
        )
        
        return [e.to_dict() for e in results[:limit]]
    
    def update_entry(self, entry_id: str, updates: Dict[str, Any]) -> Optional[KnowledgeEntry]:
        """更新条目"""
        entry = self.entries.get(entry_id)
        if not entry:
            return None
        
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        entry.updated_at = datetime.now().isoformat()
        self._rebuild_index()
        self._save_data()
        return entry
    
    def delete_entry(self, entry_id: str) -> bool:
        """删除条目"""
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._rebuild_index()
            self._save_data()
            return True
        
        return False
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set()
        for entry in self.entries.values():
            if entry.category:
                categories.add(entry.category)
        return sorted(list(categories))
    
    # ===== Glossary 管理 =====
    
    def add_glossary(self, glossary: Glossary) -> str:
        """添加词库"""
        self.glossaries[glossary.id] = glossary
        self._save_data()
        return glossary.id
    
    def get_glossary(self, glossary_id: str) -> Optional[Glossary]:
        """获取词库"""
        return self.glossaries.get(glossary_id)
    
    def list_glossaries(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """列表查询词库"""
        glossaries = list(self.glossaries.values())
        
        if enabled_only:
            glossaries = [g for g in glossaries if g.enabled]
        
        return [g.to_dict() for g in glossaries]
    
    def add_term_to_glossary(self, glossary_id: str, term: str, definition: str) -> bool:
        """添加术语到词库"""
        glossary = self.glossaries.get(glossary_id)
        if not glossary:
            return False
        
        glossary.terms[term] = definition
        glossary.updated_at = datetime.now().isoformat()
        self._save_data()
        return True
    
    def remove_term_from_glossary(self, glossary_id: str, term: str) -> bool:
        """从词库删除术语"""
        glossary = self.glossaries.get(glossary_id)
        if not glossary:
            return False
        
        if term in glossary.terms:
            del glossary.terms[term]
            glossary.updated_at = datetime.now().isoformat()
            self._save_data()
            return True
        
        return False
    
    def update_glossary(self, glossary_id: str, updates: Dict[str, Any]) -> Optional[Glossary]:
        """更新词库"""
        glossary = self.glossaries.get(glossary_id)
        if not glossary:
            return None
        
        for key, value in updates.items():
            if hasattr(glossary, key) and key != 'terms':
                setattr(glossary, key, value)
        
        glossary.updated_at = datetime.now().isoformat()
        self._save_data()
        return glossary
    
    def delete_glossary(self, glossary_id: str) -> bool:
        """删除词库"""
        if glossary_id in self.glossaries:
            del self.glossaries[glossary_id]
            self._save_data()
            return True
        
        return False
    
    def lookup_term(self, glossary_id: str, term: str) -> Optional[str]:
        """查找术语定义"""
        glossary = self.glossaries.get(glossary_id)
        if not glossary:
            return None
        
        return glossary.terms.get(term)


# 全局知识库管理器实例
_kb_manager_instance: Optional[KnowledgeBaseManager] = None


def get_knowledge_base_manager() -> KnowledgeBaseManager:
    """获取或创建知识库管理器实例"""
    global _kb_manager_instance
    if _kb_manager_instance is None:
        _kb_manager_instance = KnowledgeBaseManager()
    return _kb_manager_instance
