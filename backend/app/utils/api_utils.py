"""Shared helpers for API route modules."""

from __future__ import annotations

from typing import Any, Dict

from flask import request

BAD_REQUEST_EXCEPTIONS = (ValueError, TypeError, KeyError)


def get_json_body() -> Dict[str, Any]:
    """Return a validated JSON object body or raise ValueError."""
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError('JSON body must be an object')
    return payload
