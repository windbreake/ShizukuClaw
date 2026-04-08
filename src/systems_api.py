# -*- coding: utf-8 -*-
"""
系统集成模块 - 整合所有新系统的API接口
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import json
import re
import requests
import shlex
import time
import os
import shutil
import subprocess
import threading
import uuid
from html import unescape

# 导入各个系统
from src.enhanced_logging import get_enhanced_logger
from src.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
from src.mcp_manager import get_mcp_manager, MCPServer, MCPResource, MCPTool
from src.knowledge_base_manager import get_knowledge_base_manager, KnowledgeEntry, Glossary, EntryType
from src.instruction_manager import (
    get_instruction_manager, AgentInstruction, Personality, 
    BehaviorRule, InstructionType
)

# 创建蓝图
systems_bp = Blueprint('systems', __name__, url_prefix='/api/systems')

# 官方 MCP Registry API 端点（内置式，可覆盖）
# 常见的 MCP Registry 源：
# - 官方: https://mcp.run/api/servers
# - Smithery: https://registry.smithery.ai/servers
MCP_REGISTRY_API = 'https://mcp.run/api/servers'
MCP_REGISTRY_CACHE = {'ts': 0.0, 'data': []}
MCP_REGISTRY_CACHE_TTL = 3600  # 1 小时缓存
MCP_SMITHERY_CACHE = {'entries': {}}
MCP_SMITHERY_CACHE_TTL = 900
MCP_SMITHERY_STATUS_CACHE = {'ts': 0.0, 'data': None}
MCP_SMITHERY_STATUS_CACHE_TTL = 15
MCP_SMITHERY_INSTALL_JOBS = {}
MCP_SMITHERY_INSTALL_JOBS_LOCK = threading.Lock()
MCP_SMITHERY_INSTALL_JOB_TTL = 3600

# 本地官方 MCP 示例（如果 Smithery 不可用）
MCP_MARKET_CATALOG = [
    {
        'id': 'filesystem-local',
        'name': 'Filesystem Local',
        'description': '读写本地工作目录（stdio）',
        'type': 'stdio',
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-filesystem', '.'],
        'tags': ['file', 'local', 'official']
    },
    {
        'id': 'git-local',
        'name': 'Git Local',
        'description': 'Git 仓库操作（stdio）',
        'type': 'stdio',
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-git', '.'],
        'tags': ['git', 'scm', 'official']
    },
    {
        'id': 'fetch-web',
        'name': 'Fetch Web',
        'description': '网页抓取与摘要（stdio）',
        'type': 'stdio',
        'command': 'uvx',
        'args': ['mcp-server-fetch'],
        'tags': ['web', 'crawler', 'official']
    },
    {
        'id': 'sqlite-local',
        'name': 'SQLite Local',
        'description': '快速连接 SQLite 文件',
        'type': 'stdio',
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-sqlite', '--db-path', 'data/database.sqlite'],
        'tags': ['database', 'sqlite']
    }
]


def _load_smithery_config():
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config_path = os.path.join(base_path, 'data', 'config.json')
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        market_cfg = cfg.get('mcp_market', {}) or {}
        return market_cfg.get('smithery', {}) or {}
    except Exception:
        return {}


def _smithery_runner():
    cfg = _load_smithery_config()
    configured_bin = str(cfg.get('cli_bin') or '').strip()
    candidate_bins = []
    if configured_bin:
        candidate_bins.append(configured_bin)
    candidate_bins.extend(['smithery'])

    seen = set()
    for b in candidate_bins:
        if not b or b in seen:
            continue
        seen.add(b)
        full = shutil.which(b)
        if full:
            return [full]

    npx = shutil.which('npx')
    if npx:
        return [npx, '-y', '@smithery/cli@latest']
    return []


def _smithery_runner_info():
    cfg = _load_smithery_config()
    configured_bin = str(cfg.get('cli_bin') or '').strip()

    if configured_bin:
        full = shutil.which(configured_bin)
        if full:
            return {
                'runner': [full],
                'installed': True,
                'mode': 'configured',
                'cli': full,
            }

    global_bin = shutil.which('smithery')
    if global_bin:
        return {
            'runner': [global_bin],
            'installed': True,
            'mode': 'global',
            'cli': global_bin,
        }

    npx = shutil.which('npx')
    if npx:
        return {
            'runner': [npx, '-y', '@smithery/cli@latest'],
            'installed': False,
            'mode': 'npx-fallback',
            'cli': f'{npx} -y @smithery/cli@latest',
        }

    return {
        'runner': [],
        'installed': False,
        'mode': 'missing',
        'cli': '',
    }


def _find_smithery_cli():
    info = _smithery_runner_info()
    return str(info.get('cli') or '').strip()


def _run_smithery_cli(args, timeout=45):
    info = _smithery_runner_info()
    runner = list(info.get('runner') or [])
    if not runner:
        raise RuntimeError('Smithery CLI 未安装，请先点击“安装 Smithery CLI”')
    cmd = list(runner) + list(args or [])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=max(5, int(timeout or 45)),
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    )
    return {
        'ok': proc.returncode == 0,
        'code': int(proc.returncode),
        'stdout': str(proc.stdout or ''),
        'stderr': str(proc.stderr or ''),
        'cmd': cmd,
    }


def _extract_json_from_text(text):
    raw = str(text or '').strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass

    s1 = raw.find('[')
    s2 = raw.find('{')
    starts = [x for x in [s1, s2] if x >= 0]
    if not starts:
        return None
    start = min(starts)

    for end in range(len(raw), start, -1):
        chunk = raw[start:end].strip()
        if not chunk:
            continue
        try:
            return json.loads(chunk)
        except Exception:
            continue
    return None


def _clean_smithery_text(value):
    text = str(value or '')
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'[│┆┊|]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ''
    lowered = text.lower()
    if lowered in {'custom', 'unknown', 'undefined', 'null', '-', '---', '...', '....'}:
        return ''
    if not re.search(r'[\w\u4e00-\u9fff]', text):
        return ''
    return text


def _normalize_smithery_mcp_items(payload):
    rows = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for k in ('items', 'data', 'list', 'servers', 'results'):
            v = payload.get(k)
            if isinstance(v, list):
                rows = v
                break

    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        sid = str(it.get('qualifiedName') or it.get('id') or it.get('slug') or it.get('name') or '').strip()
        if not sid:
            continue

        name = _clean_smithery_text(it.get('name') or sid) or sid
        description = _clean_smithery_text(it.get('description') or '')
        author = _clean_smithery_text(it.get('author') or it.get('owner') or it.get('namespace') or '')
        tags = []
        for tag in list(it.get('tags') or it.get('keywords') or it.get('topics') or []):
            cleaned = _clean_smithery_text(tag)
            if cleaned:
                tags.append(cleaned)

        connection_url = str(it.get('connectionUrl') or it.get('connection_url') or '').strip()
        registry_url = str(it.get('registry_url') or it.get('url') or '').strip()
        if not registry_url:
            registry_url = f'https://smithery.ai/servers/{sid}'

        out.append({
            'id': sid,
            'name': name,
            'description': description,
            'author': author,
            'version': _clean_smithery_text(it.get('version') or ''),
            'keywords': tags,
            'tags': tags,
            'type': _clean_smithery_text(it.get('type') or it.get('protocol') or 'remote') or 'remote',
            'homepage': str(it.get('homepage') or ''),
            'repository': str(it.get('repository') or ''),
            'documentation': str(it.get('documentation') or ''),
            'registry_url': registry_url,
            'connection_url': connection_url,
            'protocol_version': _clean_smithery_text(it.get('protocol_version') or '1.0') or '1.0',
            'implementation': _clean_smithery_text(it.get('implementation') or ''),
            'source': 'smithery',
            'installable': True,
            'user_config_required': False,
            'stars': int(it.get('useCount') or it.get('stars') or 0),
        })
    return out


def _mcp_smithery_cache_key(query: str, extra: str = ''):
    return f"{str(query or '').strip().lower()}|{str(extra or '').strip().lower()}"


def _mcp_smithery_cache_get(key: str):
    now = time.time()
    entry = MCP_SMITHERY_CACHE.get('entries', {}).get(key)
    if not entry:
        return None
    if (now - float(entry.get('ts') or 0.0)) > MCP_SMITHERY_CACHE_TTL:
        return None
    return dict(entry)


def _mcp_smithery_cache_set(key: str, items, diag: dict = None):
    MCP_SMITHERY_CACHE.setdefault('entries', {})[key] = {
        'ts': time.time(),
        'items': list(items or []),
        'diag': dict(diag or {}),
    }


def _smithery_install_job_prune_locked(now=None):
    now = now or time.time()
    stale_ids = []
    for job_id, job in list(MCP_SMITHERY_INSTALL_JOBS.items()):
        updated_at = float(job.get('updated_at') or job.get('created_at') or 0.0)
        if job.get('status') in ('running', 'queued'):
            continue
        if (now - updated_at) > MCP_SMITHERY_INSTALL_JOB_TTL:
            stale_ids.append(job_id)
    for job_id in stale_ids:
        MCP_SMITHERY_INSTALL_JOBS.pop(job_id, None)


def _smithery_install_job_snapshot(job_id: str):
    with MCP_SMITHERY_INSTALL_JOBS_LOCK:
        _smithery_install_job_prune_locked()
        job = MCP_SMITHERY_INSTALL_JOBS.get(job_id)
        if not job:
            return None
        return {
            'job_id': job.get('job_id', job_id),
            'status': job.get('status', 'queued'),
            'created_at': job.get('created_at'),
            'updated_at': job.get('updated_at'),
            'command_display': job.get('command_display', ''),
            'returncode': job.get('returncode'),
            'message': job.get('message', ''),
            'logs': list(job.get('logs') or []),
            'installed': bool(job.get('status') == 'success'),
        }


def _smithery_install_job_append(job_id: str, line: str):
    text = str(line or '').replace('\r', '').rstrip('\n')
    if not text.strip():
        return
    log_line = text.strip('\n')
    now = time.time()
    with MCP_SMITHERY_INSTALL_JOBS_LOCK:
        job = MCP_SMITHERY_INSTALL_JOBS.get(job_id)
        if not job:
            return
        logs = list(job.get('logs') or [])
        logs.append(log_line)
        if len(logs) > 400:
            logs = logs[-400:]
        job['logs'] = logs
        job['updated_at'] = now
    print(f"[Smithery CLI][{job_id}] {log_line}")


def _smithery_install_job_finish(job_id: str, status: str, message: str, returncode: int = None):
    now = time.time()
    with MCP_SMITHERY_INSTALL_JOBS_LOCK:
        job = MCP_SMITHERY_INSTALL_JOBS.get(job_id)
        if not job:
            return
        job['status'] = status
        job['message'] = str(message or '')
        job['updated_at'] = now
        if returncode is not None:
            job['returncode'] = int(returncode)
        job['logs'] = list(job.get('logs') or [])
    print(f"[Smithery CLI][{job_id}] {status.upper()}: {message}")


def _start_smithery_install_job():
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('未找到 npm，请先安装 Node.js 20+')

    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    command = [npm, 'install', '-g', '@smithery/cli@latest']
    command_display = 'npm install -g @smithery/cli@latest'
    job_id = uuid.uuid4().hex
    now = time.time()

    with MCP_SMITHERY_INSTALL_JOBS_LOCK:
        _smithery_install_job_prune_locked(now)
        MCP_SMITHERY_INSTALL_JOBS[job_id] = {
            'job_id': job_id,
            'status': 'queued',
            'created_at': now,
            'updated_at': now,
            'command_display': command_display,
            'returncode': None,
            'message': '准备启动 Smithery CLI 安装',
            'logs': [
                '准备安装 Smithery CLI',
                f'命令: {command_display}',
            ],
        }

    def _runner():
        process = None
        try:
            with MCP_SMITHERY_INSTALL_JOBS_LOCK:
                job = MCP_SMITHERY_INSTALL_JOBS.get(job_id)
                if job:
                    job['status'] = 'running'
                    job['updated_at'] = time.time()

            _smithery_install_job_append(job_id, f'工作目录: {base_path}')
            _smithery_install_job_append(job_id, f'开始执行: {command_display}')

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                cwd=base_path,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            if process.stdout:
                for raw_line in iter(process.stdout.readline, ''):
                    if raw_line == '':
                        break
                    _smithery_install_job_append(job_id, raw_line)

            returncode = process.wait()
            if returncode == 0:
                cli = _find_smithery_cli()
                _smithery_install_job_append(job_id, f'检测到 CLI: {cli or "未检测到"}')
                _smithery_install_job_finish(job_id, 'success', 'Smithery CLI 安装完成', returncode)
            else:
                _smithery_install_job_append(job_id, f'安装命令退出码: {returncode}')
                _smithery_install_job_finish(job_id, 'error', 'Smithery CLI 安装失败，请查看日志', returncode)
        except Exception as exc:
            _smithery_install_job_append(job_id, f'安装异常: {exc}')
            _smithery_install_job_finish(job_id, 'error', str(exc), -1)
        finally:
            try:
                if process and process.stdout:
                    process.stdout.close()
            except Exception:
                pass

    threading.Thread(target=_runner, daemon=True).start()
    return _smithery_install_job_snapshot(job_id)




def _fetch_official_mcp_registry(limit: int = 30, registry_url: str = None):
    """从官方 MCP Registry 获取服务器元数据及完整信息。
    
    返回格式包含：
    - id, name, description（基础信息）
    - author, license, homepage, documentation（详细信息）
    - protocol_version, implementation（实现细节）
    - registry_url（官方注册表链接，用于跳转）
    - user_config_required（用户需要手动配置）
    """
    limit = max(1, min(200, int(limit or 30)))
    api_url = registry_url or MCP_REGISTRY_API
    
    # 检查缓存
    global MCP_REGISTRY_CACHE
    now = time.time()
    if MCP_REGISTRY_CACHE.get('ts', 0) + MCP_REGISTRY_CACHE_TTL > now and MCP_REGISTRY_CACHE.get('data'):
        return MCP_REGISTRY_CACHE['data'][:limit]
    
    items = []
    try:
        # 调用官方 MCP Registry API
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # 兼容多种 API 返回格式
        servers = data.get('servers', []) or data.get('data', []) or (data if isinstance(data, list) else [])
        
        for srv in servers:
            item = {
                # 基础信息
                'id': str(srv.get('id') or srv.get('name', '').lower().replace(' ', '-')),
                'name': str(srv.get('name') or 'MCP Server'),
                'description': str(srv.get('description') or ''),
                
                # 详细元数据
                'author': str(srv.get('author') or srv.get('maintainer', '')),
                'license': str(srv.get('license', '')),
                'version': str(srv.get('version', '')),
                'keywords': list(srv.get('keywords', [])) or list(srv.get('tags', [])) or [],
                
                # 链接信息
                'homepage': str(srv.get('homepage') or srv.get('url', '')),
                'repository': str(srv.get('repository') or srv.get('repo', '')),
                'documentation': str(srv.get('documentation') or srv.get('docs', '')),
                'registry_url': str(srv.get('registry_url', f'https://mcp.run/servers/{srv.get("id", "")}')),
                
                # 实现信息
                'protocol_version': str(srv.get('protocol_version', '1.0')),
                'implementation': str(srv.get('implementation', '')),
                'type': str(srv.get('protocol', srv.get('type', 'stdio'))),
                
                # 安装提示
                'user_config_required': True,  # 用户需要自己配置连接参数
                'source': 'mcp-registry',
                'installable': True,
            }
            items.append(item)
        
        # 更新缓存
        if items:
            MCP_REGISTRY_CACHE = {'ts': now, 'data': items}
            return items[:limit]
    except Exception as e:
        pass
    
    # 回退到本地官方目录
    for it in MCP_MARKET_CATALOG:
        items.append({
            'id': str(it.get('id') or ''),
            'name': str(it.get('name') or 'Official MCP'),
            'description': str(it.get('description') or ''),
            'author': 'Anthropic',
            'license': 'MIT',
            'version': '1.0',
            'keywords': list(it.get('tags') or ['official']),
            'homepage': 'https://modelcontextprotocol.io',
            'repository': 'https://github.com/modelcontextprotocol',
            'documentation': 'https://modelcontextprotocol.io/docs',
            'registry_url': 'https://mcp.run',
            'protocol_version': '1.0',
            'implementation': f"{it.get('type', 'stdio')}: {it.get('command', '')}",
            'type': str(it.get('type') or 'stdio'),
            'user_config_required': True,
            'source': 'official-local',
            'installable': True,
        })
    
    return items[:limit]


def _fetch_mcpmarket_trending(limit: int = 30):
    """[兼容函数] 从官方 MCP Registry 获取趋势 MCP。"""
    return _fetch_official_mcp_registry(limit)


def _parse_mcp_command_from_page(html: str):
    text = unescape(str(html or ''))

    # 优先解析 JSON 风格 command/args。
    cmd_match = re.search(r'"command"\s*:\s*"([^"]+)"', text, flags=re.IGNORECASE)
    args_match = re.search(r'"args"\s*:\s*\[(.*?)\]', text, flags=re.IGNORECASE | re.DOTALL)
    if cmd_match:
        command = cmd_match.group(1).strip()
        args = []
        if args_match:
            raw_args = args_match.group(1)
            args = re.findall(r'"([^"]+)"', raw_args)
        return {'type': 'stdio', 'command': command, 'args': args}

    # 其次解析 shell 行命令。
    line_match = re.search(r'(npx|uvx|python3?|node)\s+([^\n<`]+)', text, flags=re.IGNORECASE)
    if line_match:
        line = f"{line_match.group(1)} {line_match.group(2)}".strip()
        try:
            parts = shlex.split(line)
        except Exception:
            parts = line.split()
        if parts:
            return {'type': 'stdio', 'command': parts[0], 'args': parts[1:]}

    # 最后尝试识别 SSE / HTTP URL。
    url_match = re.search(r'https?://[^\s"\'<>]+', text)
    if url_match:
        return {'type': 'http', 'url': url_match.group(0).strip()}

    return None

# ===== 日志API =====

@systems_bp.route('/logs', methods=['GET'])
def get_logs():
    """获取系统日志"""
    logger = get_enhanced_logger()
    level = request.args.get('level')
    limit = request.args.get('limit', 100, type=int)
    
    entries = logger.get_entries(level=level, limit=limit)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': entries,
        'count': len(entries)
    })

@systems_bp.route('/logs/clear', methods=['POST'])
def clear_logs():
    """清除日志"""
    logger = get_enhanced_logger()
    logger.clear_entries()
    return jsonify({
        'code': 0,
        'message': 'Logs cleared'
    })

# ===== 任务调度API =====

@systems_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """列表任务"""
    scheduler = get_task_scheduler()
    status = request.args.get('status')
    
    tasks = scheduler.list_tasks(status=status)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': tasks,
        'count': len(tasks)
    })

@systems_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    try:
        data = request.json
        
        task = AgentTask(
            name=data.get('name', ''),
            description=data.get('description', ''),
            task_type=data.get('task_type', TaskType.ONE_TIME.value),
            command=data.get('command', ''),
            args=data.get('args', {}),
            scheduled_time=data.get('scheduled_time'),
            cron_expression=data.get('cron_expression'),
            interval_seconds=data.get('interval_seconds'),
            max_retries=data.get('max_retries', 3),
            enabled=data.get('enabled', True),
            notify_on_complete=data.get('notify_on_complete', True)
        )
        
        scheduler = get_task_scheduler()
        task_id = scheduler.add_task(task)
        
        return jsonify({
            'code': 0,
            'message': 'Task created',
            'data': {'id': task_id}
        }), 201
    except Exception as e:
        return jsonify({
            'code': 400,
            'message': str(e)
        }), 400

@systems_bp.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    scheduler = get_task_scheduler()
    task = scheduler.get_task(task_id)
    
    if not task:
        return jsonify({'code': 404, 'message': 'Task not found'}), 404
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': task.to_dict()
    })

@systems_bp.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    try:
        data = request.json
        scheduler = get_task_scheduler()
        task = scheduler.update_task(task_id, data)
        
        if not task:
            return jsonify({'code': 404, 'message': 'Task not found'}), 404
        
        return jsonify({
            'code': 0,
            'message': 'Task updated',
            'data': task.to_dict()
        })
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    scheduler = get_task_scheduler()
    if scheduler.delete_task(task_id):
        return jsonify({'code': 0, 'message': 'Task deleted'})
    return jsonify({'code': 404, 'message': 'Task not found'}), 404

@systems_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    scheduler = get_task_scheduler()
    if scheduler.cancel_task(task_id):
        return jsonify({'code': 0, 'message': 'Task cancelled'})
    return jsonify({'code': 404, 'message': 'Task not found'}), 404

@systems_bp.route('/tasks/<task_id>/results', methods=['GET'])
def get_task_results(task_id):
    """获取任务执行结果"""
    scheduler = get_task_scheduler()
    limit = request.args.get('limit', 50, type=int)
    results = scheduler.get_task_results(task_id, limit)
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': results,
        'count': len(results)
    })

# ===== MCP API =====

@systems_bp.route('/mcp/servers', methods=['GET'])
def list_mcp_servers():
    """列表MCP服务器"""
    manager = get_mcp_manager()
    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
    servers = manager.list_servers(enabled_only=enabled_only)
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': servers,
        'count': len(servers)
    })

@systems_bp.route('/mcp/servers', methods=['POST'])
def create_mcp_server():
    """创建MCP服务器"""
    try:
        data = request.json
        
        server = MCPServer(
            name=data.get('name', ''),
            description=data.get('description', ''),
            protocol_version=data.get('protocol_version', '1.0'),
            type=data.get('type', ''),
            command=data.get('command', ''),
            args=data.get('args', []),
            url=data.get('url'),
            headers=data.get('headers', {}),
            capabilities=data.get('capabilities', {}),
            enabled=data.get('enabled', True)
        )
        
        manager = get_mcp_manager()
        server_id = manager.add_server(server)
        
        return jsonify({
            'code': 0,
            'message': 'Server created',
            'data': {'id': server_id}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/mcp/servers/<server_id>', methods=['GET'])
def get_mcp_server(server_id):
    """获取MCP服务器"""
    manager = get_mcp_manager()
    server = manager.get_server(server_id)
    
    if not server:
        return jsonify({'code': 404, 'message': 'Server not found'}), 404
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': server.to_dict()
    })

@systems_bp.route('/mcp/servers/<server_id>', methods=['PUT'])
def update_mcp_server(server_id):
    """更新MCP服务器"""
    try:
        data = request.json
        manager = get_mcp_manager()
        server = manager.update_server(server_id, data)
        
        if not server:
            return jsonify({'code': 404, 'message': 'Server not found'}), 404
        
        return jsonify({
            'code': 0,
            'message': 'Server updated',
            'data': server.to_dict()
        })
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/mcp/servers/<server_id>', methods=['DELETE'])
def delete_mcp_server(server_id):
    """删除MCP服务器"""
    manager = get_mcp_manager()
    if manager.delete_server(server_id):
        return jsonify({'code': 0, 'message': 'Server deleted'})
    return jsonify({'code': 404, 'message': 'Server not found'}), 404


@systems_bp.route('/mcp/market', methods=['GET'])
def list_mcp_market_catalog():
    """返回内置 MCP 市场条目"""
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': MCP_MARKET_CATALOG,
        'count': len(MCP_MARKET_CATALOG)
    })


@systems_bp.route('/mcp/market/install', methods=['POST'])
def install_mcp_market_item():
    """根据市场条目一键创建 MCP server"""
    try:
        data = request.json or {}
        item_id = str(data.get('id', '')).strip()
        if not item_id:
            return jsonify({'code': 400, 'message': 'id is required'}), 400

        market_item = next((x for x in MCP_MARKET_CATALOG if x.get('id') == item_id), None)
        if market_item is None:
            return jsonify({'code': 404, 'message': 'Market item not found'}), 404

        manager = get_mcp_manager()
        servers = manager.list_servers(enabled_only=False)
        for s in servers:
            if (s.get('name') or '').strip().lower() == (market_item.get('name') or '').strip().lower():
                return jsonify({
                    'code': 0,
                    'message': 'Server already exists',
                    'data': {'id': s.get('id'), 'name': s.get('name'), 'exists': True}
                })

        server = MCPServer(
            name=market_item.get('name', ''),
            description=market_item.get('description', ''),
            protocol_version='1.0',
            type=market_item.get('type', ''),
            command=market_item.get('command', ''),
            args=list(market_item.get('args', []) or []),
            url=market_item.get('url'),
            enabled=True,
            capabilities={'tags': list(market_item.get('tags', []) or []), 'source': 'market'}
        )

        if server.type in ('http', 'sse'):
            server.url = market_item.get('url', '')

        server_id = manager.add_server(server)
        return jsonify({
            'code': 0,
            'message': 'Server installed',
            'data': {'id': server_id, 'name': server.name, 'exists': False}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400


@systems_bp.route('/mcp/market/smithery/search', methods=['GET'])
@systems_bp.route('/mcp/market/registry', methods=['GET'])
@systems_bp.route('/mcp/market/mcpmarket', methods=['GET'])
def list_mcpmarket_items():
    """Smithery CLI 驱动的 MCP 商店检索（兼容旧路由）。"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 30, type=int)
        query = str(request.args.get('query', '') or '').strip().lower()

        page = max(1, int(page or 1))
        page_size = max(5, min(100, int(page_size or 30)))

        cli = _find_smithery_cli()
        if not cli:
            return jsonify({
                'code': 0,
                'message': 'success',
                'data': [],
                'count': 0,
                'page': page,
                'page_size': page_size,
                'total': 0,
                'has_more': False,
                'query': query,
                'mode': 'smithery_cli',
                'cli_installed': False,
                'warning': 'Smithery CLI 未安装，请先安装后再同步商店'
            })

        cache_key = _mcp_smithery_cache_key(query, f'{cli}|p{page}|ps{page_size}')
        cached = _mcp_smithery_cache_get(cache_key)
        if cached and cached.get('items'):
            items = list(cached.get('items') or [])
            diag = dict(cached.get('diag') or {})
            diag.update({'cached': True, 'mode': 'smithery_cli', 'cli': cli})
            return jsonify({
                'code': 0,
                'message': 'success',
                'data': items,
                'count': len(items),
                'page': page,
                'page_size': page_size,
                'total': int(diag.get('total') or len(items)),
                'has_more': bool(diag.get('has_more')),
                'query': query,
                'mode': 'smithery_cli',
                'cli_installed': True,
                'diagnostics': diag,
            })

        effective_query = query or 'github'
        attempts = []
        attempts.extend([
            ['--json', 'mcp', 'search', effective_query, '--page', str(page)],
            ['mcp', 'search', effective_query, '--page', str(page)],
            ['--json', 'mcp', 'search', effective_query],
            ['mcp', 'search', effective_query],
        ])

        payload = None
        text_rows = []
        errors = []
        for args in attempts:
            result = _run_smithery_cli(args, timeout=45)
            if not result.get('ok'):
                errors.append((result.get('stderr') or result.get('stdout') or '').strip()[:300])
                continue

            out = result.get('stdout') or ''
            parsed = _extract_json_from_text(out)
            if parsed is not None:
                payload = parsed
                break

            for line in out.splitlines():
                line = _clean_smithery_text(line)
                if not line:
                    continue
                text_rows.append(line)
            if text_rows:
                break

        items = _normalize_smithery_mcp_items(payload) if payload is not None else []
        has_more = bool((payload or {}).get('hasMore')) if isinstance(payload, dict) else False
        total = (page - 1) * page_size + len(items) + (1 if has_more else 0)
        if not items and text_rows:
            for i, line in enumerate(text_rows, start=1):
                if query and query not in line.lower():
                    continue
                sid = f'smithery-{i}'
                items.append({
                    'id': sid,
                    'name': line[:80],
                    'description': line,
                    'author': '',
                    'version': '',
                    'keywords': [],
                    'tags': [],
                    'type': 'remote',
                    'homepage': '',
                    'repository': '',
                    'documentation': '',
                    'registry_url': '',
                    'connection_url': '',
                    'protocol_version': '1.0',
                    'implementation': '',
                    'source': 'smithery',
                    'installable': True,
                    'user_config_required': False,
                })
            has_more = False
            total = (page - 1) * page_size + len(items)

        _mcp_smithery_cache_set(cache_key, items, {
            'mode': 'smithery_cli',
            'errors': errors[:5],
            'cli': cli,
            'cached': False,
            'has_more': has_more,
            'total': total,
            'effective_query': effective_query,
        })

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': items,
            'count': len(items),
            'page': page,
            'page_size': page_size,
            'total': total,
            'has_more': has_more,
            'query': query,
            'mode': 'smithery_cli',
            'cli_installed': True,
            'diagnostics': {
                'mode': 'smithery_cli',
                'errors': errors[:5],
                'cli': cli,
                'cached': False,
                'effective_query': effective_query,
            }
        })
    except Exception as e:
        return jsonify({
            'code': 502,
            'message': str(e),
            'data': [],
            'count': 0,
            'page': 1,
            'page_size': max(5, min(100, int(request.args.get('page_size', 30) or 30))),
            'total': 0,
            'has_more': False,
            'query': str(request.args.get('query', '') or '').strip().lower(),
            'mode': 'smithery_cli',
        }), 502


