# -*- coding: utf-8 -*-
"""Benchmark evaluator based on GitHub project pytest-benchmark.

Repository: https://github.com/pytest-dev/pytest-benchmark
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


class BenchmarkRunError(RuntimeError):
    """Raised when benchmark configuration is invalid."""


@dataclass(frozen=True)
class BenchmarkTarget:
    key: str
    test_path: str
    description: str


class GitHubBenchmarkEvaluator:
    """Execute performance benchmark through pytest-benchmark plugin."""

    TARGETS = {
        "systems_api_helpers": BenchmarkTarget(
            key="systems_api_helpers",
            test_path=os.path.join("tests", "benchmarks", "test_systems_api_benchmark.py"),
            description="Benchmark core helper functions in systems_api",
        ),
    }

    def __init__(self, project_root: str | None = None, python_executable: str | None = None):
        # benchmark_evaluator.py 位于 src/tools/，向上两级到项目根目录
        self.project_root = project_root or os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.python_executable = python_executable or sys.executable

    def list_targets(self) -> List[Dict[str, str]]:
        return [
            {
                "key": t.key,
                "test_path": t.test_path,
                "description": t.description,
            }
            for t in self.TARGETS.values()
        ]

    def run(self, target: str, timeout_seconds: int = 180) -> Dict[str, Any]:
        spec = self.TARGETS.get(str(target or "").strip())
        if not spec:
            valid_targets = ", ".join(sorted(self.TARGETS.keys()))
            raise BenchmarkRunError(f"unknown target: {target}; available: {valid_targets}")

        test_path = os.path.join(self.project_root, spec.test_path)
        if not os.path.exists(test_path):
            raise BenchmarkRunError(f"benchmark test not found: {spec.test_path}")

        result_dir = os.path.join(self.project_root, "logs", "benchmarks")
        os.makedirs(result_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_name = f"benchmark_{spec.key}_{ts}.json"
        report_path = os.path.join(result_dir, report_name)

        cmd = [
            self.python_executable,
            "-m",
            "pytest",
            spec.test_path,
            "-q",
            "--benchmark-only",
            "--benchmark-disable-gc",
            "--benchmark-json",
            report_path,
        ]

        proc = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=max(10, int(timeout_seconds or 180)),
        )

        report = {}
        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    report = json.load(f) or {}
            except (OSError, json.JSONDecodeError):
                report = {}

        summary = self._summarize(report)
        return {
            "ok": proc.returncode == 0,
            "target": spec.key,
            "description": spec.description,
            "command": cmd,
            "returncode": int(proc.returncode),
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:],
            "report_path": os.path.relpath(report_path, self.project_root),
            "summary": summary,
        }

    @staticmethod
    def _summarize(report: Dict[str, Any]) -> Dict[str, Any]:
        benchmarks = list(report.get("benchmarks") or [])
        rows = []
        for b in benchmarks:
            stats = dict(b.get("stats") or {})
            rows.append(
                {
                    "name": b.get("name", ""),
                    "fullname": b.get("fullname", ""),
                    "iterations": stats.get("iterations"),
                    "rounds": stats.get("rounds"),
                    "mean_seconds": stats.get("mean"),
                    "stddev_seconds": stats.get("stddev"),
                    "median_seconds": stats.get("median"),
                    "ops": b.get("ops"),
                }
            )
        return {
            "benchmarks_count": len(rows),
            "benchmarks": rows,
        }
