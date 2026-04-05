"""OneBot 消息回复触发策略。"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterable
from typing import Any, Dict, List, Tuple

_REPLY_STATE = {
    'last_reply_at': {}
}
_STATE_LOCK = threading.Lock()


def _extract_cq_at_targets(text: str) -> List[str]:
    raw = str(text or '')
    return [m.group(1) for m in re.finditer(r'\[CQ:at,qq=([^\],]+)', raw, re.IGNORECASE)]


def _strip_cq_codes(text: str) -> str:
    raw = str(text or '')
    return re.sub(r'\[CQ:[^\]]+\]', ' ', raw, flags=re.IGNORECASE)


def _normalize_keywords(value: Any) -> List[str]:
    if value is None:
        return []

    keywords: List[str] = []
    if isinstance(value, str):
        chunks = re.split(r'[\n,，;；]+', value)
        for chunk in chunks:
            cleaned = chunk.strip()
            if cleaned:
                keywords.append(cleaned)
    elif isinstance(value, Iterable):
        for item in value:
            cleaned = str(item or '').strip()
            if cleaned:
                keywords.append(cleaned)

    deduped: List[str] = []
    seen = set()
    for keyword in keywords:
        lowered = keyword.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(keyword)
    return deduped


def default_reply_policy(existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    existing = existing or {}
    return {
        'enabled': bool(existing.get('enabled', True)),
        'group_mode': str(existing.get('group_mode', 'mention_or_keyword') or 'mention_or_keyword').strip().lower(),
        'private_mode': str(existing.get('private_mode', 'always') or 'always').strip().lower(),
        'cooldown_seconds': max(0, int(existing.get('cooldown_seconds', 10) or 0)),
        'keywords': _normalize_keywords(existing.get('keywords', [])),
        'bot_qq': str(existing.get('bot_qq', '') or '').strip(),
    }


def extract_onebot_message_info(message: Any) -> Dict[str, Any]:
    text_parts: List[str] = []
    at_targets: List[str] = []
    has_at = False

    if isinstance(message, str):
        at_targets = [str(x or '').strip() for x in _extract_cq_at_targets(message) if str(x or '').strip()]
        text = _strip_cq_codes(message).strip()
        has_at = bool(at_targets)
        return {'text': text, 'has_at': has_at or ('@' in text), 'at_targets': at_targets, 'raw': message}

    if isinstance(message, list):
        for segment in message:
            if isinstance(segment, str):
                cleaned = segment.strip()
                if cleaned:
                    text_parts.append(cleaned)
                continue

            if not isinstance(segment, dict):
                continue

            segment_type = str(segment.get('type', '')).strip().lower()
            data = segment.get('data', {}) if isinstance(segment.get('data', {}), dict) else {}

            if segment_type == 'text':
                text_raw = str(data.get('text', '') or '')
                cq_targets = [str(x or '').strip() for x in _extract_cq_at_targets(text_raw) if str(x or '').strip()]
                if cq_targets:
                    has_at = True
                    at_targets.extend(cq_targets)

                cleaned = _strip_cq_codes(text_raw).strip()
                if cleaned:
                    text_parts.append(cleaned)
            elif segment_type == 'at':
                has_at = True
                qq = str(data.get('qq', '') or '').strip()
                if qq:
                    at_targets.append(qq)
                    text_parts.append(f'@{qq}')
                else:
                    text_parts.append('@')
            elif segment_type:
                text_parts.append(f'[{segment_type}]')

        text = ' '.join(text_parts).strip()
        return {'text': text, 'has_at': has_at or ('@' in text), 'at_targets': at_targets, 'raw': message}

    return {'text': '', 'has_at': False, 'at_targets': [], 'raw': message}


def _extract_bot_identity(payload: Dict[str, Any], policy: Dict[str, Any]) -> str:
    candidates = [
        str(policy.get('bot_qq', '') or '').strip(),
        str(payload.get('self_id', '') or '').strip(),
        str(payload.get('bot_id', '') or '').strip(),
        str(payload.get('robot_id', '') or '').strip(),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return ''


def _conversation_key(payload: Dict[str, Any]) -> str:
    message_type = str(payload.get('message_type', 'private') or 'private').strip().lower()
    if message_type == 'group':
        group_id = str(payload.get('group_id', '') or '').strip()
        if group_id:
            return f'group:{group_id}'
    user_id = str(payload.get('user_id', '') or '').strip()
    if user_id:
        return f'{message_type}:{user_id}'
    return message_type


def _keyword_triggered(text: str, keywords: List[str]) -> bool:
    if not text or not keywords:
        return False

    normalized_text = re.sub(r'\s+', ' ', text).strip()

    for keyword in keywords:
        candidate = str(keyword or '').strip()
        if not candidate:
            continue

        escaped = re.escape(candidate)
        if re.fullmatch(r'[A-Za-z0-9_]+', candidate):
            pattern = rf'(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])'
        else:
            pattern = escaped

        if re.search(pattern, normalized_text, re.IGNORECASE):
            return True

    return False


def _mention_triggered(info: Dict[str, Any], bot_qq: str) -> bool:
    if not info.get('has_at'):
        return False

    targets = [str(target or '').strip() for target in info.get('at_targets', []) if str(target or '').strip()]
    if not targets or not bot_qq:
        return False

    return bot_qq in targets


def _to_me_triggered(payload: Dict[str, Any]) -> bool:
    value = payload.get('to_me', False)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return False


def _contains_bothub_command(text: str) -> bool:
    normalized = str(text or '').strip().lower()
    if not normalized:
        return False
    return re.search(r'(^|\s)/bothub(?:\s+\d+)?(?=\s|$)', normalized) is not None


def should_reply_to_onebot_message(payload: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    policy = default_reply_policy(policy)
    if not policy.get('enabled', True):
        return False, {'reason': 'reply policy disabled'}

    info = extract_onebot_message_info(payload.get('message') or payload.get('raw_message') or '')
    text = str(info.get('text', '') or '').strip()
    if not text:
        return False, {'reason': 'empty message', 'conversation_key': _conversation_key(payload), 'message_text': ''}

    message_type = str(payload.get('message_type', 'private') or 'private').strip().lower()
    group_mode = str(policy.get('group_mode', 'mention_or_keyword') or 'mention_or_keyword').strip().lower()
    private_mode = str(policy.get('private_mode', 'always') or 'always').strip().lower()
    keywords = _normalize_keywords(policy.get('keywords', []))
    bot_qq = _extract_bot_identity(payload, policy)

    keyword_hit = _keyword_triggered(text, keywords)
    mention_hit = _mention_triggered(info, bot_qq)
    to_me_hit = _to_me_triggered(payload)

    if _contains_bothub_command(text):
        should_reply = (message_type == 'group') and (mention_hit or to_me_hit)
        return should_reply, {
            'reason': 'bothub command',
            'conversation_key': _conversation_key(payload),
            'message_text': text,
            'keyword_hit': False,
            'mention_hit': mention_hit,
            'to_me_hit': to_me_hit,
            'message_type': message_type,
        }

    should_reply = False
    trigger_reason = 'not matched'

    if message_type == 'group':
        if group_mode == 'always':
            should_reply = True
            trigger_reason = 'group always'
        elif group_mode == 'mention_only':
            should_reply = mention_hit
            trigger_reason = 'group mention'
        elif group_mode == 'keyword_only':
            should_reply = keyword_hit
            trigger_reason = 'group keyword'
        else:
            should_reply = mention_hit or keyword_hit
            trigger_reason = 'group mention_or_keyword'
    else:
        if private_mode == 'always':
            should_reply = True
            trigger_reason = 'private always'
        elif private_mode == 'never':
            should_reply = False
            trigger_reason = 'private disabled'
        elif private_mode == 'mention_only':
            should_reply = mention_hit
            trigger_reason = 'private mention'
        elif private_mode == 'keyword_only':
            should_reply = keyword_hit
            trigger_reason = 'private keyword'
        else:
            should_reply = mention_hit or keyword_hit
            trigger_reason = 'private mention_or_keyword'

    return should_reply, {
        'reason': trigger_reason,
        'conversation_key': _conversation_key(payload),
        'message_text': text,
        'keyword_hit': keyword_hit,
        'mention_hit': mention_hit,
        'message_type': message_type,
    }


def can_reply_now(conversation_key: str, cooldown_seconds: int) -> Tuple[bool, float]:
    cooldown_seconds = max(0, int(cooldown_seconds or 0))
    if cooldown_seconds <= 0:
        return True, 0.0

    now = time.monotonic()
    with _STATE_LOCK:
        last_at = float(_REPLY_STATE['last_reply_at'].get(conversation_key, 0.0) or 0.0)
        elapsed = now - last_at
        if elapsed < cooldown_seconds:
            return False, cooldown_seconds - elapsed
        return True, 0.0


def mark_replied(conversation_key: str) -> None:
    with _STATE_LOCK:
        _REPLY_STATE['last_reply_at'][conversation_key] = time.monotonic()