@systems_bp.route('/mcp/market/registry/install', methods=['POST'])
@systems_bp.route('/mcp/market/mcpmarket/install', methods=['POST'])
def install_mcpmarket_item_from_url():
    """兼容旧路由：代理到 Smithery CLI 安装。"""
    return install_mcp_smithery_item()


@systems_bp.route('/mcp/market/smithery/status', methods=['GET'])
def mcp_smithery_status():
    """Smithery CLI 状态。"""
    try:
        now = time.time()
        cached_data = MCP_SMITHERY_STATUS_CACHE.get('data')
        cached_ts = float(MCP_SMITHERY_STATUS_CACHE.get('ts') or 0.0)
        if cached_data is not None and (now - cached_ts) <= MCP_SMITHERY_STATUS_CACHE_TTL:
            return jsonify({'code': 0, 'message': 'success', 'data': dict(cached_data)})

        info = _smithery_runner_info()
        cli = str(info.get('cli') or '').strip()
        installed = bool(info.get('installed'))
        mode = str(info.get('mode') or '')
        if not cli:
            data = {'installed': False, 'cli': '', 'version': '', 'mode': 'missing'}
            MCP_SMITHERY_STATUS_CACHE['ts'] = now
            MCP_SMITHERY_STATUS_CACHE['data'] = dict(data)
            return jsonify({'code': 0, 'message': 'success', 'data': data})

        version = ''
        for args in (['--version'], ['version']):
            try:
                r = _run_smithery_cli(args, timeout=10)
                if r.get('ok'):
                    text = (r.get('stdout') or '').strip()
                    version = text.splitlines()[0] if text else ''
                    break
            except Exception:
                continue
        data = {'installed': installed, 'cli': cli, 'version': version, 'mode': mode}
        MCP_SMITHERY_STATUS_CACHE['ts'] = now
        MCP_SMITHERY_STATUS_CACHE['data'] = dict(data)
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@systems_bp.route('/mcp/market/smithery/cli/install', methods=['POST'])
def install_mcp_smithery_cli():
    """后台安装 Smithery CLI，并返回可轮询的 job。"""
    try:
        job = _start_smithery_install_job()
        return jsonify({
            'code': 0,
            'message': 'Smithery CLI 安装已在后台启动',
            'data': {
                'installed': False,
                'job_id': job.get('job_id'),
                'status': job.get('status', 'queued'),
                'command': job.get('command_display', ''),
                'logs': list(job.get('logs') or []),
                'status_url': f"/api/systems/mcp/market/smithery/cli/install/jobs/{job.get('job_id')}",
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@systems_bp.route('/mcp/market/smithery/cli/install/jobs/<job_id>', methods=['GET'])
def mcp_smithery_install_job(job_id):
    """查询 Smithery CLI 安装任务状态和实时日志。"""
    try:
        job = _smithery_install_job_snapshot(str(job_id).strip())
        if not job:
            return jsonify({'code': 404, 'message': 'job not found'}), 404
        return jsonify({'code': 0, 'message': 'success', 'data': job})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@systems_bp.route('/mcp/market/smithery/install', methods=['POST'])
def install_mcp_smithery_item():
    """通过 Smithery CLI 安装/接入 MCP。"""
    try:
        data = request.json or {}
        target = str(data.get('server_id') or data.get('id') or data.get('name') or '').strip()
        connection_url = str(data.get('connection_url') or '').strip()
        target_url = str(data.get('registry_url') or data.get('url') or '').strip()
        target_ref = connection_url or target_url or target

        if not target_ref:
            return jsonify({'code': 400, 'message': 'server_id/url is required'}), 400

        attempts = [
            ['mcp', 'add', target_ref],
        ]
        errors = []
        ok_result = None
        for args in attempts:
            r = _run_smithery_cli(args, timeout=120)
            if r.get('ok'):
                ok_result = r
                break
            errors.append((r.get('stderr') or r.get('stdout') or '').strip()[:500])

        if not ok_result:
            return jsonify({'code': 500, 'message': 'Smithery MCP 接入失败', 'details': errors}), 500

        return jsonify({
            'code': 0,
            'message': f'Smithery MCP 接入完成: {target_ref}',
            'data': {
                'target': target_ref,
                'stdout': (ok_result.get('stdout') or '')[-1200:],
                'cli': _find_smithery_cli(),
            }
        })
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

# ===== 知识库API =====

@systems_bp.route('/knowledge/entries', methods=['GET'])
def list_knowledge_entries():
    """列表知识库条目"""
    manager = get_knowledge_base_manager()
    category = request.args.get('category')
    entry_type = request.args.get('type')
    
    entries = manager.list_entries(category=category, entry_type=entry_type)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': entries,
        'count': len(entries)
    })

@systems_bp.route('/knowledge/entries/search', methods=['GET'])
def search_knowledge_entries():
    """搜索知识库条目"""
    manager = get_knowledge_base_manager()
    query = request.args.get('q', '')
    limit = request.args.get('limit', 20, type=int)
    
    results = manager.search_entries(query, limit)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': results,
        'count': len(results)
    })

