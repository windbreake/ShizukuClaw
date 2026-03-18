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
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 加载配置
CONFIG_DATA = load_config()


def generate_system_prompt(character, template):
    """根据模板和角色配置生成系统提示语
    
    Args:
        character (dict): 角色配置信息
        template (str): 系统提示语模板
        
    Returns:
        str: 生成的系统提示语
    """
    # 提取口癖并处理
    catchphrases = character['catchphrases'] or '喵'
    phrases_list = [phrase.strip() for phrase in catchphrases.split(',') if phrase.strip()]

    # 格式化模板
    system_prompt = template.format(
        name=character['name'],
        personality=character['personality'],
        brother_qqid=character['brother_qqid'],
        catchphrases=catchphrases,
        first_catchphrase=phrases_list[0] if phrases_list else '喵~',
        second_catchphrase=phrases_list[1] if len(phrases_list) > 1 else '哒！'
    )

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
    'character': CONFIG_DATA['character'],
    'system_prompt': generate_system_prompt(CONFIG_DATA['character'], 
                                            CONFIG_DATA['system_prompt_template']),
    'database': CONFIG_DATA.get('database', {
        'host': 'localhost',
        'user': 'root',
        'password': '!NGC339cn',
        'database': 'catgirl_db'
    })
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
