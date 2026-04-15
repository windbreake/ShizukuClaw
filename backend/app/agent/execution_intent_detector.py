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

    # 参考 AstrBot 指令路由：系统指令前缀优先，不直接落入执行自动化。
    SYSTEM_COMMAND_PREFIXES = ('/', '!', '#', '.', '^')

    # 允许通过前缀显式触发执行的命令。
    EXEC_COMMAND_PREFIXES = {
        '/run', '/exec', '/execute', '/debug', '/test', '/start',
        '!run', '!exec', '!debug',
    }

    # 参考 AstrBot 本地 booter 的危险命令规则（简化版）。
    DANGEROUS_COMMAND_PATTERNS = (
        ' rm -rf ',
        ' rm -fr ',
        ' rm -r ',
        ' mkfs',
        ' dd if=',
        ' shutdown',
        ' reboot',
        ' poweroff',
        ' halt',
        ' sudo ',
        ':(){:|:&};:',
        ' kill -9 ',
        ' killall ',
    )
    
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
        raw_text = str(user_input or '').strip()
        source = str(frontend_source or '').strip().lower()

        if not raw_text:
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "empty_input",
                "suggested_target": None,
                "risk_level": "low",
                "allow_auto_execute": False,
            }

        # 执行能力仅面向管理员，避免普通用户误触发。
        if not is_admin:
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "not_admin",
                "suggested_target": None,
                "risk_level": "low",
                "allow_auto_execute": False,
            }

        # 来源门控：sandbox 与 control_panel 可触发，其他来源默认禁用。
        if source not in {'sandbox', 'control_panel'}:
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "context_mismatch",
                "suggested_target": None,
                "risk_level": "low",
                "allow_auto_execute": False,
            }

        # Astr 风格：系统指令前缀优先路由，不将普通指令误判为执行请求。
        if ExecutionIntentDetector._looks_like_non_exec_command(raw_text):
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "system_command_routed",
                "suggested_target": None,
                "risk_level": "low",
                "allow_auto_execute": False,
            }
        
        text_lower = raw_text.lower()
        
        # 检查排除短语
        for phrase in ExecutionIntentDetector.EXCLUSION_PHRASES:
            if phrase.lower() in text_lower:
                return {
                    "is_execution_request": False,
                    "confidence": 0.0,
                    "reason": "excluded_phrase",
                    "suggested_target": None,
                    "risk_level": "low",
                    "allow_auto_execute": False,
                }
        
        # 检查是否包含执行关键词
        has_verb = any(verb.lower() in text_lower for verb in ExecutionIntentDetector.EXECUTION_VERBS)
        if not has_verb:
            return {
                "is_execution_request": False,
                "confidence": 0.0,
                "reason": "no_execution_verb",
                "suggested_target": None,
                "risk_level": "low",
                "allow_auto_execute": False,
            }
        
        # 检查是否在否定语境
        has_negation = any(neg in raw_text for neg in ExecutionIntentDetector.NEGATION_WORDS)
        
        target = ExecutionIntentDetector._extract_target(raw_text)
        has_target = bool(target)

        # 来源分级：sandbox 更偏自动化，control_panel 更偏显式确认
        confidence = 0.9 if source == 'sandbox' else 0.68
        reason = 'explicit_request'

        explicit_phrase = bool(re.search(r'(帮我|请|麻烦).{0,8}(运行|执行|调试|检查|测试|启动)', raw_text, re.IGNORECASE))
        if explicit_phrase:
            confidence += 0.08

        if has_target:
            confidence += 0.18

        if has_negation:
            # 例如："不能执行" -> 强烈降权；"执行了但有问题" -> 轻微降权
            distance_check = ExecutionIntentDetector._check_negation_distance(raw_text)
            if distance_check:
                confidence = min(confidence, 0.32)
                reason = "negation_context_detected"
            else:
                confidence -= 0.08

        # control_panel 下必须“更明确”：没有目标且不含明确祈使短语则不触发执行。
        if source == 'control_panel' and (not has_target) and (not explicit_phrase):
            confidence = min(confidence, 0.45)
            reason = 'insufficient_specificity'

        confidence = max(0.0, min(confidence, 1.0))
        
        # 尝试识别执行目标
        target = target if has_target else None
        
        # 确定风险等级
        risk_level = ExecutionIntentDetector._assess_risk(raw_text, target)

        threshold = 0.62 if source == 'sandbox' else 0.7
        is_execution_request = confidence >= threshold

        # 高风险请求仍可被识别为“执行意图”，但禁止自动执行（仅允许后续确认或人工处理）。
        allow_auto_execute = is_execution_request and risk_level != 'high'

        # 危险模式命中时，明确标记原因，便于前端 trace 展示。
        if risk_level == 'high' and is_execution_request:
            reason = 'dangerous_command_guard'
        
        return {
            "is_execution_request": is_execution_request,
            "confidence": confidence,
            "reason": reason,
            "suggested_target": target,
            "risk_level": risk_level,
            "allow_auto_execute": allow_auto_execute,
        }

    @staticmethod
    def _looks_like_non_exec_command(text: str) -> bool:
        """是否为非执行系统命令（例如 /help、/tool ls）。"""
        raw = str(text or '').strip()
        if not raw:
            return False

        if not raw.startswith(ExecutionIntentDetector.SYSTEM_COMMAND_PREFIXES):
            return False

        lower = raw.lower()
        # 显式执行命令前缀放行，让后续意图判定继续处理。
        if any(lower.startswith(prefix) for prefix in ExecutionIntentDetector.EXEC_COMMAND_PREFIXES):
            return False

        return True
    
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

        # 常见“当前项目”表达，归一化为工作区根目录。
        if re.search(r'(当前项目|这个项目|整个项目|本项目)', str(text or '')):
            return '.'
        
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

        normalized = f" {str(user_input or '').lower()} "

        if any(pattern in normalized for pattern in ExecutionIntentDetector.DANGEROUS_COMMAND_PATTERNS):
            return "high"
        
        # 危险操作
        dangerous_ops = {'rm', 'delete', '删除', 'rmdir', 'format', 'truncate'}
        if any(op in normalized for op in dangerous_ops):
            return "high"
        
        # 中等风险（系统命令）
        risky_ops = {'chmod', 'chown', 'sudo', 'pip install'}
        if any(op in normalized for op in risky_ops):
            return "medium"
        
        # 低风险（只读或安全操作）
        return "low"
