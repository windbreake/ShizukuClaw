"""Tests for search intent guard to avoid hijacking execution requests."""

from app.utils.shared_utils import should_search


def test_should_not_search_for_execution_request_cn():
    text = "请在sandbox里启动 snake_game.py 并修复报错"
    assert should_search(text) is False


def test_should_not_search_for_execution_request_en():
    text = "run snake_game.py and fix traceback ModuleNotFoundError"
    assert should_search(text) is False


def test_should_search_for_regular_question():
    text = "今天北京天气怎么样？"
    assert should_search(text) is True
