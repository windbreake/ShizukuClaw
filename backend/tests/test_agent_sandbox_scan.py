"""Tests for sandbox project scanning and debug planning."""

from __future__ import annotations

import json
from pathlib import Path

from app.agent.agent_sandbox import AgentSandbox


def test_scan_project_runtime_detects_dotnet_solution(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "App.sln").write_text("Microsoft Visual Studio Solution File, Format Version 12.00\n", encoding="utf-8")
    (workspace / "Program.cs").write_text("class Program { static void Main() {} }\n", encoding="utf-8")

    sandbox = AgentSandbox(str(workspace))
    scan = sandbox._scan_project_runtime(str(workspace))

    assert scan["project_type"] == "dotnet"
    assert scan["entry"].endswith("App.sln")
    assert "dotnet_restore" in scan["plan"]
    assert "dotnet_build" in scan["plan"]


def test_scan_project_runtime_detects_python_project(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")

    sandbox = AgentSandbox(str(workspace))
    scan = sandbox._scan_project_runtime(str(workspace))

    assert scan["project_type"] == "python"
    assert scan["entry"].endswith("main.py")
    assert "bootstrap_python_env" in scan["plan"]
    assert "py_compile" in scan["plan"]


def test_run_project_debug_includes_scan_stage(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('hello from sandbox')\n", encoding="utf-8")

    sandbox = AgentSandbox(str(workspace))
    raw = sandbox.run_project_debug(target=str(workspace), run_tests=False, start_app=False)
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["project_type"] == "python"
    assert payload["scan"]["project_type"] == "python"
    assert payload["steps"][0]["step"] == "scan"
    assert payload["plan"][0] == "scan"


def test_run_project_debug_missing_target_fails_fast(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sandbox = AgentSandbox(str(workspace))
    missing = workspace / "not-exists-app"
    raw = sandbox.run_project_debug(target=str(missing), run_tests=False, start_app=False)
    payload = json.loads(raw)

    assert payload["ok"] is False
    assert payload["project_type"] == "unknown"
    assert payload["steps"][0]["step"] == "scan"
    assert "does not exist" in payload["steps"][0]["stderr"]
