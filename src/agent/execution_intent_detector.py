# -*- coding: utf-8 -*-
"""
执行意图检测器

功能描述:
    智能检测用户是否明确要求执行/运行某个项目或脚本。
    相比简单正则匹配，提供置信度和原因，支持误触发降级。
"""

import re
from typing import Optional, Dict


class ExecutionIntentDetector:
    """检测用户的执行意图"""
    
    # 执行关键词（动词）
    EXECUTION_VERBS = {
        '运行', '执行', '跑起来', '调试', '检查', '测试',
        '启动', '运行一遍', '试试看', '验证', '检查一下',
        'run', 'execute', 'debug', 'test', 'check', 'start'
    }
    
    # 否定词/消极词（判断是否在否定语境）
    NEGATION_WORDS = {
        '不', '无法', '错误', '问题', '可能', '试过', '已',
        '不要', '别', '禁止', '无需'
    }
    
    # 排除短语（避免误触发）
    EXCLUSION_PHRASES = {
        '代码运行良好',
        '程序运行平稳',
        '运行状态',
        '运行方式',
        '运行环境',
        '运行时间',
        '运行日志'
    }
    
    @staticmethod
    def detect(
        user_input: str,
        is_admin: bool = False,
        frontend_source: str = ''
    ) -> Dict:
        """
        检测执行意图
        
        参数:
            user_input: 用户输入文本
            is_admin: 是否为管理员
            frontend_source: 前端来源（sandbox, control_panel等）
        
        返回:
            {
                "is_execution_request": bool,
                "confidence": float (0-1),
                "reason": str,
                "suggested_target": str or None,
                "risk_level": str  # "high", "medium", "low"
            }
        """
        
        # 基础检查
        if not user_input or not is_admin or frontend_source != 'sandbox':
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "context_mismatch",
                "suggested_target": None,
                "risk_level": "low"
            }
        
        text_lower = user_input.lower()
        
        # 检查排除短语
        for phrase in ExecutionIntentDetector.EXCLUSION_PHRASES:
            if phrase.lower() in text_lower:
                return {
                    "is_execution_request": False,
                    "confidence": 0.0,
                    "reason": "excluded_phrase",
                    "suggested_target": None,
                    "risk_level": "low"
                }
        
        # 检查是否包含执行关键词
        has_verb = any(verb in user_input for verb in ExecutionIntentDetector.EXECUTION_VERBS)
        if not has_verb:
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "no_execution_verb",
                "suggested_target": None,
                "risk_level": "low"
            }
        
        # 检查是否在否定语境
        has_negation = any(neg in user_input for neg in ExecutionIntentDetector.NEGATION_WORDS)
        
        if has_negation:
            # 计算前后距离，确定是否真的是否定
            # 例如："试过了，不行" 不是否定执行请求
            # 例如："不能执行" 才是真的否定
            distance_check = ExecutionIntentDetector._check_negation_distance(user_input)
            confidence = 0.3 if distance_check else 0.9
            reason = "negation_context_detected" if distance_check else "explicit_request"
        else:
            confidence = 0.95
            reason = "explicit_request"
        
        # 尝试识别执行目标
        target = ExecutionIntentDetector._extract_target(user_input)
        
        # 确定风险等级
        risk_level = ExecutionIntentDetector._assess_risk(user_input, target)
        
        return {
            "is_execution_request": confidence > 0.5,
            "confidence": confidence,
            "reason": reason,
            "suggested_target": target,
            "risk_level": risk_level
        }
    
    @staticmethod
    def _extract_target(text: str) -> Optional[str]:
        """从用户输入中提取运行目标 (文件名或项目名)"""
        
        # 匹配模式1: "运行 xxx.py" 或 "执行 xxx"
        patterns = [
            r'(?:运行|执行|调试|运行一遍|跑起来)\s+([^\s，。！？\n]+\.py)\b',
            r'(?:运行|执行|调试|运行一遍|跑起来)\s+([^\s，。！？\n/\\]+(?:/[^\s，。！？\n]+)*)\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                target = match.group(1).strip()
                # 移除尾部的中文标点
                target = re.sub(r'[，。！？，、；：]+$', '', target)
                return target
        
        return None
    
    @staticmethod
    def _check_negation_distance(text: str) -> bool:
        """检查否定词是否真的适用于执行动词"""
        
        # 找出第一个执行动词的位置
        exe_pos = len(text)
        for verb in ExecutionIntentDetector.EXECUTION_VERBS:
            pos = text.find(verb)
            if pos != -1 and pos < exe_pos:
                exe_pos = pos
        
        # 找出最后一个否定词的位置
        neg_pos = -1
        for neg in ExecutionIntentDetector.NEGATION_WORDS:
            pos = text.rfind(neg)
            if pos > neg_pos:
                neg_pos = pos
        
        # 如果否定词在执行动词之后，比如 "执行了，不过有问题"，则不算真正的否定
        if neg_pos > exe_pos:
            return False
        
        # 如果否定词在执行动词之前，且距离较近，才算真正的否定
        distance = exe_pos - neg_pos
        return distance < 20  # 20个字符内
    
    @staticmethod
    def _assess_risk(user_input: str, target: Optional[str]) -> str:
        """评估执行请求的风险等级"""
        
        # 危险操作
        dangerous_ops = {'rm', 'delete', '删除', 'rmdir', 'format', 'truncate'}
        if any(op in user_input.lower() for op in dangerous_ops):
            return "high"
        
        # 中等风险（系统命令）
        risky_ops = {'chmod', 'chown', 'sudo', 'pip install'}
        if any(op in user_input.lower() for op in risky_ops):
            return "medium"
        
        # 低风险（只读或安全操作）
        return "low"
