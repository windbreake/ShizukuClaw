# -*- coding: utf-8 -*-
"""
AstrBot Plugin Compatibility Layer for ShizukuClaw

This plugin provides compatibility for AstrBot plugins, allowing them to run
within the ShizukuClaw framework without modifying core code.

Features:
- Load and execute AstrBot plugins (Star-based)
- Parse metadata.yaml and _conf_schema.json
- Provide Context and Event simulation
- Isolated plugin execution environment
- Dedicated AstrBot plugin store page
"""

import os
import sys
import json
import yaml
import importlib
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.plugin_framework.ui_extensions import (
    UIMenuItem, UIPage, UISettingSection, UIWidget, ApiRoute, ui_registry
)

# Module-level plugin metadata (required by ShizukuClaw plugin system)
PLUGIN_META = {
    "name": "astrbot_compatibility",
    "version": "1.0.0",
    "description": "提供AstrBot插件兼容层，支持加载和运行AstrBot插件",
    "author": "ShizukuClaw Team",
    "dependencies": []  # No ShizukuClaw plugin dependencies
}


@dataclass
class AstrBotMessage:
    """Simulated AstrBot message object."""
    type: str = "text"
    self_id: str = ""
    session_id: str = ""
    message_id: str = ""
    group_id: str = ""
    sender: Dict[str, Any] = field(default_factory=dict)
    message: List[Any] = field(default_factory=list)
    message_str: str = ""
    raw_message: Any = None
    timestamp: int = 0


@dataclass
class AstrMessageEvent:
    """Simulated AstrBot message event."""
    message_obj: AstrBotMessage = None
    context: Any = None
    
    def get_sender_name(self) -> str:
        """Get sender name from message."""
        if self.message_obj and self.message_obj.sender:
            return self.message_obj.sender.get('name', 'Unknown')
        return 'Unknown'
    
    async def plain_result(self, text: str):
        """Return plain text result."""
        return {'type': 'text', 'content': text}
    
    async def image_result(self, url: str):
        """Return image result."""
        return {'type': 'image', 'url': url}