@systems_bp.route('/knowledge/entries', methods=['POST'])
def create_knowledge_entry():
    """创建知识库条目"""
    try:
        data = request.json
        
        entry = KnowledgeEntry(
            title=data.get('title', ''),
            content=data.get('content', ''),
            entry_type=data.get('type', EntryType.KNOWLEDGE.value),
            category=data.get('category', ''),
            tags=data.get('tags', []),
            keywords=data.get('keywords', []),
            priority=data.get('priority', 0),
            weight=data.get('weight', 1.0),
            author=data.get('author', ''),
            source=data.get('source', '')
        )
        
        manager = get_knowledge_base_manager()
        entry_id = manager.add_entry(entry)
        
        return jsonify({
            'code': 0,
            'message': 'Entry created',
            'data': {'id': entry_id}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/knowledge/entries/<entry_id>', methods=['GET'])
def get_knowledge_entry(entry_id):
    """获取知识库条目"""
    manager = get_knowledge_base_manager()
    entry = manager.get_entry(entry_id)
    
    if not entry:
        return jsonify({'code': 404, 'message': 'Entry not found'}), 404
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': entry.to_dict()
    })

@systems_bp.route('/knowledge/entries/<entry_id>', methods=['PUT'])
def update_knowledge_entry(entry_id):
    """更新知识库条目"""
    try:
        data = request.json
        manager = get_knowledge_base_manager()
        entry = manager.update_entry(entry_id, data)
        
        if not entry:
            return jsonify({'code': 404, 'message': 'Entry not found'}), 404
        
        return jsonify({
            'code': 0,
            'message': 'Entry updated',
            'data': entry.to_dict()
        })
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/knowledge/entries/<entry_id>', methods=['DELETE'])
def delete_knowledge_entry(entry_id):
    """删除知识库条目"""
    manager = get_knowledge_base_manager()
    if manager.delete_entry(entry_id):
        return jsonify({'code': 0, 'message': 'Entry deleted'})
    return jsonify({'code': 404, 'message': 'Entry not found'}), 404

