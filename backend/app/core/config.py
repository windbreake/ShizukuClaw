"""配置模块，用于加载和管理应用程序配置"""

import copy
import filecmp
import importlib.util
import json
import os
import shutil
import socket
import time
import traceback

import requests

try:
    from app.agent.reply_policy import default_reply_policy
except ImportError:
    from app.agent.reply_policy import default_reply_policy

# 获取应用根目录（backend/app）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'db', 'data')
LEGACY_SRC_DATA_DIR = os.path.join(PROJECT_ROOT, 'src', 'data')
LEGACY_APP_DATA_DIR = os.path.join(PROJECT_ROOT, 'data')


def _migrate_legacy_src_data():
    """Migrate legacy src/data content into project-root data safely.

    Migration rules:
    - If target file doesn't exist, move file directly.
    - If target file exists and content matches, drop legacy duplicate.
    - If target file exists and content differs, keep target and move legacy
      file to data/_migrated_from_src_data_conflicts/ to avoid data loss.
    """
    if not os.path.isdir(LEGACY_SRC_DATA_DIR):
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    conflict_root = os.path.join(DATA_DIR, '_migrated_from_src_data_conflicts')

    for current_root, _, files in os.walk(LEGACY_SRC_DATA_DIR):
        rel_dir = os.path.relpath(current_root, LEGACY_SRC_DATA_DIR)
        target_dir = DATA_DIR if rel_dir == '.' else os.path.join(DATA_DIR, rel_dir)
        os.makedirs(target_dir, exist_ok=True)

        for filename in files:
            legacy_file = os.path.join(current_root, filename)
            target_file = os.path.join(target_dir, filename)

            if not os.path.exists(target_file):
                shutil.move(legacy_file, target_file)
                continue

            try:
                same_content = filecmp.cmp(legacy_file, target_file, shallow=False)
            except OSError:
                same_content = False

            if same_content:
                os.remove(legacy_file)
                continue

            conflict_dir = conflict_root if rel_dir == '.' else os.path.join(conflict_root, rel_dir)
            os.makedirs(conflict_dir, exist_ok=True)
            name, ext = os.path.splitext(filename)
            conflict_file = os.path.join(conflict_dir, f"{name}.legacy_src_data.{int(time.time())}{ext}")
            shutil.move(legacy_file, conflict_file)

    # Remove empty legacy dirs from deepest level upward.
    for current_root, _, _ in os.walk(LEGACY_SRC_DATA_DIR, topdown=False):
        if not os.listdir(current_root):
            try:
                os.rmdir(current_root)
            except OSError:
                pass


_migrate_legacy_src_data()


