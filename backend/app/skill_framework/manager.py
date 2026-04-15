# -*- coding: utf-8 -*-
"""Lightweight skill manager compatible with SKILL.md directory layout."""

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class SkillMeta:
    """Metadata shown in admin UI."""

    skill_id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    path: str = ""
    has_scripts: bool = False
    has_references: bool = False
    enabled: bool = True


class SkillManager:
    """Discover, parse and manage skills from db/data/skills."""

    def __init__(self, project_root: str):
        self.logger = logging.getLogger("skill_framework")
        self.project_root = project_root
        self.config_path = os.path.join(project_root, "data", "config.json")
        self.skills_dir = os.path.join(project_root, "db", "data", "skills")
        self.legacy_skills_dir = os.path.join(project_root, "data", "skills")
        self._skills: Dict[str, SkillMeta] = {}
        self._skill_policies: Dict[str, dict] = {}
        self._framework_enabled = True

    @staticmethod
    def _default_policy() -> dict:
        return {
            "enabled": True,
            "allow_model_invocation": True,
        }

    def _normalize_policy(self, policy: dict = None) -> dict:
        policy = policy or {}
        out = dict(self._default_policy())
        out["enabled"] = bool(policy.get("enabled", out["enabled"]))
        out["allow_model_invocation"] = bool(
            policy.get("allow_model_invocation", out["allow_model_invocation"])
        )
        return out

    def _read_framework_config(self) -> dict:
        default_cfg = {"enabled": True, "skills": {}}
        if not os.path.exists(self.config_path):
            return default_cfg
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            fw = config_data.get("skill_framework", {})
            if not isinstance(fw, dict):
                return default_cfg
            return {
                "enabled": bool(fw.get("enabled", True)),
                "skills": fw.get("skills", {}) if isinstance(fw.get("skills", {}), dict) else {},
            }
        except Exception:
            return default_cfg

    def _write_framework_config(self, framework_config: dict) -> None:
        try:
            config_data = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            config_data["skill_framework"] = framework_config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.logger.warning("Failed to persist skill framework config: %s", exc)

    def _load_policies_from_config(self) -> None:
        fw = self._read_framework_config()
        self._framework_enabled = bool(fw.get("enabled", True))
        raw_skills = fw.get("skills", {})
        self._skill_policies = {}
        for skill_id, policy in raw_skills.items():
            self._skill_policies[str(skill_id)] = self._normalize_policy(policy)

    def _save_policies_to_config(self) -> None:
        fw = self._read_framework_config()
        fw["enabled"] = self._framework_enabled
        fw["skills"] = self._skill_policies
        self._write_framework_config(fw)

    def _parse_frontmatter(self, text: str) -> dict:
        # Compatible with OpenClaw-style YAML frontmatter for common key:value lines.
        content = text or ""
        if not content.startswith("---"):
            return {}

        end = content.find("\n---", 3)
        if end < 0:
            return {}

        frontmatter = content[3:end].strip("\n")
        result = {}
        for raw_line in frontmatter.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip().strip("\"").strip("'")
            result[key] = value
        return result

    def _build_skill_meta(self, skill_dir: str) -> SkillMeta:
        skill_id = os.path.basename(skill_dir)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        fm = self._parse_frontmatter(content)
        name = fm.get("name") or skill_id
        description = fm.get("description") or ""
        version = fm.get("version") or "0.1.0"
        author = fm.get("author") or ""

        if not description:
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            for ln in lines:
                if ln.startswith("#"):
                    continue
                description = ln[:120]
                break

        scripts_dir = os.path.join(skill_dir, "scripts")
        refs_dir = os.path.join(skill_dir, "references")

        policy = self._skill_policies.get(skill_id, self._default_policy())
        return SkillMeta(
            skill_id=skill_id,
            name=name,
            description=description,
            version=version,
            author=author,
            path=skill_dir,
            has_scripts=os.path.isdir(scripts_dir),
            has_references=os.path.isdir(refs_dir),
            enabled=bool(policy.get("enabled", True)),
        )

    def _discover_skills(self) -> Dict[str, SkillMeta]:
        discovered: Dict[str, SkillMeta] = {}
        scan_dirs = [self.skills_dir]
        if self.legacy_skills_dir != self.skills_dir:
            scan_dirs.append(self.legacy_skills_dir)

        for skills_dir in scan_dirs:
            if not os.path.isdir(skills_dir):
                continue

            for item in os.listdir(skills_dir):
                if item.startswith("_"):
                    continue
                skill_dir = os.path.join(skills_dir, item)
                if not os.path.isdir(skill_dir):
                    continue
                skill_md = os.path.join(skill_dir, "SKILL.md")
                if not os.path.exists(skill_md):
                    continue
                try:
                    meta = self._build_skill_meta(skill_dir)
                    discovered[meta.skill_id] = meta
                except Exception as exc:
                    self.logger.warning("Failed to load skill '%s': %s", item, exc)

        if not os.path.isdir(self.skills_dir):
            os.makedirs(self.skills_dir, exist_ok=True)
        return discovered

    def load_all(self) -> None:
        self._load_policies_from_config()
        self._skills = self._discover_skills()
        for sid in self._skills.keys():
            if sid not in self._skill_policies:
                self._skill_policies[sid] = self._default_policy()
            self._skills[sid].enabled = bool(self._skill_policies[sid].get("enabled", True))
        self._save_policies_to_config()

    def reload_all(self) -> None:
        self._skills = {}
        self.load_all()

    def get_skill_policy(self, skill_id: str) -> dict:
        return dict(self._skill_policies.get(skill_id, self._default_policy()))

    def update_skill_policy(self, skill_id: str, policy: dict, persist: bool = True) -> dict:
        if not skill_id:
            raise ValueError("skill_id is required")
        merged = self.get_skill_policy(skill_id)
        merged.update(policy or {})
        normalized = self._normalize_policy(merged)
        self._skill_policies[skill_id] = normalized
        skill = self._skills.get(skill_id)
        if skill is not None:
            skill.enabled = bool(normalized.get("enabled", True))
        if persist:
            self._save_policies_to_config()
        return normalized

    def set_framework_enabled(self, enabled: bool, persist: bool = True) -> None:
        self._framework_enabled = bool(enabled)
        if persist:
            self._save_policies_to_config()

    def delete_skill_project(self, skill_id: str) -> dict:
        """Delete skill directory and unregister from manager."""
        sid = str(skill_id or '').strip()
        if not sid:
            raise ValueError('skill_id is required')

        skill = self._skills.get(sid)
        if not skill:
            raise ValueError(f'Skill not found: {sid}')

        skill_path = os.path.abspath(str(skill.path or ''))
        skills_root = os.path.abspath(self.skills_dir)
        if not skill_path or not skill_path.startswith(skills_root + os.sep):
            raise ValueError('Invalid skill path')

        removed_from_disk = False
        if os.path.exists(skill_path):
            shutil.rmtree(skill_path)
            removed_from_disk = True

        self._skills.pop(sid, None)
        self._skill_policies.pop(sid, None)
        self._save_policies_to_config()

        return {
            'skill_id': sid,
            'path': skill_path,
            'removed_from_disk': removed_from_disk,
        }

    def get_framework_status(self) -> dict:
        items = []
        for sid in sorted(self._skills.keys()):
            skill = self._skills[sid]
            skill_dict = asdict(skill)
            skill_dict["policy"] = self.get_skill_policy(sid)
            items.append(skill_dict)

        return {
            "enabled": self._framework_enabled,
            "loaded_skills": [x["skill_id"] for x in items],
            "skills": items,
            "skills_dir": self.skills_dir,
            "skill_count": len(items),
        }
