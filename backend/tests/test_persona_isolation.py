import os
import pytest

import app.agent.ai_chat_system as ai_module
from app.agent.ai_chat_system import AIChatSystem
from app.database import database as db_module
from app.database.database import DatabaseManager


def test_chat_history_isolated_by_persona_table(tmp_path, monkeypatch):
    db_path = tmp_path / 'chat_history.db'
    monkeypatch.setattr(
        db_module,
        'CONFIG',
        {
            'database': {
                'engine': 'sqlite',
                'sqlite_path': str(db_path),
            }
        },
        raising=False,
    )

    manager = DatabaseManager()
    try:
        manager.save_chat('hello alpha', 'reply alpha', persona_filename='alpha.json')
        manager.save_chat('hello beta', 'reply beta', persona_filename='beta.json')

        alpha_rows = manager.get_chat_history(limit=10, persona_filename='alpha.json')
        beta_rows = manager.get_chat_history(limit=10, persona_filename='beta.json')

        assert len(alpha_rows) == 1
        assert len(beta_rows) == 1
        assert alpha_rows[0][1] == 'hello alpha'
        assert beta_rows[0][1] == 'hello beta'

        cursor = manager._new_cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'chat_history_%'")
            table_names = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()

        assert 'chat_history_alpha' in table_names
        assert 'chat_history_beta' in table_names

        manager.clear_chat_history(persona_filename='alpha.json')

        alpha_after_clear = manager.get_chat_history(limit=10, persona_filename='alpha.json')
        beta_after_clear = manager.get_chat_history(limit=10, persona_filename='beta.json')

        assert alpha_after_clear == []
        assert len(beta_after_clear) == 1
        assert beta_after_clear[0][1] == 'hello beta'
    finally:
        manager.close()


def test_migrate_legacy_chat_history_to_persona_tables(tmp_path, monkeypatch):
    db_path = tmp_path / 'chat_history.db'
    monkeypatch.setattr(
        db_module,
        'CONFIG',
        {
            'database': {
                'engine': 'sqlite',
                'sqlite_path': str(db_path),
            }
        },
        raising=False,
    )

    manager = DatabaseManager()
    try:
        cursor = manager._new_cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_input TEXT,
                    ai_response TEXT,
                    image_description TEXT,
                    persona_filename TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "INSERT INTO chat_history (user_input, ai_response, image_description, persona_filename) VALUES (?, ?, ?, ?)",
                ('legacy alpha', 'legacy alpha reply', None, 'alpha.json')
            )
            cursor.execute(
                "INSERT INTO chat_history (user_input, ai_response, image_description, persona_filename) VALUES (?, ?, ?, ?)",
                ('legacy beta', 'legacy beta reply', None, 'beta.json')
            )
            manager.connection.commit()
        finally:
            cursor.close()

        result = manager.migrate_legacy_chat_history_to_persona_tables(delete_legacy=False)
        assert result.get('success') is True
        assert result.get('personas_scanned') == 2

        alpha_rows = manager.get_chat_history(limit=10, persona_filename='alpha.json')
        beta_rows = manager.get_chat_history(limit=10, persona_filename='beta.json')
        assert len(alpha_rows) == 1
        assert len(beta_rows) == 1
        assert alpha_rows[0][1] == 'legacy alpha'
        assert beta_rows[0][1] == 'legacy beta'
    finally:
        manager.close()


def test_tools_should_only_enable_on_execution_intent():
    assert AIChatSystem._should_enable_agent_tools(is_admin=True, is_simple_chat=False, run_request=True) is True
    assert AIChatSystem._should_enable_agent_tools(is_admin=True, is_simple_chat=False, run_request=False) is False
    assert AIChatSystem._should_enable_agent_tools(is_admin=True, is_simple_chat=True, run_request=True) is False
    assert AIChatSystem._should_enable_agent_tools(is_admin=False, is_simple_chat=False, run_request=True) is False


def test_lightweight_chat_mode_should_only_trigger_for_simple_non_exec(monkeypatch):
    monkeypatch.setattr(ai_module.AIChatSystem, 'should_search', staticmethod(lambda _x: False))

    assert AIChatSystem._should_use_lightweight_chat_mode(True, {'is_execution_request': False}, '你好') is True
    assert AIChatSystem._should_use_lightweight_chat_mode(False, {'is_execution_request': False}, '你好') is False
    assert AIChatSystem._should_use_lightweight_chat_mode(True, {'is_execution_request': True}, 'run tests') is False


def test_chat_model_candidates_can_disable_fallback(monkeypatch):
    monkeypatch.setattr(
        ai_module,
        'CONFIG',
        {
            'api': {
                'model': 'primary-model',
                'fallback_models': ['fallback-a', 'fallback-b'],
            }
        },
        raising=False,
    )

    chat = object.__new__(AIChatSystem)

    with_fallback = chat._get_chat_model_candidates(allow_fallback=True)
    no_fallback = chat._get_chat_model_candidates(allow_fallback=False)

    assert with_fallback == ['primary-model', 'fallback-a', 'fallback-b']
    assert no_fallback == ['primary-model']


def test_build_call_policy_for_simple_chat(monkeypatch):
    monkeypatch.setattr(ai_module.AIChatSystem, 'should_search', staticmethod(lambda _x: False))

    policy = AIChatSystem._build_call_policy(
        is_admin=False,
        frontend_source='control_panel',
        normalized_input='你好',
        image=None,
        attachments=None,
        execution_intent={'is_execution_request': False},
    )

    assert policy['is_simple_chat'] is True
    assert policy['enable_tools'] is False
    assert policy['allow_model_fallback'] is False
    assert policy['load_agent_context'] is False


def test_build_call_policy_for_execution_request(monkeypatch):
    monkeypatch.setattr(ai_module.AIChatSystem, 'should_search', staticmethod(lambda _x: False))

    policy = AIChatSystem._build_call_policy(
        is_admin=True,
        frontend_source='control_panel',
        normalized_input='请运行 tests',
        image=None,
        attachments=None,
        execution_intent={'is_execution_request': True, 'allow_auto_execute': True},
    )

    assert policy['run_request'] is True
    assert policy['enable_tools'] is True
    assert policy['allow_model_fallback'] is True
    assert policy['enable_search_pipeline'] is False


def test_build_call_policy_should_not_shortcut_low_signal(monkeypatch):
    monkeypatch.setattr(ai_module.AIChatSystem, 'should_search', staticmethod(lambda _x: False))

    policy = AIChatSystem._build_call_policy(
        is_admin=True,
        frontend_source='control_panel',
        normalized_input='1',
        image=None,
        attachments=None,
        execution_intent={'is_execution_request': False, 'allow_auto_execute': True},
    )

    assert policy['use_low_signal_shortcut'] is False
    assert policy['run_request'] is False


def test_last_call_policy_snapshot_roundtrip():
    chat = object.__new__(AIChatSystem)
    chat._last_call_policy = {}

    chat._set_last_call_policy({'enable_tools': False, 'run_request': False}, route='precheck')
    snapshot = chat.get_last_call_policy()

    assert snapshot['route'] == 'precheck'
    assert snapshot['enable_tools'] is False
    assert snapshot['run_request'] is False
    assert 'timestamp' in snapshot