def _load_json_file(file_path, default_value):
    try:
        with open(file_path, 'r', encoding='utf-8') as file_handle:
            data = json.load(file_handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return copy.deepcopy(default_value)


def _system_config_default():
    return {
        'server': {
            'port': 8888,
        },
        'launcher': {
            'startup_self_check': True,
            'startup_page': '/control_panel',
        },
        'unified_api': {
            'host': '0.0.0.0',
            'access_token': 'neko-proxy-key-123',
        },
        'onebot': {
            'host': '0.0.0.0',
            'port': 3000,
            'access_token': '',
            'http': {
                'enable': False,
                'host': '0.0.0.0',
                'port': 3000,
            },
            'ws': {
                'enable': True,
                'host': '0.0.0.0',
                'port': 3001,
            },
            'ws_reverse': {
                'enable': False,
                'url': '',
            },
        },
        'work_mode': {
            'enabled': False,
            'password_hash': '',
            'sandbox_enabled': False,
            'reply_policy': default_reply_policy({}),
            'chat_settings': {
                'bothub_enabled': True,
                'sandbox_show_agent_trace': True,
                'sandbox_trace_collapsed': True,
                'sandbox_show_back_to_top': True,
                'sandbox_use_docker_runtime': False,  # 仅 Windows 默认关闭
                'sandbox_use_wsl_runtime': False,     # WSL 运行时
                'sandbox_agent_autonomous': True,
                'sandbox_trace_retention_days': 7,
            },
            'features': {
                'allow_file_write': True,
                'allow_code_exec': True,
                'allow_plan_update': True,
                'allow_coder_tool': True,
                'plugin_command_requires_work_mode': False,
                'plugin_dev_tools_require_work_mode': True,
                'allow_external_access': False,
                'require_external_approval': True,
            },
            'security_modes': {
                'level1_password_hash': '',      # 工作模式密码 (SHA256)
                'level2_password_hash': '',      # 广域管理模式密码 (SHA256)
                'global_admin_enabled': False,   # 是否启用广域管理模式
                'sandbox_mode': 'amala',         # 沙箱引擎: amala, docker, wsl
                'amala_default_security': 0,     # amala 默认安全级别 (0=沙箱, 1=工作, 2=广域)
            },
            'allowed_databases': ['catgirl_db'],
        },
    }


def _load_system_config():
    system_path = os.path.join(DATA_DIR, 'system_config.json')
    data = _load_json_file(system_path, _system_config_default())
    defaults = _system_config_default()

    for section_name, section_default in defaults.items():
        if section_name not in data or not isinstance(data.get(section_name), dict):
            data[section_name] = copy.deepcopy(section_default)
            continue
        for key, default_value in section_default.items():
            data[section_name].setdefault(key, copy.deepcopy(default_value))

    return data


def load_config():
    """从JSON文件加载配置"""
    config_path = os.path.join(DATA_DIR, 'config.json')
    db_path = os.path.join(DATA_DIR, 'database.json')
    system_path = os.path.join(DATA_DIR, 'system_config.json')
    legacy_db_path = os.path.join(LEGACY_APP_DATA_DIR, 'database.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = json.load(f)
    except Exception:
        full_config = {}

    # 1. Load active persona
    active_persona = full_config.get('active_persona', 'shizuku.json')
    persona_path = os.path.join(DATA_DIR, 'personas', active_persona)
    
    # Fallback if active persona file doesn't exist
    if not os.path.exists(persona_path):
        personas_dir = os.path.join(DATA_DIR, 'personas')
        if os.path.exists(personas_dir):
            files = [f for f in os.listdir(personas_dir) if f.endswith('.json')]
            if files:
                persona_path = os.path.join(personas_dir, files[0])
                full_config['active_persona'] = files[0] # Update active to found one

    # Load persona data
    if os.path.exists(persona_path):
        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
                full_config['character'] = persona_data.get('character', {})
                if 'system_prompt' in persona_data:
                    full_config['system_prompt_template'] = persona_data['system_prompt'].get('template', '')
                full_config['persona_runtime'] = {
                    'reply_style': persona_data.get('reply_style', ''),
                    'states': persona_data.get('states', []),
                    'state_probability': persona_data.get('state_probability', 0.3),
                    'plan_style': persona_data.get('plan_style', ''),
                    'plan_style_private': persona_data.get('plan_style_private', ''),
                    'plan_style_group': persona_data.get('plan_style_group', ''),
                    'state_weights': persona_data.get('state_weights', []),
                    'enable_expression_learning': persona_data.get('enable_expression_learning', True),
                    'behavior_rules': persona_data.get('behavior_rules', []),
                    'command_responses': persona_data.get('command_responses', {}),
                    'quick_ack_replies': persona_data.get('quick_ack_replies', {}),
                    'quick_ack_no_repeat_window': persona_data.get('quick_ack_no_repeat_window', 3),
                    'detemplate_openers': persona_data.get('detemplate_openers', []),
                    'detemplate_no_repeat_window': persona_data.get('detemplate_no_repeat_window', 4),
                    'detemplate_marker_variants': persona_data.get('detemplate_marker_variants', {}),
                }
        except Exception as e:
            print(f"Error loading persona {persona_path}: {e}")
            full_config['character'] = {}
            full_config['system_prompt_template'] = ""
            full_config['persona_runtime'] = {}
    else:
        full_config['character'] = {}
        full_config['system_prompt_template'] = ""
        full_config['persona_runtime'] = {}

    # 2. Load database config
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                full_config['database'] = json.load(f)
        except Exception as e:
            print(f"Error loading database config: {e}")
    elif os.path.exists(legacy_db_path):
        try:
            with open(legacy_db_path, 'r', encoding='utf-8') as f:
                legacy_db_cfg = json.load(f)
            if isinstance(legacy_db_cfg, dict):
                full_config['database'] = legacy_db_cfg
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(db_path, 'w', encoding='utf-8') as f:
                    json.dump(legacy_db_cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error loading legacy database config: {e}")

    # 3. Load system runtime config
    if os.path.exists(system_path):
        try:
            with open(system_path, 'r', encoding='utf-8') as f:
                system_config = json.load(f)
            if isinstance(system_config, dict):
                full_config['system_config'] = system_config
                full_config['server'] = system_config.get('server', {})
                full_config['launcher'] = system_config.get('launcher', {})
                full_config['unified_api'] = system_config.get('unified_api', {})
                full_config['onebot'] = system_config.get('onebot', {})
                full_config['work_mode'] = system_config.get('work_mode', {})
        except Exception as e:
            print(f"Error loading system config: {e}")
    
    return full_config


# 加载配置
CONFIG_DATA = load_config()
SYSTEM_CONFIG_DATA = _load_system_config()


def _safe_api_section(section_name: str, default_base_url: str = '', default_model: str = '') -> dict:
    """Read api_keys section safely to avoid KeyError when config is partially migrated."""
    api_keys = CONFIG_DATA.get('api_keys', {}) if isinstance(CONFIG_DATA, dict) else {}
    section = api_keys.get(section_name, {}) if isinstance(api_keys, dict) else {}
    if not isinstance(section, dict):
        section = {}
    return {
        'key': str(section.get('key', '') or ''),
        'base_url': str(section.get('base_url', default_base_url) or default_base_url),
        'model': str(section.get('model', default_model) or default_model),
        'fallback_models': section.get('fallback_models', []) if isinstance(section.get('fallback_models', []), list) else []
    }


def _build_coder_api_config():
    """构建统一 Coder API 配置（兼容旧版 api_keys.coder）"""
    api_keys = CONFIG_DATA.get('api_keys', {})
    coder_data = CONFIG_DATA.get('coder_api', {})

    legacy_coder = api_keys.get('coder', {})
    legacy_kimi = api_keys.get('kimi_coder', {})
    legacy_minimax = api_keys.get('minimax_coder', {})
    legacy_claude = api_keys.get('claude_coder', {})

    providers = coder_data.get('providers', {})

    kimi_cfg = providers.get('kimi', {})
    minimax_cfg = providers.get('minimax', {})
    claude_cfg = providers.get('claude', {})

    return {
        'provider': coder_data.get('provider', 'kimi'),
        'providers': {
            'kimi': {
                'key': kimi_cfg.get('key') or legacy_kimi.get('key') or legacy_coder.get('key', ''),
                'base_url': kimi_cfg.get('base_url') or legacy_kimi.get('base_url') or legacy_coder.get('base_url', 'https://api.moonshot.cn/v1'),
                'model': kimi_cfg.get('model') or legacy_kimi.get('model') or legacy_coder.get('model', 'moonshot-v1-8k')
            },
            'minimax': {
                'key': minimax_cfg.get('key') or legacy_minimax.get('key', ''),
                'base_url': minimax_cfg.get('base_url') or legacy_minimax.get('base_url', 'https://api.minimaxi.com/v1'),
                'model': minimax_cfg.get('model') or legacy_minimax.get('model', 'MiniMax-M2.7')
            },
            'claude': {
                'key': claude_cfg.get('key') or legacy_claude.get('key', ''),
                'base_url': claude_cfg.get('base_url') or legacy_claude.get('base_url', 'https://api.anthropic.com/v1'),
                'model': claude_cfg.get('model') or legacy_claude.get('model', 'claude-3-7-sonnet-latest')
            }
        }
    }


CODER_API_CONFIG = _build_coder_api_config()

_deepseek_api = _safe_api_section('deepseek_chat', default_base_url='https://api.deepseek.com/v1', default_model='deepseek-chat')
_image_recognition_api = _safe_api_section('image_recognition', default_base_url='https://dashscope.aliyuncs.com/api/v1')
_search_api = _safe_api_section('search', default_base_url='https://api.moonshot.cn/v1')
_image_generation_api = _safe_api_section('image_generation', default_base_url='https://api.deepseek.com/v1')
_video_generation_api = _safe_api_section('video_generation')


def generate_system_prompt(character, template):
    """根据模板和角色配置生成系统提示语
    
    Args:
        character (dict): 角色配置信息
        template (str): 系统提示语模板
        
    Returns:
        str: 生成的系统提示语
    """
    # 提取口癖并处理
    catchphrases = character.get('catchphrases', '喵') or '喵'
    phrases_list = [phrase.strip() for phrase in catchphrases.split(',') if phrase.strip()]

    class _SafeDict(dict):
        def __missing__(self, key):
            return ''

    # 格式化模板，允许角色卡使用可选占位符而不直接报错
    system_prompt = template.format_map(_SafeDict({
        'name': character.get('name', '小雫'),
        'personality': character.get('personality', '可爱猫娘'),
        'type': character.get('type', ''),
        'brother_qqid': character.get('brother_qqid', '暂无'),
        'catchphrases': catchphrases,
        'first_catchphrase': phrases_list[0] if phrases_list else '喵~',
        'second_catchphrase': phrases_list[1] if len(phrases_list) > 1 else '哒！'
    }))

    return system_prompt


CONFIG = {
    'server': {
        'port': SYSTEM_CONFIG_DATA.get('server', {}).get('port', 8888),  # Web服务器端口
        'log_file': os.path.join(PROJECT_ROOT, 'app.log'),  # 使用绝对路径
    },
    'api': {
        'key': _deepseek_api['key'],
        'base_url': _deepseek_api['base_url'],
        'model': _deepseek_api['model'],
        'fallback_models': _deepseek_api['fallback_models']
    },
    'aliyun_api': {
        'key': _image_recognition_api['key'],
        'base_url': _image_recognition_api['base_url']
    },
    'search_api': {
        'key': _search_api['key'],
        'base_url': _search_api['base_url']
    },
    'image_generation_api': {
        'key': _image_generation_api['key'],
        'base_url': _image_generation_api['base_url']
    },
    'video_generation_api': {
        'key': _video_generation_api['key'],
        'base_url': _video_generation_api['base_url']
    },
    'coder_api': CODER_API_CONFIG,
    'character': CONFIG_DATA['character'],
    'active_persona': CONFIG_DATA.get('active_persona', 'shizuku.json'),
    'system_prompt': generate_system_prompt(CONFIG_DATA['character'], 
                                            CONFIG_DATA['system_prompt_template']),
    'persona_runtime': {
        'reply_style': CONFIG_DATA.get('persona_runtime', {}).get('reply_style', ''),
        'states': CONFIG_DATA.get('persona_runtime', {}).get('states', []),
        'state_probability': CONFIG_DATA.get('persona_runtime', {}).get('state_probability', 0.3),
        'plan_style': CONFIG_DATA.get('persona_runtime', {}).get('plan_style', ''),
        'plan_style_private': CONFIG_DATA.get('persona_runtime', {}).get('plan_style_private', ''),
        'plan_style_group': CONFIG_DATA.get('persona_runtime', {}).get('plan_style_group', ''),
        'state_weights': CONFIG_DATA.get('persona_runtime', {}).get('state_weights', []),
        'enable_expression_learning': CONFIG_DATA.get('persona_runtime', {}).get('enable_expression_learning', True),
        'behavior_rules': CONFIG_DATA.get('persona_runtime', {}).get('behavior_rules', []),
        'command_responses': CONFIG_DATA.get('persona_runtime', {}).get('command_responses', {})
    },
    'database': CONFIG_DATA.get('database', {
        'engine': 'mysql',
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'Fjh0729!',
        'database': 'catgirl_db'
    }),
    'unified_api': SYSTEM_CONFIG_DATA.get('unified_api', {
        'host': '0.0.0.0',
        'port': 8000,
        'access_token': 'neko-proxy-key-123'
    }),
    'onebot': SYSTEM_CONFIG_DATA.get('onebot', {
        'host': '0.0.0.0',
        'port': 3000,
        'access_token': '',
        'http': {
            'enable': False,
            'host': '0.0.0.0',
            'port': 3000,
        },
        'ws': {
            'enable': True,
            'host': '0.0.0.0',
            'port': 3001,
        },
        'ws_reverse': {
            'enable': False,
            'url': '',
        },
    }),
    'work_mode': {
        'enabled': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('enabled', False),
        'password_hash': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('password_hash', ''),
        'sandbox_enabled': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('sandbox_enabled', False),
        'reply_policy': default_reply_policy(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('reply_policy', {})),
        'chat_settings': {
            'bothub_enabled': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('bothub_enabled', True)),
            'sandbox_show_agent_trace': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_show_agent_trace', True)),
            'sandbox_trace_collapsed': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_trace_collapsed', True)),
            'sandbox_show_back_to_top': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_show_back_to_top', True)),
            'sandbox_use_docker_runtime': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_use_docker_runtime', True)),
            'sandbox_agent_autonomous': bool(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_agent_autonomous', True)),
            'sandbox_trace_retention_days': int(SYSTEM_CONFIG_DATA.get('work_mode', {}).get('chat_settings', {}).get('sandbox_trace_retention_days', 7) or 7),
        },
        'features': {
            'allow_file_write': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_file_write', True),
            'allow_code_exec': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_code_exec', True),
            'allow_plan_update': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_plan_update', True),
            'allow_coder_tool': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_coder_tool', True),
            'plugin_command_requires_work_mode': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('plugin_command_requires_work_mode', False),
            'plugin_dev_tools_require_work_mode': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('features', {}).get('plugin_dev_tools_require_work_mode', True)
        },
        'allowed_databases': SYSTEM_CONFIG_DATA.get('work_mode', {}).get('allowed_databases', ['catgirl_db'])
    },
    'launcher': SYSTEM_CONFIG_DATA.get('launcher', {
        'startup_self_check': True,
        'open_browser': True,
        'startup_page': '/control_panel'
    }),
}


def _check_plugins_health():
    """静态检查插件框架配置、插件项目结构和基础环境。"""
    lines = []
    config_path = os.path.join(DATA_DIR, 'config.json')
    plugin_root = os.path.join(DATA_DIR, 'plungin')
    builtin_path = os.path.join(PROJECT_ROOT, 'plugin_framework', 'builtin_plugins.py')

    plugin_framework_cfg = {}
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                plugin_framework_cfg = cfg.get('plugin_framework', {}) or {}
    except Exception as e:
        lines.append(f"插件配置读取: 失败({e})")

    framework_enabled = bool(plugin_framework_cfg.get('enabled', True))
    policy_count = len(plugin_framework_cfg.get('plugins', {}) or {})
    lines.append(f"插件框架: {'启用' if framework_enabled else '禁用'} (策略数: {policy_count})")

    if os.path.exists(builtin_path):
        lines.append("内置插件文件: 正常")
    else:
        lines.append("内置插件文件: 缺失")

    if not os.path.isdir(plugin_root):
        lines.append("外置插件目录: 不存在")
        return lines

    plugin_dirs = []
    for item in os.listdir(plugin_root):
        if item.startswith('_'):
            continue
        project_dir = os.path.join(plugin_root, item)
        if os.path.isdir(project_dir):
            plugin_dirs.append(project_dir)

    lines.append(f"外置插件项目数: {len(plugin_dirs)}")

    for project_dir in sorted(plugin_dirs):
        project_name = os.path.basename(project_dir)
        manifest_path = os.path.join(project_dir, 'plugin.json')
        entry_file = 'plugin.py'

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                entry_file = str(manifest.get('entry', 'plugin.py'))
            except Exception as e:
                lines.append(f"插件[{project_name}] manifest: 解析失败({e})")

        entry_path = os.path.join(project_dir, entry_file)
        if os.path.exists(entry_path):
            lines.append(f"插件[{project_name}] 入口: 正常({entry_file})")
        else:
            lines.append(f"插件[{project_name}] 入口: 缺失({entry_file})")

        if os.path.exists(entry_path):
            try:
                with open(entry_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                compile(source, entry_path, 'exec')
                lines.append(f"插件[{project_name}] 语法: 正常")
            except Exception as e:
                lines.append(f"插件[{project_name}] 语法: 失败({e})")

            # 尝试导入插件入口，确保插件可被框架加载。
            try:
                module_name = f"plugin_selfcheck_{project_name}"
                spec = importlib.util.spec_from_file_location(module_name, entry_path)
                if spec is None or spec.loader is None:
                    lines.append(f"插件[{project_name}] 导入: 失败(无法创建模块规格)")
                else:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    has_register = callable(getattr(module, 'register', None))
                    has_plugin_class = isinstance(getattr(module, 'Plugin', None), type)
                    if has_register or has_plugin_class:
                        lines.append(f"插件[{project_name}] 导入: 正常")
                    else:
                        lines.append(f"插件[{project_name}] 导入: 警告(缺少 register/Plugin 入口)")
            except Exception as e:
                err = str(e).strip()
                if not err:
                    err = traceback.format_exc().splitlines()[-1] if traceback.format_exc() else 'unknown error'
                lines.append(f"插件[{project_name}] 导入: 失败({err})")

        runtime_cfg_path = os.path.join(project_dir, 'config.json')
        if os.path.exists(runtime_cfg_path):
            try:
                with open(runtime_cfg_path, 'r', encoding='utf-8') as f:
                    runtime_cfg = json.load(f)
                if isinstance(runtime_cfg, dict):
                    lines.append(f"插件[{project_name}] 配置: 正常")
                else:
                    lines.append(f"插件[{project_name}] 配置: 非对象JSON")
            except Exception as e:
                lines.append(f"插件[{project_name}] 配置: 解析失败({e})")
        else:
            lines.append(f"插件[{project_name}] 配置: 未发现(config.json)")

        req_path = os.path.join(project_dir, 'requirements.txt')
        if os.path.exists(req_path):
            missing_modules = []
            try:
                with open(req_path, 'r', encoding='utf-8') as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith('#'):
                            continue
                        pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=', 1)[0].strip()
                        top_level = pkg.replace('-', '_')
                        # Map known pip package -> import module aliases
                        _alias_map = {
                            'pyyaml': 'yaml',
                            'pillow': 'PIL',
                            'python_dotenv': 'dotenv',
                            'python_docx': 'docx',
                            'python_pptx': 'pptx',
                            'mysql_connector_python': 'mysql.connector',
                            'psycopg2_binary': 'psycopg2',
                            'pytest_benchmark': 'pytest_benchmark',
                        }
                        check_module = _alias_map.get(top_level, top_level)
                        if check_module and importlib.util.find_spec(check_module) is None:
                            missing_modules.append(pkg)
                if missing_modules:
                    lines.append(f"插件[{project_name}] 环境: 缺少依赖({', '.join(missing_modules[:5])})")
                    # Auto-install missing dependencies
                    try:
                        from app.core.dependency_checker import check_and_install
                        check_and_install(req_path, f"Auto:{project_name}")
                    except Exception:
                        pass
                else:
                    lines.append(f"插件[{project_name}] 环境: 依赖可用")
            except Exception as e:
                lines.append(f"插件[{project_name}] 环境: 检查失败({e})")

    return lines


def check_service_status():
    """检查所有服务的状态
    
    Returns:
        str: 服务状态报告
    """
    results = []

    # 仅检查可配置端口，避免页面路由被误当作独立端口服务。
    onebot_cfg = CONFIG.get('onebot', {}) or {}
    onebot_http = onebot_cfg.get('http', {}) if isinstance(onebot_cfg, dict) else {}
    onebot_ws = onebot_cfg.get('ws', {}) if isinstance(onebot_cfg, dict) else {}

    ports_to_check = [
        (int(CONFIG.get('server', {}).get('port', 8888) or 8888), "Web服务器"),
        (int(CONFIG.get('unified_api', {}).get('port', 8000) or 8000), "统一API"),
    ]

    # 兼容旧版 onebot(host/port) 和新版 onebot(http/ws/ws_reverse) 结构。
    if isinstance(onebot_http, dict) and onebot_http:
        if bool(onebot_http.get('enable', True)):
            ports_to_check.append((int(onebot_http.get('port', 3000) or 3000), "OneBot HTTP"))
    else:
        ports_to_check.append((int(onebot_cfg.get('port', 8000) or 8000), "OneBot"))

    if isinstance(onebot_ws, dict) and onebot_ws and bool(onebot_ws.get('enable', False)):
        ports_to_check.append((int(onebot_ws.get('port', 3001) or 3001), "OneBot WS"))

    reverse_cfg = onebot_cfg.get('ws_reverse', {}) if isinstance(onebot_cfg, dict) else {}
    if isinstance(reverse_cfg, dict):
        reverse_enabled = bool(reverse_cfg.get('enable', False))
        reverse_url = str(reverse_cfg.get('url', '') or '').strip() or 'ws://127.0.0.1:6199/ws'
        results.append(f"OneBot Reverse WS: {'启用' if reverse_enabled else '禁用'} -> {reverse_url}")

    extra_ports = SYSTEM_CONFIG_DATA.get('service_ports', {})
    if isinstance(extra_ports, dict):
        for key, value in extra_ports.items():
            try:
                ports_to_check.append((int(value), f"{key}服务"))
            except (TypeError, ValueError):
                continue

    unique_ports = []
    seen_ports = set()
    for port, name in ports_to_check:
        if port in seen_ports:
            continue
        seen_ports.add(port)
        unique_ports.append((port, name))

    for port, name in unique_ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            status = "空闲" if s.connect_ex(('localhost', port)) != 0 else "占用"
            results.append(f"{name} ({port}): {status}")

    # 检查数据库
    try:
        from app.database.database import get_connection

        conn = get_connection()
        if conn:
            results.append("数据库状态: 正常")
            conn.close()
        else:
            results.append("数据库状态: 连接失败")
    except Exception as e:
        results.append(f"数据库状态: 失败({str(e)})")

    # 检查API密钥
    api_sources = {
        'deepseek_chat': CONFIG_DATA.get('api_keys', {}).get('deepseek_chat', {}),
        'search': CONFIG_DATA.get('api_keys', {}).get('search', {}),
        'image_recognition': CONFIG_DATA.get('api_keys', {}).get('image_recognition', {}),
        'image_generation': CONFIG_DATA.get('api_keys', {}).get('image_generation', {}),
        'video_generation': CONFIG_DATA.get('api_keys', {}).get('video_generation', {}),
    }
    coder_provider = CONFIG.get('coder_api', {}).get('provider', 'kimi')
    coder_provider_cfg = CONFIG.get('coder_api', {}).get('providers', {}).get(coder_provider, {})
    api_sources[f'coder_{coder_provider}'] = coder_provider_cfg

    for api_name, api_cfg in api_sources.items():
        key = api_cfg.get('key', '')
        base_url = api_cfg.get('base_url', '')
        if not base_url:
            results.append(f"{api_name}: 未配置")
            continue
        if not key:
            results.append(f"{api_name}: 未设置密钥")
            continue

        try:
            headers = {"Authorization": f"Bearer {key}"}
            response = requests.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=5)
            api_status = "正常" if response.status_code == 200 else f"错误({response.status_code})"
            results.append(f"{api_name}: {api_status}")
        except requests.RequestException as e:
            results.append(f"{api_name}: 失败({str(e)})")

    # 插件系统静态自检
    try:
        for line in _check_plugins_health():
            results.append(line)
    except Exception as e:
        results.append(f"插件自检: 失败({e})")

    return "\n".join(results)
