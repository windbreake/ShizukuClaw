# -*- coding: utf-8 -*-
"""Auto-check and install missing pip dependencies on startup.

- Main project dependencies: read from backend/requirements.txt
- Plugin dependencies: read from each plugin's requirements.txt
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List


def _parse_requirements(requirements_path: str) -> List[str]:
    """Parse a requirements.txt file and return package names."""
    packages = []
    if not os.path.isfile(requirements_path):
        return packages

    with open(requirements_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name before version specifier: pkg~=x, pkg>=x, pkg==x, pkg[x]...
            match = re.match(r"^([a-zA-Z0-9_.-]+(?:\s*\[[^\]]*\])?)", line)
            if match:
                pkg = match.group(1).strip()
                if pkg:
                    packages.append(pkg)
    return packages


def _module_alias(pkg_name: str) -> str:
    """Map pip package name to importable module name when they differ."""
    aliases = {
        "mysql-connector-python": "mysql.connector",
        "psycopg2-binary": "psycopg2",
        "pillow": "PIL",
        "python-dotenv": "dotenv",
        "python-docx": "docx",
        "python-pptx": "pptx",
        "pypdf": "pypdf",
        "reportlab": "reportlab",
        "apscheduler": "apscheduler",
        "Werkzeug": "werkzeug",
        "spglib": "spglib",
        "websockets": "websockets",
        "PyYAML": "yaml",
        "pyyaml": "yaml",
        "openai": "openai",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "colorama": "colorama",
        "requests": "requests",
        "psutil": "psutil",
        "config": "config",
        "flask": "flask",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
        "pytest": "pytest",
        "pytest-benchmark": "pytest_benchmark",
        "openpyxl": "openpyxl",
    }
    return aliases.get(pkg_name, pkg_name.replace("-", "_"))


def _is_installed(pkg_name: str) -> bool:
    """Check if a pip package is installed by trying to import its module."""
    module_name = _module_alias(pkg_name)
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def find_missing(requirements_path: str) -> List[str]:
    """Return list of package names from requirements.txt that are not installed."""
    packages = _parse_requirements(requirements_path)
    return [p for p in packages if not _is_installed(p)]


def install_packages(packages: List[str]) -> bool:
    """Install a list of pip packages. Returns True on success."""
    if not packages:
        return True
    try:
        cmd = [sys.executable, "-m", "pip", "install", *packages]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"[DependencyChecker] pip install failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[DependencyChecker] pip install error: {e}")
        return False


def check_and_install(requirements_path: str, context: str = "") -> bool:
    """Check a requirements.txt and auto-install missing packages.

    Returns True if all dependencies are satisfied (or were installed).
    """
    if not os.path.isfile(requirements_path):
        return True  # No requirements file means no dependencies

    missing = find_missing(requirements_path)
    if not missing:
        return True

    ctx = f"[{context}] " if context else ""
    print(f"{ctx}Missing dependencies: {', '.join(missing)}")
    print(f"{ctx}Auto-installing...")
    success = install_packages(missing)
    if success:
        print(f"{ctx}Dependencies installed successfully.")
    else:
        print(f"{ctx}Warning: some dependencies could not be installed.")
    return success


def check_main_dependencies() -> bool:
    """Check and install main project dependencies from backend/requirements.txt."""
    backend_dir = Path(__file__).parent.parent  # backend/app/core -> backend/app
    requirements_path = backend_dir / "requirements.txt"
    return check_and_install(str(requirements_path), "Main Project")


def check_plugin_dependencies(plugin_dir: str) -> bool:
    """Check and install a single plugin's dependencies from its requirements.txt."""
    req_path = os.path.join(plugin_dir, "requirements.txt")
    plugin_name = os.path.basename(plugin_dir)
    return check_and_install(req_path, f"Plugin:{plugin_name}")


def check_all_plugin_dependencies(plugins_dir: str) -> None:
    """Check and install dependencies for all plugins in a directory."""
    if not os.path.isdir(plugins_dir):
        return

    for item in os.listdir(plugins_dir):
        if item.startswith("_") or item.startswith("."):
            continue
        plugin_dir = os.path.join(plugins_dir, item)
        if not os.path.isdir(plugin_dir):
            continue
        req_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.isfile(req_path):
            check_and_install(req_path, f"Plugin:{item}")
