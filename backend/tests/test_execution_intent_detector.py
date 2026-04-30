"""Regression tests for execution intent gating behavior."""

from app.agent.execution_intent_detector import ExecutionIntentDetector


def test_non_admin_is_never_execution_request():
    result = ExecutionIntentDetector.detect(
        "运行 main.py",
        is_admin=False,
        frontend_source="control_panel",
    )
    assert result["is_execution_request"] is False
    assert result["reason"] == "not_admin"
    assert result["allow_auto_execute"] is False


def test_control_panel_requires_specificity():
    result = ExecutionIntentDetector.detect(
        "运行一下",
        is_admin=True,
        frontend_source="control_panel",
    )
    assert result["is_execution_request"] is False
    assert result["reason"] == "insufficient_specificity"


def test_control_panel_explicit_target_can_execute():
    result = ExecutionIntentDetector.detect(
        "请运行 main.py",
        is_admin=True,
        frontend_source="control_panel",
    )
    assert result["is_execution_request"] is True
    assert result["allow_auto_execute"] is True
    assert result["suggested_target"] == "main.py"


def test_sandbox_is_more_permissive_than_control_panel():
    result = ExecutionIntentDetector.detect(
        "运行一下",
        is_admin=True,
        frontend_source="sandbox",
    )
    assert result["is_execution_request"] is True
    assert result["allow_auto_execute"] is True


def test_system_command_prefix_is_routed_away_from_auto_exec():
    result = ExecutionIntentDetector.detect(
        "/help 运行 main.py",
        is_admin=True,
        frontend_source="control_panel",
    )
    assert result["is_execution_request"] is False
    assert result["reason"] == "system_command_routed"


def test_dangerous_command_is_high_risk_and_blocked_from_auto_exec():
    result = ExecutionIntentDetector.detect(
        "请执行 rm -rf /tmp/test",
        is_admin=True,
        frontend_source="sandbox",
    )
    assert result["is_execution_request"] is True
    assert result["risk_level"] == "high"
    assert result["allow_auto_execute"] is False
    assert result["reason"] == "dangerous_command_guard"
