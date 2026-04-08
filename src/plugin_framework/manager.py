# -*- coding: utf-8 -*-
"""Plugin manager with command/rule dispatch and dynamic loading."""

import json
import importlib.util
import inspect
import logging
import os
import shutil
import time
import traceback
from urllib.parse import urlparse
from typing import Dict, List

from .base import PluginContext, PluginMeta, PluginResult
from .registry import PluginRegistry


class PluginManager:
    """Load plugins and dispatch command/rule hooks."""

    def __init__(self, chat_system, external_plugins_dir=None):
        self.chat_system = chat_system
        self.registry = PluginRegistry()
        self.logger = logging.getLogger("plugin_framework")
        self._loaded_plugins: List[str] = []
        self._plugin_meta: Dict[str, PluginMeta] = {}
        self._plugin_policies: Dict[str, dict] = {}
        self._plugin_projects: Dict[str, str] = {}
        self._framework_enabled = True
        self._started = False
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(self.project_root, "data", "config.json")
        # Plugin projects are stored under data/plungin/<plugin_project>/
        self.external_plugins_dir = external_plugins_dir or os.path.join(self.project_root, "data", "plungin")

    @staticmethod
    def _default_policy() -> dict:
        return {
            "enabled": True,
            "allow_network": False,
            "allowed_domains": [],
            "allowed_commands": [],
            "max_execution_ms": 10000
        }

    def _normalize_policy(self, policy: dict = None) -> dict:
        policy = policy or {}
        out = dict(self._default_policy())
        out["enabled"] = bool(policy.get("enabled", out["enabled"]))
        out["allow_network"] = bool(policy.get("allow_network", out["allow_network"]))

        domains = policy.get("allowed_domains", out["allowed_domains"])
        if not isinstance(domains, list):
            domains = []
        out["allowed_domains"] = [str(x).strip().lower() for x in domains if str(x).strip()]

        commands = policy.get("allowed_commands", out["allowed_commands"])
        if not isinstance(commands, list):
            commands = []
        out["allowed_commands"] = [str(x).strip().lower().lstrip("/") for x in commands if str(x).strip()]

        try:
            timeout_ms = int(policy.get("max_execution_ms", out["max_execution_ms"]))
        except Exception:
            timeout_ms = out["max_execution_ms"]
        out["max_execution_ms"] = max(100, timeout_ms)
        return out

    def _read_framework_config(self) -> dict:
        default_cfg = {"enabled": True, "plugins": {}}
        if not os.path.exists(self.config_path):
            return default_cfg
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            fw = config_data.get("plugin_framework", {})
            if not isinstance(fw, dict):
                return default_cfg
            return {
                "enabled": bool(fw.get("enabled", True)),
                "plugins": fw.get("plugins", {}) if isinstance(fw.get("plugins", {}), dict) else {}
            }
        except Exception:
            return default_cfg

    def _write_framework_config(self, framework_config: dict) -> None:
        try:
            config_data = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            config_data["plugin_framework"] = framework_config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.logger.warning("Failed to persist plugin framework config: %s", exc)

    def _load_policies_from_config(self) -> None:
        fw = self._read_framework_config()
        self._framework_enabled = bool(fw.get("enabled", True))
        raw_plugins = fw.get("plugins", {})
        self._plugin_policies = {}
        for plugin_name, policy in raw_plugins.items():
            self._plugin_policies[str(plugin_name)] = self._normalize_policy(policy)

    def _save_policies_to_config(self) -> None:
        fw = self._read_framework_config()
        fw["enabled"] = self._framework_enabled
        fw["plugins"] = self._plugin_policies
        self._write_framework_config(fw)

    def _register_plugin_meta(self, plugin_name: str, meta: PluginMeta) -> None:
        self._plugin_meta[plugin_name] = meta
        if plugin_name not in self._plugin_policies:
            self._plugin_policies[plugin_name] = self._default_policy()

    def _make_plugin_meta(self, module_or_obj, plugin_name: str) -> PluginMeta:
        meta_raw = getattr(module_or_obj, "PLUGIN_META", None)
        if isinstance(meta_raw, dict):
            deps = meta_raw.get("dependencies", [])
            if not isinstance(deps, list):
                deps = []
            return PluginMeta(
                name=str(meta_raw.get("name") or plugin_name),
                version=str(meta_raw.get("version") or "0.1.0"),
                description=str(meta_raw.get("description") or ""),
                author=str(meta_raw.get("author") or ""),
                dependencies=[str(x).strip() for x in deps if str(x).strip()]
            )
        return PluginMeta(name=plugin_name)

    def _dependencies_satisfied(self, meta: PluginMeta) -> bool:
        for dep in meta.dependencies:
            if dep not in self._loaded_plugins:
                self.logger.warning("Plugin '%s' skipped, missing dependency '%s'", meta.name, dep)
                return False
        return True

    def get_plugin_policy(self, plugin_name: str) -> dict:
        return dict(self._plugin_policies.get(plugin_name, self._default_policy()))

    def update_plugin_policy(self, plugin_name: str, policy: dict, persist: bool = True) -> dict:
        if not plugin_name:
            raise ValueError("plugin_name is required")
        merged = self.get_plugin_policy(plugin_name)
        merged.update(policy or {})
        normalized = self._normalize_policy(merged)
        self._plugin_policies[plugin_name] = normalized
        if persist:
            self._save_policies_to_config()
        return normalized

    def ensure_plugin_policy(self, plugin_name: str, default_policy: dict, persist: bool = False) -> dict:
        if plugin_name not in self._plugin_policies:
            normalized = self._normalize_policy(default_policy)
            self._plugin_policies[plugin_name] = normalized
            if persist:
                self._save_policies_to_config()
            return normalized
        return self.get_plugin_policy(plugin_name)

    def set_framework_enabled(self, enabled: bool, persist: bool = True) -> None:
        self._framework_enabled = bool(enabled)
        if persist:
            self._save_policies_to_config()

    def _is_plugin_enabled(self, plugin_name: str) -> bool:
        return bool(self.get_plugin_policy(plugin_name).get("enabled", True))

    def _is_command_allowed(self, plugin_name: str, command: str) -> bool:
        policy = self.get_plugin_policy(plugin_name)
        allowed = policy.get("allowed_commands", [])
        if not allowed:
            return True
        return (command or "").strip().lower().lstrip("/") in allowed

    def validate_url_for_plugin(self, plugin_name: str, url: str) -> tuple[bool, str]:
        policy = self.get_plugin_policy(plugin_name)
        if not policy.get("allow_network", False):
            return False, f"Plugin '{plugin_name}' network access disabled by policy"

        domains = policy.get("allowed_domains", [])
        if not domains:
            return True, ""

        try:
            hostname = (urlparse(url).hostname or "").lower()
        except Exception:
            hostname = ""

        if not hostname:
            return False, "Invalid URL"

        for allowed in domains:
            if hostname == allowed or hostname.endswith("." + allowed):
                return True, ""
        return False, f"Domain '{hostname}' is not allowed for plugin '{plugin_name}'"

    def _run_with_policy(self, plugin_name: str, run_callable):
        start = time.perf_counter()
        result = run_callable()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        max_ms = self.get_plugin_policy(plugin_name).get("max_execution_ms", 10000)
        if elapsed_ms > max_ms:
            return PluginResult(
                handled=True,
                response=f"插件执行超时: {plugin_name} ({elapsed_ms}ms > {max_ms}ms)"
            )
        return result

    def _hook_summary_for_plugin(self, plugin_name: str) -> dict:
        return {
            "on_startup": sum(1 for _, n in self.registry.startup_handlers if n == plugin_name),
            "on_shutdown": sum(1 for _, n in self.registry.shutdown_handlers if n == plugin_name),
            "on_message": sum(1 for _, n, _ in self.registry.message_handlers if n == plugin_name),
            "on_response": sum(1 for _, n in self.registry.response_handlers if n == plugin_name),
            "on_error": sum(1 for _, n in self.registry.error_handlers if n == plugin_name)
        }

    def _unregister_plugin(self, plugin_name: str) -> None:
        self.registry.command_handlers = {
            cmd: item for cmd, item in self.registry.command_handlers.items() if item[1] != plugin_name
        }
        self.registry.regex_rules = [rule for rule in self.registry.regex_rules if rule.plugin_name != plugin_name]
        self.registry.response_handlers = [item for item in self.registry.response_handlers if item[1] != plugin_name]
        self.registry.message_handlers = [item for item in self.registry.message_handlers if item[1] != plugin_name]
        self.registry.startup_handlers = [item for item in self.registry.startup_handlers if item[1] != plugin_name]
        self.registry.shutdown_handlers = [item for item in self.registry.shutdown_handlers if item[1] != plugin_name]
        self.registry.error_handlers = [item for item in self.registry.error_handlers if item[1] != plugin_name]
        if plugin_name in self._loaded_plugins:
            self._loaded_plugins = [name for name in self._loaded_plugins if name != plugin_name]
        self._plugin_meta.pop(plugin_name, None)
        self._plugin_projects.pop(plugin_name, None)

    def _sync_removed_external_plugins(self) -> None:
        removed_plugins = []
        for plugin_name, project_path in list(self._plugin_projects.items()):
            if project_path and not os.path.exists(project_path):
                removed_plugins.append(plugin_name)

        for plugin_name in removed_plugins:
            self.logger.info("Plugin project removed from disk, unregistering: %s", plugin_name)
            self._unregister_plugin(plugin_name)

    def delete_plugin_project(self, plugin_name: str) -> dict:
        """Delete an external plugin project from disk and unregister it safely."""
        name = str(plugin_name or '').strip()
        if not name:
            raise ValueError("plugin_name is required")
        if name.lower().startswith('builtin.'):
            raise ValueError("Built-in plugins cannot be deleted")

        project_path = self._plugin_projects.get(name, '')
        if not project_path:
            raise ValueError(f"Plugin not found: {name}")

        abs_project = os.path.abspath(project_path)
        abs_external_root = os.path.abspath(self.external_plugins_dir)
        if not abs_project.startswith(abs_external_root + os.sep):
            raise ValueError("Only external plugins can be deleted")

        removed_from_disk = False
        if os.path.exists(abs_project):
            shutil.rmtree(abs_project)
            removed_from_disk = True

        self._unregister_plugin(name)
        if name in self._plugin_policies:
            self._plugin_policies.pop(name, None)
            self._save_policies_to_config()

        return {
            "plugin_name": name,
            "project_path": abs_project,
            "removed_from_disk": removed_from_disk
        }

    def get_framework_status(self) -> dict:
        self._sync_removed_external_plugins()
        plugins = []
        for plugin_name in self._loaded_plugins:
            meta = self._plugin_meta.get(plugin_name, PluginMeta(name=plugin_name))
            project_path = self._plugin_projects.get(plugin_name, "")
            plugins.append({
                "name": plugin_name,
                "version": meta.version,
                "description": meta.description,
                "author": meta.author,
                "dependencies": list(meta.dependencies),
                "project_path": project_path,
                "policy": self.get_plugin_policy(plugin_name),
                "hooks": self._hook_summary_for_plugin(plugin_name)
            })
        return {
            "enabled": self._framework_enabled,
            "loaded_plugins": list(self._loaded_plugins),
            "plugins": plugins,
            "commands": self.get_registered_commands()
        }

    def get_loaded_plugins(self) -> List[str]:
        """Return the names of plugins currently loaded into the registry."""
        self._sync_removed_external_plugins()
        return list(self._loaded_plugins)

    def get_registered_commands(self) -> List[str]:
        """Return the sorted list of registered command names."""
        self._sync_removed_external_plugins()
        return sorted(self.registry.command_handlers.keys())

    def get_registered_command_info(self) -> List[dict]:
        """Return command metadata for UI display and diagnostics."""
        self._sync_removed_external_plugins()
        items = []
        for command_name, (handler, plugin_name) in sorted(self.registry.command_handlers.items()):
            items.append({
                "command": command_name,
                "plugin_name": plugin_name,
                "handler": getattr(handler, "__name__", "<callable>")
            })
        return items

    def load_all(self) -> None:
        self._load_policies_from_config()
        if not self._framework_enabled:
            self.logger.info("Plugin framework is disabled by config")
            return
        self._load_builtin_plugins()
        self._load_external_plugins()
        self._run_startup_handlers()
        self._save_policies_to_config()
        self._started = True

    def reload_all(self) -> None:
        if self._started:
            self._run_shutdown_handlers()

        self.registry = PluginRegistry()
        self._loaded_plugins = []
        self._plugin_meta = {}
        self._plugin_projects = {}
        self._started = False
        self.load_all()

    def _mark_loaded(self, name: str) -> None:
        if name and name not in self._loaded_plugins:
            self._loaded_plugins.append(name)

    def _load_builtin_plugins(self) -> None:
        from . import builtin_plugins

        try:
            plugin_name = "builtin.basic"
            meta = self._make_plugin_meta(builtin_plugins, plugin_name)
            if not self._dependencies_satisfied(meta):
                return

            builtin_plugins.register(self.registry, self)
            self._register_convention_hooks(builtin_plugins, plugin_name)
            self._mark_loaded(plugin_name)
            self._register_plugin_meta(plugin_name, meta)
            # 为内置插件设置配置路径
            builtin_config_dir = os.path.join(os.path.dirname(__file__), 'builtin')
            if not os.path.exists(builtin_config_dir):
                os.makedirs(builtin_config_dir, exist_ok=True)
            self._plugin_projects[plugin_name] = builtin_config_dir
        except Exception as exc:
            self.logger.error("Failed to load built-in plugins: %s", exc)

    def _load_external_plugins(self) -> None:
        if not os.path.isdir(self.external_plugins_dir):
            return

        for item in os.listdir(self.external_plugins_dir):
            if item.startswith("_"):
                continue
            project_dir = os.path.join(self.external_plugins_dir, item)
            if not os.path.isdir(project_dir):
                continue
            try:
                self._load_external_plugin_project(project_dir)
            except Exception as exc:
                self.logger.error("Failed loading plugin project %s: %s", project_dir, exc)
                self.logger.debug(traceback.format_exc())

    def _load_external_plugin_project(self, project_dir: str) -> None:
        manifest_path = os.path.join(project_dir, "plugin.json")
        entry_file = "plugin.py"
        fallback_name = f"ext_plugin_{os.path.basename(project_dir)}"

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                entry_file = str(manifest.get("entry", "plugin.py"))
                fallback_name = str(manifest.get("module_name", fallback_name))
            except Exception as exc:
                self.logger.warning("Invalid plugin manifest %s: %s", manifest_path, exc)

        module_file = os.path.join(project_dir, entry_file)
        if not os.path.exists(module_file):
            self.logger.warning("Plugin entry not found: %s", module_file)
            return

        module_name = f"ext_plugin_{os.path.basename(project_dir)}"
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_name = self._register_from_module(module, fallback_name)
        if plugin_name:
            self._plugin_projects[plugin_name] = project_dir

    def _register_from_module(self, module, fallback_name: str) -> None:
        plugin_name = getattr(module, "PLUGIN_NAME", fallback_name)
        meta = self._make_plugin_meta(module, plugin_name)

        if not self._dependencies_satisfied(meta):
            return ""

        if hasattr(module, "register") and callable(module.register):
            module.register(self.registry, self)
            self._register_convention_hooks(module, plugin_name)
            self._mark_loaded(plugin_name)
            self._register_plugin_meta(plugin_name, meta)
            return plugin_name

        plugin_cls = getattr(module, "Plugin", None)
        if plugin_cls is not None and inspect.isclass(plugin_cls):
            plugin_obj = plugin_cls()
            register_fn = getattr(plugin_obj, "register", None)
            if callable(register_fn):
                register_fn(self.registry, self)
                self._register_convention_hooks(plugin_obj, plugin_name)
                self._mark_loaded(plugin_name)
                self._register_plugin_meta(plugin_name, meta)
                return plugin_name

        return ""

    def _register_convention_hooks(self, module, plugin_name: str) -> None:
        # Register lifecycle hooks following naming convention
        for attr_name in ['on_startup', 'on_shutdown', 'on_message', 'on_response', 'on_error']:
            hook = getattr(module, attr_name, None)
            if callable(hook):
                if attr_name == 'on_startup':
                    self.registry.register_startup_handler(hook, plugin_name)
                elif attr_name == 'on_shutdown':
                    self.registry.register_shutdown_handler(hook, plugin_name)
                elif attr_name == 'on_message':
                    self.registry.register_message_handler(hook, plugin_name)
                elif attr_name == 'on_response':
                    self.registry.register_response_handler(hook, plugin_name)
                elif attr_name == 'on_error':
                    self.registry.register_error_handler(hook, plugin_name)

    def _run_startup_handlers(self):
        for handler, plugin_name in self.registry.startup_handlers:
            try:
                if self._is_plugin_enabled(plugin_name):
                    handler()
                    self.logger.info(f"Executed startup handler for plugin: {plugin_name}")
            except Exception as e:
                self.logger.error(f"Error executing startup handler for {plugin_name}: {e}")

    def _run_shutdown_handlers(self):
        for handler, plugin_name in self.registry.shutdown_handlers:
            try:
                if self._is_plugin_enabled(plugin_name):
                    handler()
                    self.logger.info(f"Executed shutdown handler for plugin: {plugin_name}")
            except Exception as e:
                self.logger.error(f"Error executing shutdown handler for {plugin_name}: {e}")

    def _dispatch_error_handlers(self, context: PluginContext, exc: Exception) -> None:
        for handler, plugin_name in self.registry.error_handlers:
            if not self._is_plugin_enabled(plugin_name):
                continue
            try:
                handler(context, exc)
            except Exception as hook_exc:
                self.logger.error("Error in on_error hook (%s): %s", plugin_name, hook_exc)

    def process_input(self, context: PluginContext) -> PluginResult:
        """Process incoming user input through command, regex and message hooks."""
        if context is None:
            return PluginResult()

        if not self._framework_enabled:
            return PluginResult()

        user_input = (context.user_input or "").strip()
        if not user_input:
            return PluginResult()

        # 1) Command dispatch: /command arg1 arg2
        if user_input.startswith("/"):
            body = user_input[1:].strip()
            if body:
                cmd, _, arg = body.partition(" ")
                command = cmd.strip().lower()
                handler_item = self.registry.command_handlers.get(command)
                if handler_item:
                    handler, plugin_name = handler_item
                    if not self._is_plugin_enabled(plugin_name):
                        return PluginResult()
                    if not self._is_command_allowed(plugin_name, command):
                        return PluginResult(handled=True, response=f"命令 /{command} 已被策略禁用")
                    try:
                        result = self._run_with_policy(plugin_name, lambda: handler(context, arg.strip()))
                        return result if isinstance(result, PluginResult) else PluginResult()
                    except Exception as exc:
                        self.logger.error("Plugin command failed (%s): %s", plugin_name, exc)
                        self._dispatch_error_handlers(context, exc)
                        return PluginResult(handled=True, response=f"插件命令执行失败: {exc}")

        # 2) Regex rules
        for rule in self.registry.regex_rules:
            plugin_name = rule.plugin_name
            if not self._is_plugin_enabled(plugin_name):
                continue
            try:
                match = rule.pattern.search(user_input)
                if not match:
                    continue
                result = self._run_with_policy(plugin_name, lambda: rule.handler(context, match))
                if isinstance(result, PluginResult):
                    return result
            except Exception as exc:
                self.logger.error("Plugin regex rule failed (%s): %s", plugin_name, exc)
                self._dispatch_error_handlers(context, exc)

        # 3) Message handlers (allow chained rewrite/handle)
        merged_result = PluginResult(handled=False)
        for handler, plugin_name, _priority in self.registry.message_handlers:
            if not self._is_plugin_enabled(plugin_name):
                continue
            try:
                result = self._run_with_policy(plugin_name, lambda: handler(context))
                if not isinstance(result, PluginResult):
                    continue

                if result.metadata:
                    merged_result.metadata.update(result.metadata)

                if result.rewritten_input:
                    context.user_input = result.rewritten_input
                    merged_result.rewritten_input = result.rewritten_input

                if result.handled:
                    merged_result.handled = True
                    if result.response is not None:
                        merged_result.response = result.response
                    return merged_result
            except Exception as exc:
                self.logger.error("Plugin message hook failed (%s): %s", plugin_name, exc)
                self._dispatch_error_handlers(context, exc)

        return merged_result

    def process_response(self, context: PluginContext, response_text: str) -> str:
        """Run response hooks to transform final text before sending to user."""
        if not self._framework_enabled:
            return response_text

        text = response_text
        for handler, plugin_name in self.registry.response_handlers:
            if not self._is_plugin_enabled(plugin_name):
                continue
            try:
                transformed = self._run_with_policy(plugin_name, lambda: handler(context, text))
                if isinstance(transformed, str):
                    text = transformed
            except Exception as exc:
                self.logger.error("Plugin response hook failed (%s): %s", plugin_name, exc)
                self._dispatch_error_handlers(context, exc)

        return text

    def get_plugin_runtime_config(self, plugin_name: str) -> dict:
        print(f"[DEBUG] get_plugin_runtime_config called for: {plugin_name}")
        # 特殊处理内置插件
        if plugin_name == "builtin.basic":
            print(f"[DEBUG] Handling builtin.basic")
            builtin_config_dir = os.path.join(os.path.dirname(__file__), 'builtin')
            if not os.path.exists(builtin_config_dir):
                os.makedirs(builtin_config_dir, exist_ok=True)
            config_path = os.path.join(builtin_config_dir, "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    print(f"[DEBUG] Loaded config from {config_path}: {data}")
                    return data if isinstance(data, dict) else {}
                except Exception as e:
                    self.logger.warning(f"Failed to load config for {plugin_name}: {e}")
                    return {}
            print(f"[DEBUG] Config file not found at {config_path}, returning empty dict")
            # 如果配置文件不存在，创建一个默认配置
            default_config = {
                "description": "Built-in basic plugin configuration",
                "version": "1.0.0",
                "enabled": True
            }
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                print(f"[DEBUG] Created default config at {config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to create default config for {plugin_name}: {e}")
            return default_config
        
        print(f"[DEBUG] Looking in _plugin_projects for {plugin_name}")
        project_path = self._plugin_projects.get(plugin_name)
        if not project_path:
            # 再次检查是否为内置插件，以防在某些情况下没有正确加载
            if plugin_name == "builtin.basic":
                print(f"[DEBUG] Found builtin.basic but not in _plugin_projects, handling directly")
                builtin_config_dir = os.path.join(os.path.dirname(__file__), 'builtin')
                if not os.path.exists(builtin_config_dir):
                    os.makedirs(builtin_config_dir, exist_ok=True)
                config_path = os.path.join(builtin_config_dir, "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        return data if isinstance(data, dict) else {}
                    except Exception as e:
                        self.logger.warning(f"Failed to load config for {plugin_name}: {e}")
                        return {}
                # 如果还是不存在，创建默认配置
                default_config = {
                    "description": "Built-in basic plugin configuration",
                    "version": "1.0.0",
                    "enabled": True
                }
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(default_config, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    self.logger.warning(f"Failed to create default config for {plugin_name}: {e}")
                return default_config
            
            raise ValueError(f"Plugin not found: {plugin_name}")
        config_path = os.path.join(project_path, "config.json")
        if not os.path.exists(config_path):
            # 如果配置文件不存在，返回空配置
            return {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            self.logger.warning(f"Failed to load config for {plugin_name}: {e}")
            return {}

    def update_plugin_runtime_config(self, plugin_name: str, config_data: dict) -> dict:
        print(f"[DEBUG] update_plugin_runtime_config called for: {plugin_name}")
        # 特殊处理内置插件
        if plugin_name == "builtin.basic":
            builtin_config_dir = os.path.join(os.path.dirname(__file__), 'builtin')
            if not os.path.exists(builtin_config_dir):
                os.makedirs(builtin_config_dir, exist_ok=True)
            config_path = os.path.join(builtin_config_dir, "config.json")
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                print(f"[DEBUG] Saved config to {config_path}: {config_data}")
                # 同时确保该插件被添加到项目列表中
                self._plugin_projects[plugin_name] = builtin_config_dir
                return config_data
            except Exception as e:
                self.logger.error(f"Failed to save config for {plugin_name}: {e}")
                raise
        
        project_path = self._plugin_projects.get(plugin_name)
        if not project_path:
            # 再次检查是否为内置插件，以防在某些情况下没有正确加载
            if plugin_name == "builtin.basic":
                print(f"[DEBUG] Updating builtin.basic but not in _plugin_projects, handling directly")
                builtin_config_dir = os.path.join(os.path.dirname(__file__), 'builtin')
                if not os.path.exists(builtin_config_dir):
                    os.makedirs(builtin_config_dir, exist_ok=True)
                config_path = os.path.join(builtin_config_dir, "config.json")
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
                    # 确保该插件被添加到项目列表中
                    self._plugin_projects[plugin_name] = builtin_config_dir
                    return config_data
                except Exception as e:
                    self.logger.error(f"Failed to save config for {plugin_name}: {e}")
                    raise
            
            raise ValueError(f"Plugin not found: {plugin_name}")
        config_path = os.path.join(project_path, "config.json")
        try:
            if not os.path.exists(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return config_data
        except Exception as e:
            self.logger.error(f"Failed to save config for {plugin_name}: {e}")
            raise
