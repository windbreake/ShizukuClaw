# -*- coding: utf-8 -*-

import pytest

pytest.importorskip("pytest_benchmark")

from src.services.systems_market_api import _clean_smithery_text, _extract_json_from_text


def test_benchmark_extract_json_from_text(benchmark):
    payload = '{"servers":[{"id":"filesystem-local","name":"Filesystem Local","description":"stdio"}]}'
    result = benchmark(_extract_json_from_text, payload)
    assert isinstance(result, dict)
    assert isinstance(result.get("servers"), list)


def test_benchmark_clean_smithery_text(benchmark):
    noisy = "  ││   Smithery   CLI\n\r\n   output  ...   "
    result = benchmark(_clean_smithery_text, noisy)
    assert isinstance(result, str)
    assert "Smithery" in result
