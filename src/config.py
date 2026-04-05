"""配置模块，用于加载和管理应用程序配置"""

import json
import os
import socket

import requests

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """从JSON文件加载配置"""
    config_path = os.path.join(PROJECT_ROOT, 'data', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = json.load(f)
    except Exception:
        full_config = {}

    # 1. Load active persona
    active_persona = full_config.get('active_persona', 'shizuku.json')
    persona_path = os.path.join(PROJECT_ROOT, 'data', 'personas', active_persona)
    
    # Fallback if active persona file doesn't exist
    if not os.path.exists(persona_path):
        personas_dir = os.path.join(PROJECT_ROOT, 'data', 'personas')
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
                    'behavior_rules': persona_data.get('behavior_rules', [])
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
    db_path = os.path.join(PROJECT_ROOT, 'data', 'database.json')
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                full_config['database'] = json.load(f)
        except Exception as e:
            print(f"Error loading database config: {e}")
    
    return full_config


# 加载配置
CONFIG_DATA = load_config()


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
        'port': 8888,  # Web服务器端口
        'log_file': os.path.join(PROJECT_ROOT, 'app.log'),  # 使用绝对路径
    },
    'api': {
        'key': CONFIG_DATA['api_keys']['deepseek_chat']['key'],
        'base_url': CONFIG_DATA['api_keys']['deepseek_chat']['base_url']
    },
    'aliyun_api': {
        'key': CONFIG_DATA['api_keys']['image_recognition']['key'],
        'base_url': CONFIG_DATA['api_keys']['image_recognition']['base_url']
    },
    'search_api': {
        'key': CONFIG_DATA['api_keys']['search']['key'],
        'base_url': CONFIG_DATA['api_keys']['search']['base_url']
    },
    'image_generation_api': {
        'key': CONFIG_DATA['api_keys']['image_generation']['key'],
        'base_url': CONFIG_DATA['api_keys']['image_generation']['base_url']
    },
    'video_generation_api': {
        'key': CONFIG_DATA['api_keys']['video_generation']['key'],
        'base_url': CONFIG_DATA['api_keys']['video_generation']['base_url']
    },
    'coder_api': CODER_API_CONFIG,
    'character': CONFIG_DATA['character'],
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
        'behavior_rules': CONFIG_DATA.get('persona_runtime', {}).get('behavior_rules', [])
    },
    'database': CONFIG_DATA.get('database', {
        'engine': 'mysql',
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'yyty511511',
        'database': 'catgirl_db'
    }),
    'unified_api': CONFIG_DATA.get('unified_api', {
        'host': '0.0.0.0',
        'port': 8000,
        'access_token': 'neko-proxy-key-123'
    }),
    'work_mode': {
        'enabled': CONFIG_DATA.get('work_mode', {}).get('enabled', False),
        'password_hash': CONFIG_DATA.get('work_mode', {}).get('password_hash', ''),
        'sandbox_enabled': False,
        'features': {
            'allow_file_write': CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_file_write', True),
            'allow_code_exec': CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_code_exec', True),
            'allow_plan_update': CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_plan_update', True),
            'allow_coder_tool': CONFIG_DATA.get('work_mode', {}).get('features', {}).get('allow_coder_tool', True)
        },
        'allowed_databases': CONFIG_DATA.get('work_mode', {}).get('allowed_databases', ['catgirl_db'])
    }
}


def check_service_status():
    """检查所有服务的状态
    
    Returns:
        str: 服务状态报告
    """
    results = []

    # 检查服务端口
    ports_to_check = [
        (8888, "Web服务器"),
        (8081, "控制面板"),
        (8082, "数据库管理"),
        (8083, "日志服务"),
        (5000, "Koishi主端口"),
        (5001, "Koishi备用端口")
    ]

    for port, name in ports_to_check:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            status = "空闲" if s.connect_ex(('localhost', port)) != 0 else "占用"
            results.append(f"{name} ({port}): {status}")

    # 检查API密钥
    try:
        headers = {"Authorization": f"Bearer {CONFIG['api']['key']}"}
        response = requests.get(
            f"{CONFIG['api']['base_url']}/models",
            headers=headers,
            timeout=5
        )
        api_status = "正常" if response.status_code == 200 else f"错误({response.status_code})"
        results.append(f"API状态: {api_status}")
    except requests.RequestException as e:
        results.append(f"API连接失败: {str(e)}")

    return "\n".join(results)