class AstrBotContext:
    """Simulated AstrBot Context object."""
    
    def __init__(self, plugin_manager=None):
        self.plugin_manager = plugin_manager
        self.config = {}
        self.logger = None
    
    def get_config(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value


class AstrBotLogger:
    """Simulated AstrBot logger."""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
    
    def info(self, msg: str):
        print(f"[AstrBot:{self.plugin_name}] INFO: {msg}")
    
    def warning(self, msg: str):
        print(f"[AstrBot:{self.plugin_name}] WARNING: {msg}")
    
    def error(self, msg: str):
        print(f"[AstrBot:{self.plugin_name}] ERROR: {msg}")
    
    def debug(self, msg: str):
        print(f"[AstrBot:{self.plugin_name}] DEBUG: {msg}")


class AstrBotConfig(dict):
    """Simulated AstrBot configuration object."""
    
    def __init__(self, config_dict: dict, config_path: str = ""):
        super().__init__(config_dict)
        self._config_path = config_path
    
    def save_config(self):
        """Save configuration to file."""
        if self._config_path:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(dict(self), f, indent=2, ensure_ascii=False)


class AstrBotPluginLoader:
    """Loader for AstrBot plugins."""
    
    def __init__(self, plugins_dir: str):
        # Keep as Path object, but don't resolve to absolute path
        self.plugins_dir = Path(plugins_dir)
        self.loaded_plugins: Dict[str, Any] = {}
        self.plugin_metadata: Dict[str, dict] = {}
    
    def discover_plugins(self) -> List[dict]:
        """Discover all AstrBot plugins in the directory."""
        plugins = []
        
        if not self.plugins_dir.exists():
            return plugins
        
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            # Check for main.py (required for AstrBot plugins)
            main_py = plugin_dir / "main.py"
            if not main_py.exists():
                continue
            
            # Try to load metadata
            metadata = self._load_metadata(plugin_dir)
            if metadata:
                plugins.append({
                    'name': plugin_dir.name,
                    'path': str(plugin_dir),
                    'metadata': metadata
                })
        
        return plugins
    
    def _load_metadata(self, plugin_dir: Path) -> Optional[dict]:
        """Load plugin metadata from metadata.yaml or plugin.json."""
        # Try metadata.yaml first (AstrBot standard)
        metadata_yaml = plugin_dir / "metadata.yaml"
        if metadata_yaml.exists():
            try:
                with open(metadata_yaml, 'r', encoding='utf-8') as f:
                    metadata = yaml.safe_load(f)
                if isinstance(metadata, dict):
                    return metadata
            except Exception as e:
                print(f"Failed to load metadata.yaml: {e}")
        
        # Fallback to plugin.json
        plugin_json = plugin_dir / "plugin.json"
        if plugin_json.exists():
            try:
                with open(plugin_json, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load plugin.json: {e}")
        
        return None
    
    def load_plugin(self, plugin_name: str) -> Optional[Any]:
        """Load an AstrBot plugin by name."""
        plugin_dir = self.plugins_dir / plugin_name
        
        if not plugin_dir.exists():
            print(f"Plugin directory not found: {plugin_name}")
            return None
        
        # Load metadata
        metadata = self._load_metadata(plugin_dir)
        if metadata:
            self.plugin_metadata[plugin_name] = metadata
        
        # Load configuration schema if exists
        config_schema = self._load_config_schema(plugin_dir)
        
        # Create isolated context
        context = AstrBotContext(plugin_manager=self)
        context.logger = AstrBotLogger(plugin_name)
        
        # Load and instantiate plugin
        try:
            # Add plugin directory to Python path temporarily
            plugin_path = str(plugin_dir)
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            # Import main module
            spec = importlib.util.spec_from_file_location(
                f"astrbot_plugin_{plugin_name}",
                plugin_dir / "main.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find the Star class
            star_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and attr.__name__ != 'Star':
                    # Check if it looks like a Star subclass
                    if hasattr(attr, '__init__'):
                        star_class = attr
                        break
            
            if star_class:
                # Instantiate with context and optional config
                config_path = plugin_dir / "config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    config = AstrBotConfig(config_data, str(config_path))
                    instance = star_class(context, config)
                else:
                    instance = star_class(context)
                
                self.loaded_plugins[plugin_name] = {
                    'instance': instance,
                    'module': module,
                    'context': context,
                    'metadata': metadata or {},
                    'config_schema': config_schema
                }
                
                print(f"[AstrBotLoader] Loaded plugin: {plugin_name}")
                return instance
            else:
                print(f"[AstrBotLoader] No Star class found in {plugin_name}")
                return None
        
        except Exception as e:
            print(f"[AstrBotLoader] Failed to load plugin {plugin_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Clean up path
            if plugin_path in sys.path:
                sys.path.remove(plugin_path)
    
    def _load_config_schema(self, plugin_dir: Path) -> Optional[dict]:
        """Load plugin configuration schema from _conf_schema.json."""
        schema_file = plugin_dir / "_conf_schema.json"
        if schema_file.exists():
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load config schema: {e}")
        return None
    
    def _load_single_plugin(self, plugin_dir: str) -> Dict[str, Any]:
        """Load a single AstrBot plugin (internal method for hot loading).
        
        Args:
            plugin_dir: Path to the plugin directory
            
        Returns:
            Result dict with success status and plugin data
        """
        try:
            plugin_path = Path(plugin_dir)
            plugin_name = plugin_path.name
            
            # Check if main.py exists
            main_py = plugin_path / "main.py"
            if not main_py.exists():
                return {
                    'success': False,
                    'error': f'main.py not found in {plugin_dir}'
                }
            
            # Load metadata
            metadata = self._load_metadata(plugin_path)
            if metadata:
                self.plugin_metadata[plugin_name] = metadata
            
            # Load configuration schema
            config_schema = self._load_config_schema(plugin_path)
            
            # Create isolated context
            context = AstrBotContext(plugin_manager=self)
            context.logger = AstrBotLogger(plugin_name)
            
            # Add plugin directory to Python path temporarily
            plugin_path_str = str(plugin_path)
            if plugin_path_str not in sys.path:
                sys.path.insert(0, plugin_path_str)
            
            # Also add astrbot_compatibility directory to make astrbot.api importable
            # The astrbot module is in: astrbot_compatibility/astrbot/
            # Use relative path from current file location
            astrbot_compat_dir = os.path.dirname(__file__)
            if astrbot_compat_dir not in sys.path:
                sys.path.insert(0, astrbot_compat_dir)
            
            try:
                # Import main module
                spec = importlib.util.spec_from_file_location(
                    f"astrbot_plugin_{plugin_name}",
                    main_py
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find the Star class
                star_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and attr.__name__ != 'Star':
                        # Check if it looks like a Star subclass
                        if hasattr(attr, '__init__'):
                            star_class = attr
                            break
                
                if not star_class:
                    return {
                        'success': False,
                        'error': f'No Star class found in {plugin_name}'
                    }
                
                # Instantiate with context and optional config
                config_path = plugin_path / "config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    config = AstrBotConfig(config_data, str(config_path))
                    instance = star_class(context, config)
                else:
                    instance = star_class(context)
                
                # Call initialize method if exists
                if hasattr(instance, 'initialize'):
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(instance.initialize())
                        loop.close()
                    except Exception as e:
                        print(f"[AstrBotCompatibility] Error initializing plugin {plugin_name}: {e}")
                
                # Store loaded plugin
                self.loaded_plugins[plugin_name] = {
                    'instance': instance,
                    'module': module,
                    'context': context,
                    'metadata': metadata or {},
                    'config_schema': config_schema
                }
                
                return {
                    'success': True,
                    'plugin_name': plugin_name,
                    'metadata': metadata or {},
                    'message': f'Plugin {plugin_name} loaded successfully'
                }
                
            finally:
                # Clean up path
                if plugin_path_str in sys.path:
                    sys.path.remove(plugin_path_str)
        
        except Exception as e:
            print(f"[AstrBotCompatibility] Error loading plugin: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def unload_plugin(self, plugin_name: str):
        """Unload a plugin."""
        if plugin_name in self.loaded_plugins:
            plugin_data = self.loaded_plugins[plugin_name]
            instance = plugin_data.get('instance')
            
            # Call terminate method if exists
            if instance and hasattr(instance, 'terminate'):
                try:
                    if asyncio.iscoroutinefunction(instance.terminate):
                        asyncio.run(instance.terminate())
                    else:
                        instance.terminate()
                except Exception as e:
                    print(f"Error during plugin termination: {e}")
            
            del self.loaded_plugins[plugin_name]
            print(f"[AstrBotLoader] Unloaded plugin: {plugin_name}")
    
    def get_plugin_info(self, plugin_name: str) -> Optional[dict]:
        """Get plugin information."""
        if plugin_name in self.loaded_plugins:
            return self.loaded_plugins[plugin_name]
        return None
    
    def hot_load_plugin(self, plugin_dir: str) -> Dict[str, Any]:
        """Hot load a single AstrBot plugin.
        
        Args:
            plugin_dir: Path to the plugin directory
            
        Returns:
            Plugin metadata or error info
        """
        try:
            # Check if already loaded
            plugin_name = os.path.basename(plugin_dir)
            if plugin_name in self.loaded_plugins:
                return {
                    'success': False,
                    'error': f'Plugin {plugin_name} is already loaded'
                }
            
            # Load the plugin
            result = self._load_single_plugin(plugin_dir)
            
            if result.get('success'):
                print(f"[AstrBotCompatibility] Hot loaded plugin: {plugin_name}")
            else:
                print(f"[AstrBotCompatibility] Failed to hot load plugin: {result.get('error')}")
            
            return result
            
        except Exception as e:
            print(f"[AstrBotCompatibility] Error hot loading plugin: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def hot_unload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Hot unload a single AstrBot plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            Result dict
        """
        try:
            if plugin_name not in self.loaded_plugins:
                return {
                    'success': False,
                    'error': f'Plugin {plugin_name} is not loaded'
                }
            
            # Get plugin data
            plugin_data = self.loaded_plugins[plugin_name]
            
            # Call terminate if exists
            star_instance = plugin_data.get('instance')
            if star_instance and hasattr(star_instance, 'terminate'):
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(star_instance.terminate())
                    loop.close()
                except Exception as e:
                    print(f"[AstrBotCompatibility] Error terminating plugin {plugin_name}: {e}")
            
            # Remove from loaded plugins
            del self.loaded_plugins[plugin_name]
            
            print(f"[AstrBotCompatibility] Hot unloaded plugin: {plugin_name}")
            
            return {
                'success': True,
                'message': f'Plugin {plugin_name} unloaded successfully'
            }
            
        except Exception as e:
            print(f"[AstrBotCompatibility] Error hot unloading plugin: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }


# ── Marketplace data cache ──
_marketplace_cache = {"data": None, "ts": 0}
_MARKETPLACE_API = "https://api.soulter.top/astrbot/plugins"


def _fetch_marketplace_data():
    """Fetch marketplace data with 15-minute cache."""
    import time
    now = time.time()
    if _marketplace_cache["data"] is not None and (now - _marketplace_cache["ts"]) < 900:
        return _marketplace_cache["data"]
    try:
        import urllib.request
        req = urllib.request.Request(_MARKETPLACE_API, headers={"User-Agent": "ShizukuClaw/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        _marketplace_cache["data"] = raw
        _marketplace_cache["ts"] = now
        return raw
    except Exception as e:
        print(f"[AstrBotCompatibility] Failed to fetch marketplace: {e}")
        return _marketplace_cache["data"] or "{}"


def _get_manage_plugins_data():
    """Get loaded plugins data as JSON string."""
    import json as _json
    try:
        loader = _get_loader()
        loaded = []
        for name, data in loader.loaded_plugins.items():
            meta = data.get('metadata', {})
            loaded.append({
                'name': name,
                'display_name': meta.get('display_name', name),
                'description': meta.get('desc', meta.get('description', '')),
                'version': meta.get('version', ''),
                'author': meta.get('author', ''),
            })
        return _json.dumps(loaded, ensure_ascii=False)
    except Exception:
        return "[]"


# ── Module-level API handler factories ──

def _get_loader():
    if not global_loader:
        raise RuntimeError("AstrBot loader not initialized")
    return global_loader


def _json_response(data, status=200):
    import json as _json
    from flask import Response
    return Response(_json.dumps(data, ensure_ascii=False), status=status, mimetype='application/json')


def _make_available_handler():
    def handle(request):
        try:
            loader = _get_loader()
            plugins = loader.discover_plugins()
            return _json_response({'success': True, 'plugins': plugins})
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_loaded_handler():
    def handle(request):
        try:
            loader = _get_loader()
            loaded = []
            for name, data in loader.loaded_plugins.items():
                loaded.append({
                    'name': name,
                    'metadata': data.get('metadata', {}),
                    'config_schema': data.get('config_schema')
                })
            return _json_response({'success': True, 'plugins': loaded})
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_hot_load_handler():
    import os
    def handle(request):
        try:
            data = request.get_json() or {}
            plugin_name_req = data.get('plugin_name', '').strip()
            if not plugin_name_req:
                return _json_response({'success': False, 'error': 'plugin_name is required'}, 400)
            loader = _get_loader()
            plugins_dir = str(loader.plugins_dir)
            plugin_dir = os.path.join(plugins_dir, plugin_name_req)
            if not os.path.exists(plugin_dir):
                return _json_response({'success': False, 'error': f'Plugin directory not found: {plugin_dir}'}, 404)
            result = loader.hot_load_plugin(plugin_dir)
            return _json_response(result)
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_hot_unload_handler():
    def handle(request):
        try:
            data = request.get_json() or {}
            plugin_name_req = data.get('plugin_name', '').strip()
            if not plugin_name_req:
                return _json_response({'success': False, 'error': 'plugin_name is required'}, 400)
            loader = _get_loader()
            result = loader.hot_unload_plugin(plugin_name_req)
            return _json_response(result)
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_reload_handler():
    import os
    def handle(request):
        try:
            data = request.get_json() or {}
            plugin_name_req = data.get('plugin_name', '').strip()
            if not plugin_name_req:
                return _json_response({'success': False, 'error': 'plugin_name is required'}, 400)
            loader = _get_loader()
            unload_result = loader.hot_unload_plugin(plugin_name_req)
            if not unload_result.get('success'):
                print(f"[AstrBotCompatibility] Warning during reload: {unload_result.get('error')}")
            plugins_dir = str(loader.plugins_dir)
            plugin_dir = os.path.join(plugins_dir, plugin_name_req)
            if not os.path.exists(plugin_dir):
                return _json_response({'success': False, 'error': f'Plugin directory not found: {plugin_dir}'}, 404)
            result = loader.hot_load_plugin(plugin_dir)
            return _json_response(result)
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_stats_handler():
    def handle(request):
        try:
            loader = _get_loader()
            loaded_count = len(loader.loaded_plugins)
            available_count = len(loader.discover_plugins())
            return _json_response({
                'success': True,
                'stats': {
                    'loaded': loaded_count,
                    'available': available_count,
                    'errors': 0
                }
            })
        except Exception as e:
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


def _make_install_handler():
    import os
    import shutil
    import subprocess
    import tempfile
    import zipfile
    import urllib.request as _urllib
    import re as _re
    import sys as _sys
    
    def _find_main_py(plugin_dir):
        """Find main.py in the plugin directory (handle GitHub's repo-branch wrapper)."""
        main_py = os.path.join(plugin_dir, 'main.py')
        if os.path.isfile(main_py):
            return main_py
        # GitHub wraps repos as repo-branch/ — shift files up one level
        dirs = [d for d in os.listdir(plugin_dir) if os.path.isdir(os.path.join(plugin_dir, d)) and not d.startswith('.')]
        if len(dirs) == 1:
            inner = os.path.join(plugin_dir, dirs[0])
            inner_main = os.path.join(inner, 'main.py')
            if os.path.isfile(inner_main):
                # Move all contents up
                for item in os.listdir(inner):
                    src = os.path.join(inner, item)
                    dst = os.path.join(plugin_dir, item)
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
                shutil.rmtree(inner)
                return os.path.join(plugin_dir, 'main.py')
        return None
    
    def _parse_github_url(url):
        """Parse GitHub URL into author, repo, branch."""
        match = _re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/|$)', url)
        if match:
            return match.group(1), match.group(2).replace('.git', ''), 'master'
        return None, None, None
    
    def handle(request):
        try:
            data = request.get_json() or {}
            plugin_name_req = data.get('plugin_name', '').strip()
            repo_url = data.get('repo_url', '').strip()
            
            if not plugin_name_req:
                return _json_response({'success': False, 'error': 'plugin_name is required'}, 400)
            if not repo_url:
                return _json_response({'success': False, 'error': 'repo_url is required'}, 400)
            
            loader = _get_loader()
            plugins_dir = str(loader.plugins_dir)
            target_dir = os.path.join(plugins_dir, plugin_name_req)
            
            if os.path.exists(target_dir):
                return _json_response({'success': False, 'error': f'Plugin directory already exists: {plugin_name_req}'}, 409)
            
            author, repo_name, branch = _parse_github_url(repo_url)
            if not author or not repo_name:
                return _json_response({'success': False, 'error': f'Cannot parse GitHub URL: {repo_url}'}, 400)
            
            # Download ZIP from GitHub (same approach as AstrBot)
            zip_url = f'https://github.com/{author}/{repo_name}/archive/refs/heads/{branch}.zip'
            print(f"[AstrBotCompatibility] Downloading {zip_url} -> {plugin_name_req}")
            
            tmp_zip = tempfile.mktemp(suffix='.zip')
            try:
                req = _urllib.Request(zip_url, headers={'User-Agent': 'ShizukuClaw/1.0'})
                with _urllib.urlopen(req, timeout=120) as resp:
                    with open(tmp_zip, 'wb') as f:
                        f.write(resp.read())
                
                # Unzip to target directory
                os.makedirs(target_dir, exist_ok=True)
                with zipfile.ZipFile(tmp_zip, 'r') as zf:
                    zf.extractall(target_dir)
            finally:
                if os.path.isfile(tmp_zip):
                    os.remove(tmp_zip)
            
            # Find main.py (handle GitHub wrapper directory)
            main_py = _find_main_py(target_dir)
            if not main_py:
                return _json_response({'success': False, 'error': 'main.py not found after extraction. Plugin may not be an AstrBot plugin.'}, 500)
            
            # Install requirements if present
            req_txt = os.path.join(target_dir, 'requirements.txt')
            if os.path.isfile(req_txt):
                print(f"[AstrBotCompatibility] Installing requirements for {plugin_name_req}")
                try:
                    subprocess.run([_sys.executable, '-m', 'pip', 'install', '-r', req_txt],
                                   capture_output=True, text=True, timeout=180, check=False)
                except Exception:
                    pass
            
            # Hot load the plugin
            load_result = loader.hot_load_plugin(target_dir)
            return _json_response(load_result)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _json_response({'success': False, 'error': str(e)}, 500)
    return handle


class AstrBotCompatibilityPlugin:
    """Main plugin providing AstrBot compatibility layer."""
    
    PLUGIN_META = {
        "name": "astrbot_compatibility",
        "version": "1.0.0",
        "description": "提供AstrBot插件兼容层，支持加载和运行AstrBot插件",
        "author": "ShizukuClaw Team",
        "dependencies": ["pyyaml"]
    }
    
    def __init__(self):
        self.loader = None
        self.config = {}
    
    def on_load(self, manager):
        """Initialize AstrBot compatibility layer."""
        plugin_name = self.PLUGIN_META["name"]
        
        # Load configuration (handle case where plugin not yet registered)
        try:
            self.config = manager.get_plugin_runtime_config(plugin_name)
        except ValueError:
            # Plugin not registered yet, use defaults
            self.config = self._get_default_config()
        
        if not self.config:
            self.config = self._get_default_config()
        
        # Update config if needed
        try:
            manager.update_plugin_runtime_config(plugin_name, self.config)
        except ValueError:
            pass  # Plugin not registered yet, skip
        
        # Initialize plugin loader
        # Use relative path from current working directory (backend/)
        astrbot_plugins_dir = 'app/db/data/plungin/astrbot_plugins'
        
        print(f"[AstrBotCompatibility] AstrBot plugins directory: {astrbot_plugins_dir}")
        self.loader = AstrBotPluginLoader(astrbot_plugins_dir)
        print(f"[AstrBotCompatibility] Loader plugins_dir: {self.loader.plugins_dir}")
        
        # Set global loader reference for API access
        global global_loader
        global_loader = self.loader
        
        # Register UI extensions
        self._register_ui_extensions()
        
        # Inject UI helper and styles into main page
        self._inject_ui_helper()
        self._inject_plugin_styles()
        
        # Auto-load discovered plugins
        if self.config.get('auto_load_plugins', True):
            self._auto_load_plugins()
        
        print(f"[AstrBotCompatibility] Initialized successfully")
    
    def _register_ui_extensions(self):
        """Register UI extensions for AstrBot plugin management."""
        plugin_name = self.PLUGIN_META["name"]
        
        # 1. Register main menu item (order=5 to appear early in menu)
        menu_item = UIMenuItem(
            id="astrbot_store",
            label="AstrBot 插件商店",
            icon="fas fa-store",
            order=5,  # Lower order to appear near top
            url="/plugins/astrbot_compatibility/store",
            parent_id=None
        )
        ui_registry.register_menu_item(menu_item, plugin_name)
        
        # 2. Register sub-menu items
        submenu_manage = UIMenuItem(
            id="astrbot_manage",
            label="管理已安装插件",
            icon="fas fa-cogs",
            order=61,
            url="/plugins/astrbot_compatibility/manage",
            parent_id="astrbot_store"
        )
        ui_registry.register_menu_item(submenu_manage, plugin_name)
        
        submenu_settings = UIMenuItem(
            id="astrbot_settings",
            label="兼容层设置",
            icon="fas fa-sliders-h",
            order=62,
            url="/plugins/astrbot_compatibility/settings",
            parent_id="astrbot_store"
        )
        ui_registry.register_menu_item(submenu_settings, plugin_name)
        
        # 3. Register store page (dynamic content via callable)
        store_page = UIPage(
            id="store_page",
            title="AstrBot 插件商店",
            route="/store",
            content_type="html",
            content=lambda: self._get_store_page_html(),
            requires_auth=True
        )
        ui_registry.register_page(store_page, plugin_name)
        
        # 4. Register manage page (dynamic content via callable)
        manage_page = UIPage(
            id="manage_page",
            title="管理已安装插件",
            route="/manage",
            content_type="html",
            content=lambda: self._get_manage_page_html(),
            requires_auth=True
        )
        ui_registry.register_page(manage_page, plugin_name)
        
        # 5. Register settings page
        settings_page = UIPage(
            id="settings_page",
            title="兼容层设置",
            route="/settings",
            content_type="html",
            content=self._get_settings_page_html(),
            requires_auth=True
        )
        ui_registry.register_page(settings_page, plugin_name)
        
        # 6. Register settings section
        setting_section = UISettingSection(
            id="astrbot_config",
            title="AstrBot 兼容层配置",
            description="配置AstrBot插件兼容层的运行参数",
            order=150,
            fields=[
                {
                    "key": "astrbot_plugins_dir",
                    "type": "text",
                    "label": "AstrBot插件目录",
                    "default": "app/db/data/plungin/astrbot_plugins",
                    "description": "存放AstrBot插件的目录路径（相对于项目根目录）"
                },
                {
                    "key": "auto_load_plugins",
                    "type": "switch",
                    "label": "自动加载插件",
                    "default": True,
                    "description": "启动时自动加载发现的AstrBot插件"
                },
                {
                    "key": "enable_sandbox",
                    "type": "switch",
                    "label": "启用沙箱模式",
                    "default": True,
                    "description": "在隔离环境中运行AstrBot插件以提高安全性"
                }
            ]
        )
        ui_registry.register_setting_section(setting_section, plugin_name)
        
        # 7. Register dashboard widget with dynamic stats
        widget = UIWidget(
            id="astrbot_stats",
            title="AstrBot 插件统计",
            widget_type="stats",
            position="dashboard",
            order=5,  # Lower order to appear early
            config={
                "items": [
                    {"label": "已加载", "value": "loading...", "icon": "fas fa-check-circle", "color": "success"},
                    {"label": "可用", "value": "loading...", "icon": "fas fa-box", "color": "info"},
                    {"label": "错误", "value": "0", "icon": "fas fa-exclamation-triangle", "color": "danger"}
                ]
            },
            data_source="/api/plugins/astrbot_compatibility/stats",
            refresh_interval=30
        )
        ui_registry.register_widget(widget, plugin_name)
        
        # 8. Register API routes
        self._register_api_routes(plugin_name)
    
    def _inject_ui_helper(self):
        """UI helpers are loaded via plugin_ui_loader.js in control_panel.html."""
        pass
    
    def _inject_plugin_styles(self):
        """Plugin page styles are defined in static/css/style.css."""
        pass
    
    def _register_api_routes(self, plugin_name):
        """Register API routes for AstrBot plugin management."""
        import os
        
        # Register all API routes using module-level handler factories
        ui_registry.register_api_route(ApiRoute(method='GET', path='/available', handler=_make_available_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='GET', path='/loaded', handler=_make_loaded_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='POST', path='/hot_load', handler=_make_hot_load_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='POST', path='/hot_unload', handler=_make_hot_unload_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='POST', path='/install', handler=_make_install_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='POST', path='/unload', handler=_make_hot_unload_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='POST', path='/reload', handler=_make_reload_handler()), plugin_name)
        ui_registry.register_api_route(ApiRoute(method='GET', path='/stats', handler=_make_stats_handler()), plugin_name)
    
    def _get_store_page_html(self):
        """Generate store page - fully server-side rendered."""
        plugins_json = _fetch_marketplace_data()
        import json as _json
        try:
            data = _json.loads(plugins_json)
        except Exception:
            data = {}

        # Sort by stars descending, build card HTML server-side
        entries = sorted(data.items(), key=lambda e: e[1].get('stars', 0) or 0, reverse=True)
        cards = []
        for slug, info in entries:
            desc = (info.get('desc') or info.get('description') or '')[:120]
            tags_html = ''.join(f'<span class="badge bg-light text-dark border me-1">{t}</span>' for t in (info.get('tags') or [])[:4])
            logo = info.get('logo', '')
            logo_html = f'<img src="{logo}" style="width:48px;height:48px;border-radius:10px;object-fit:cover">' if logo else '<div style="width:48px;height:48px;border-radius:10px;background:#e7f3fb;display:inline-flex;align-items:center;justify-content:center;color:#66a8d2"><i class="fas fa-puzzle-piece"></i></div>'
            repo = info.get('repo', '')
            repo_btn = f'<a href="{repo}" target="_blank" class="btn btn-sm btn-outline-secondary me-1"><i class="fab fa-github"></i></a>' if repo else ''
            stars_html = f'<span class="text-muted small me-2"><i class="fas fa-star text-warning"></i> {info.get("stars", 0)}</span>' if info.get('stars') else ''
            time_html = f'<span class="text-muted small"><i class="far fa-clock me-1"></i>{info.get("updated_at", "")[:10]}</span>' if info.get('updated_at') else ''
            ver = info.get('version', '?')
            slug_esc = slug.replace("'", "\\'")
            repo_esc = (repo or '').replace("'", "\\'")
            cards.append(f'''<div class="col-lg-4 col-md-6 mb-3"><div class="card h-100"><div class="card-body"><div class="d-flex align-items-start mb-2">{logo_html}<div class="ms-3 flex-grow-1" style="min-width:0"><h6 class="card-title mb-1 text-truncate">{info.get("display_name", slug)}</h6><small class="text-muted">{info.get("author", "")}</small></div></div><p class="card-text small text-muted mb-2" style="min-height:40px">{desc}</p><div class="mb-2">{tags_html}</div><div class="d-flex justify-content-between align-items-center"><div>{stars_html}{time_html}</div><small class="badge bg-secondary">v{ver}</small></div><div class="mt-2 pt-2 border-top">{repo_btn}<button class="btn btn-sm btn-primary" onclick="window._aInstall('{slug_esc}','{repo_esc}')"><i class="fas fa-download me-1"></i>安装</button></div></div></div></div>''')

        count = len(cards)
        card_html = ''.join(cards) if cards else '<div class="col-12 text-center py-5"><i class="fas fa-inbox fa-3x text-muted mb-3"></i><p class="text-muted">没有找到匹配的插件</p></div>'

        # Build tag filter options
        tag_counts = {}
        for slug, info in entries:
            for t in (info.get('tags') or []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:30]
        tag_options = '\n'.join(f'<option value="{t}">{t} ({c})</option>' for t, c in sorted_tags)

        return f"""<div class="plugin-page-container">
<div class="plugin-page-header">
<h3><i class="fas fa-store text-primary me-2"></i>AstrBot 插件商店</h3>
<p class="text-muted">浏览和安装来自 <a href="https://plugins.astrbot.app/" target="_blank">AstrBot 官方插件市场</a> 的插件（共 {count} 个）</p>
</div>
<div class="row mb-3">
<div class="col-md-6"><input type="text" class="form-control" placeholder="搜索插件..." id="plugin-search" onkeyup="window._aFilter()"></div>
<div class="col-md-3"><select class="form-select" id="category-filter" onchange="window._aFilter()"><option value="">所有分类</option>{tag_options}</select></div>
<div class="col-md-3"><button class="btn btn-primary w-100" onclick="window._aFilter()"><i class="fas fa-search me-2"></i>搜索</button></div>
</div>
<div id="plugin-list" class="row">{card_html}</div>
</div>
"""

    def _get_manage_page_html(self):
        """Generate manage page - fully server-side rendered."""
        try:
            loader = _get_loader()
            plugins_list = []
            for name, pdata in loader.loaded_plugins.items():
                meta = pdata.get('metadata', {})
                plugins_list.append({
                    'name': name,
                    'display_name': meta.get('display_name', name),
                    'description': meta.get('desc', meta.get('description', '')),
                    'version': meta.get('version', ''),
                })
        except Exception:
            plugins_list = []

        if plugins_list:
            rows = []
            for p in plugins_list:
                name_esc = p['name'].replace("'", "\\'")
                rows.append(f"""<div class="card mb-3"><div class="card-body"><div class="d-flex justify-content-between align-items-start"><div><h5>{p['display_name']}</h5><p class="text-muted small mb-1">{p['description']}</p><small class="text-muted">版本: {p['version'] or 'N/A'}</small></div><div><button class="btn btn-sm btn-warning me-2" onclick="window._aReload('{name_esc}')"><i class="fas fa-redo"></i></button><button class="btn btn-sm btn-danger" onclick="window._aUnload('{name_esc}')"><i class="fas fa-trash"></i></button></div></div></div></div>""")
            content = ''.join(rows)
        else:
            content = '<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>当前没有加载任何AstrBot插件</div>'

        return f"""<div class="plugin-page-container">
<div class="plugin-page-header">
<h3><i class="fas fa-cogs text-primary me-2"></i>管理已安装插件</h3>
<p class="text-muted">查看和管理已加载的AstrBot插件</p>
</div>
<div id="installed-plugins" class="mt-3">{content}</div>
</div>
"""
    
    def _get_settings_page_html(self):
        """Generate settings page HTML."""
        return """
        <div class="plugin-page-container">
            <div class="plugin-page-header">
                <h3><i class="fas fa-sliders-h text-primary me-2"></i>兼容层设置</h3>
                <p class="text-muted">配置AstrBot插件兼容层的运行参数</p>
            </div>
            
            <div class="card">
                <div class="card-body">
                    <form id="astrbot-settings-form">
                        <div class="mb-3">
                            <label class="form-label">AstrBot插件目录</label>
                            <input type="text" class="form-control" name="astrbot_plugins_dir" 
                                   value="app/db/data/plungin/astrbot_plugins">
                            <small class="text-muted">存放AstrBot插件的目录路径</small>
                        </div>
                        
                        <div class="mb-3 form-check form-switch">
                            <input type="checkbox" class="form-check-input" name="auto_load_plugins" 
                                   id="auto_load" checked>
                            <label class="form-check-label" for="auto_load">自动加载插件</label>
                            <small class="d-block text-muted">启动时自动加载发现的AstrBot插件</small>
                        </div>
                        
                        <div class="mb-3 form-check form-switch">
                            <input type="checkbox" class="form-check-input" name="enable_sandbox" 
                                   id="enable_sandbox" checked>
                            <label class="form-check-label" for="enable_sandbox">启用沙箱模式</label>
                            <small class="d-block text-muted">在隔离环境中运行AstrBot插件以提高安全性</small>
                        </div>
                        
                        <button type="submit" class="btn btn-primary">保存设置</button>
                    </form>
                </div>
            </div>
        </div>
        
        <script>
        (function() {
            var form = document.getElementById('astrbot-settings-form');
            if (form) {
                form.addEventListener('submit', function(e) {
                    e.preventDefault();
                    var formData = new FormData(e.target);
                    var config = {
                        astrbot_plugins_dir: formData.get('astrbot_plugins_dir'),
                        auto_load_plugins: formData.get('auto_load_plugins') === 'on',
                        enable_sandbox: formData.get('enable_sandbox') === 'on'
                    };
                    
                    fetch('/api/plugins/config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            plugin_name: 'astrbot_compatibility',
                            config: config
                        })
                    }).then(function(r) { return r.json(); })
                    .then(function(data) {
                        alert(data.success ? '设置保存成功' : '保存失败: ' + data.error);
                    })
                    .catch(function(err) {
                        alert('保存失败: ' + err.message);
                    });
                });
            }
        })();
        </script>
        """
    
    def _auto_load_plugins(self):
        """Auto-load discovered AstrBot plugins."""
        if not self.loader:
            return
        
        plugins = self.loader.discover_plugins()
        print(f"[AstrBotCompatibility] Discovered {len(plugins)} AstrBot plugins")
        
        for plugin_info in plugins:
            plugin_name = plugin_info['name']
            try:
                self.loader.load_plugin(plugin_name)
            except Exception as e:
                print(f"[AstrBotCompatibility] Failed to load {plugin_name}: {e}")
    
    def _get_default_config(self):
        """Get default configuration."""
        return {
            "astrbot_plugins_dir": "backend/app/db/data/plungin/astrbot_plugins",
            "auto_load_plugins": True,
            "enable_sandbox": True
        }
    
    def on_unload(self, manager):
        """Cleanup on plugin unload."""
        if self.loader:
            # Unload all loaded plugins
            for plugin_name in list(self.loader.loaded_plugins.keys()):
                self.loader.unload_plugin(plugin_name)
        
        # Unregister UI extensions
        ui_registry.unregister_plugin(self.PLUGIN_META["name"])
        print(f"[AstrBotCompatibility] Unloaded")


# Create plugin instance
plugin_instance = AstrBotCompatibilityPlugin()

# Global loader reference for API access (will be set during on_load)
global_loader = None


def register(registry, manager):
    """Standard ShizukuClaw plugin registration function."""
    plugin_name = PLUGIN_META["name"]
    
    # Ensure plugin policy
    manager.ensure_plugin_policy(
        plugin_name,
        {
            "enabled": True,
            "allow_network": True,
            "allowed_domains": [],
            "allowed_commands": [],
            "max_execution_ms": 30000,
        },
        persist=False,
    )
    
    # Call the plugin's on_load method
    try:
        plugin_instance.on_load(manager)
        print(f"[AstrBotCompatibility] Plugin registered successfully")
    except Exception as e:
        print(f"[AstrBotCompatibility] Error during registration: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # Register shutdown handler
    def on_shutdown():
        try:
            plugin_instance.on_unload(manager)
        except Exception as e:
            print(f"[AstrBotCompatibility] Error during shutdown: {e}")
    
    registry.register_shutdown_handler(on_shutdown, plugin_name)