@systems_bp.route('/knowledge/categories', methods=['GET'])
def get_knowledge_categories():
    """获取知识库分类"""
    manager = get_knowledge_base_manager()
    categories = manager.get_categories()
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': categories,
        'count': len(categories)
    })

# ===== 指令API =====

@systems_bp.route('/instructions', methods=['GET'])
def list_instructions():
    """列表指令"""
    manager = get_instruction_manager()
    instr_type = request.args.get('type')
    agent_id = request.args.get('agent_id')
    
    instructions = manager.list_instructions(
        instruction_type=instr_type,
        agent_id=agent_id
    )
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': instructions,
        'count': len(instructions)
    })

@systems_bp.route('/instructions', methods=['POST'])
def create_instruction():
    """创建指令"""
    try:
        data = request.json
        
        instruction = AgentInstruction(
            name=data.get('name', ''),
            description=data.get('description', ''),
            instruction_type=data.get('type', InstructionType.SYSTEM_PROMPT.value),
            content=data.get('content', ''),
            target_agents=data.get('target_agents', []),
            priority=data.get('priority', 0),
            enabled=data.get('enabled', True)
        )
        
        manager = get_instruction_manager()
        instruction_id = manager.add_instruction(instruction)
        
        return jsonify({
            'code': 0,
            'message': 'Instruction created',
            'data': {'id': instruction_id}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/instructions/<instruction_id>', methods=['PUT'])
def update_instruction(instruction_id):
    """更新指令"""
    try:
        data = request.json
        manager = get_instruction_manager()
        instruction = manager.update_instruction(instruction_id, data)
        
        if not instruction:
            return jsonify({'code': 404, 'message': 'Instruction not found'}), 404
        
        return jsonify({
            'code': 0,
            'message': 'Instruction updated',
            'data': instruction.to_dict()
        })
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/instructions/<instruction_id>', methods=['DELETE'])
def delete_instruction(instruction_id):
    """删除指令"""
    manager = get_instruction_manager()
    if manager.delete_instruction(instruction_id):
        return jsonify({'code': 0, 'message': 'Instruction deleted'})
    return jsonify({'code': 404, 'message': 'Instruction not found'}), 404

@systems_bp.route('/personalities', methods=['GET'])
def list_personalities():
    """列表人格"""
    manager = get_instruction_manager()
    personalities = manager.list_personalities()
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': personalities,
        'count': len(personalities)
    })

@systems_bp.route('/personalities', methods=['POST'])
def create_personality():
    """创建人格"""
    try:
        data = request.json
        
        personality = Personality(
            name=data.get('name', ''),
            description=data.get('description', ''),
            traits=data.get('traits', {}),
            tone=data.get('tone', 'neutral'),
            speaking_style=data.get('speaking_style', ''),
            preferences=data.get('preferences', {}),
            response_length=data.get('response_length', 'medium'),
            emoji_usage=data.get('emoji_usage', True)
        )
        
        manager = get_instruction_manager()
        personality_id = manager.add_personality(personality)
        
        return jsonify({
            'code': 0,
            'message': 'Personality created',
            'data': {'id': personality_id}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/behavior-rules', methods=['GET'])
def list_behavior_rules():
    """列表行为规则"""
    manager = get_instruction_manager()
    rules = manager.list_behavior_rules()
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': rules,
        'count': len(rules)
    })

@systems_bp.route('/behavior-rules', methods=['POST'])
def create_behavior_rule():
    """创建行为规则"""
    try:
        data = request.json
        
        rule = BehaviorRule(
            name=data.get('name', ''),
            description=data.get('description', ''),
            trigger_pattern=data.get('trigger_pattern', ''),
            trigger_type=data.get('trigger_type', 'keyword'),
            action_type=data.get('action_type', 'response'),
            action_content=data.get('action_content', ''),
            parameters=data.get('parameters', {}),
            priority=data.get('priority', 0),
            weight=data.get('weight', 1.0),
            conditions=data.get('conditions', {}),
            cooldown_seconds=data.get('cooldown_seconds', 0),
            max_trigger_per_day=data.get('max_trigger_per_day'),
            enabled=data.get('enabled', True)
        )
        
        manager = get_instruction_manager()
        rule_id = manager.add_behavior_rule(rule)
        
        return jsonify({
            'code': 0,
            'message': 'Rule created',
            'data': {'id': rule_id}
        }), 201
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/system-status', methods=['GET'])
def get_system_status():
    """获取系统状态"""
    logger = get_enhanced_logger()
    scheduler = get_task_scheduler()
    mcp_manager = get_mcp_manager()
    kb_manager = get_knowledge_base_manager()
    instr_manager = get_instruction_manager()
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'logging': {
                'log_entries': len(logger.log_entries)
            },
            'task_scheduler': {
                'running': scheduler.scheduler.running,
                'total_tasks': len(scheduler.tasks),
                'pending_tasks': len([t for t in scheduler.tasks.values() if t.status == 'pending']),
                'completed_tasks': len([t for t in scheduler.tasks.values() if t.status == 'completed'])
            },
            'mcp': {
                'servers': len(mcp_manager.servers),
                'resources': len(mcp_manager.resources),
                'tools': len(mcp_manager.tools)
            },
            'knowledge_base': {
                'entries': len(kb_manager.entries),
                'glossaries': len(kb_manager.glossaries),
                'categories': len(kb_manager.get_categories())
            },
            'instructions': {
                'instructions': len(instr_manager.instructions),
                'personalities': len(instr_manager.personalities),
                'behavior_rules': len(instr_manager.behavior_rules)
            }
        }
    })
