# -*- coding: utf-8 -*-
"""MCP market and Smithery routes used by the systems API blueprint."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from html import unescape
import requests
from flask import jsonify, request

from src.utils.api_utils import BAD_REQUEST_EXCEPTIONS, get_json_body
from src.frameworks.mcp_manager import get_mcp_manager, MCPServer
from src.core.config import PROJECT_ROOT

MCP_REGISTRY_API = 'https://mcp.run/api/servers'
MCP_REGISTRY_CACHE = {'ts': 0.0, 'data': []}
MCP_REGISTRY_CACHE_TTL = 3600
MCP_SMITHERY_CACHE = {'entries': {}}
MCP_SMITHERY_CACHE_TTL = 900
MCP_SMITHERY_STATUS_CACHE = {'ts': 0.0, 'data': None}
MCP_SMITHERY_STATUS_CACHE_TTL = 15
MCP_SMITHERY_INSTALL_JOBS = {}
MCP_SMITHERY_INSTALL_JOBS_LOCK = threading.Lock()
MCP_SMITHERY_INSTALL_JOB_TTL = 3600
DIFY_CLI_INSTALL_JOBS = {}
DIFY_CLI_INSTALL_JOBS_LOCK = threading.Lock()
DIFY_CLI_INSTALL_JOB_TTL = 3600
DIFY_CLI_STATUS_CACHE = {'ts': 0.0, 'data': None}
DIFY_CLI_STATUS_CACHE_TTL = 15
EXTRA_CLI_INSTALL_JOBS = {}
EXTRA_CLI_INSTALL_JOBS_LOCK = threading.Lock()
EXTRA_CLI_INSTALL_JOB_TTL = 3600

DIFY_MARKET_CATALOG = [
    {
        'id': 'tool',
        'name': 'Tool',
        'description': 'Tool Provider, 可执行具体任务能力',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'agent-strategy',
        'name': 'Agent Strategy',
        'description': '自定义 Agent 策略，如 ReAct/ToT/CoT',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'llm',
        'name': 'LLM',
        'description': 'LLM 模型提供者插件模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'text-embedding',
        'name': 'Text Embedding',
        'description': '文本向量嵌入模型模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'rerank',
        'name': 'Rerank',
        'description': '重排序模型插件模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'tts',
        'name': 'TTS',
        'description': '文本转语音插件模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'speech2text',
        'name': 'Speech2Text',
        'description': '语音转文本插件模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'moderation',
        'name': 'Moderation',
        'description': '内容审核插件模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
    {
        'id': 'extension',
        'name': 'Extension',
        'description': '扩展 HTTP 服务能力模板',
        'source': 'dify-official',
        'official': True,
        'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli',
    },
]

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
    },
    {
        'id': 'github-copilot-http',
        'name': 'GitHub MCP',
        'description': 'GitHub 官方 MCP（HTTP）',
        'type': 'http',
        'url': 'https://api.githubcopilot.com/mcp/',
        'tags': ['github', 'official', 'remote']
    }
]


def _load_smithery_config():
    base_path = PROJECT_ROOT
    config_path = os.path.join(base_path, 'data', 'config.json')
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        market_cfg = cfg.get('mcp_market', {}) or {}
        return market_cfg.get('smithery', {}) or {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


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
        check=False,
        timeout=max(5, int(timeout or 45)),
        cwd=PROJECT_ROOT
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
    except (json.JSONDecodeError, TypeError, ValueError):
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
        except (json.JSONDecodeError, TypeError, ValueError):
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
        sid = str(
            it.get('qualifiedName')
            or it.get('id')
            or it.get('slug')
            or it.get('name')
            or ''
        ).strip()
        if not sid:
            continue

        name = _clean_smithery_text(it.get('name') or sid) or sid
        description = _clean_smithery_text(it.get('description') or '')
        author = _clean_smithery_text(
            it.get('author') or it.get('owner') or it.get('namespace') or ''
        )
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
            'type': _clean_smithery_text(
                it.get('type') or it.get('protocol') or 'remote'
            ) or 'remote',
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


def _start_smithery_install_job():
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('未找到 npm，请先安装 Node.js 20+')

    base_path = PROJECT_ROOT
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

            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                cwd=base_path,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            ) as process:
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
        except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, TypeError) as exc:
            _smithery_install_job_append(job_id, f'安装异常: {exc}')
            _smithery_install_job_finish(job_id, 'error', str(exc), -1)
        finally:
            try:
                if process and process.stdout:
                    process.stdout.close()
            except OSError:
                pass

    threading.Thread(target=_runner, daemon=True).start()
    return _smithery_install_job_snapshot(job_id)


def _fetch_official_mcp_registry(limit: int = 30, registry_url: str = None):
    limit = max(1, min(200, int(limit or 30)))
    api_url = registry_url or MCP_REGISTRY_API

    now = time.time()
    if (
        MCP_REGISTRY_CACHE.get('ts', 0) + MCP_REGISTRY_CACHE_TTL > now
        and MCP_REGISTRY_CACHE.get('data')
    ):
        return MCP_REGISTRY_CACHE['data'][:limit]

    items = []
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        servers = (
            data.get('servers', [])
            or data.get('data', [])
            or (data if isinstance(data, list) else [])
        )

        for srv in servers:
            item = {
                'id': str(srv.get('id') or srv.get('name', '').lower().replace(' ', '-')),
                'name': str(srv.get('name') or 'MCP Server'),
                'description': str(srv.get('description') or ''),
                'author': str(srv.get('author') or srv.get('maintainer', '')),
                'license': str(srv.get('license', '')),
                'version': str(srv.get('version', '')),
                'keywords': list(srv.get('keywords', [])) or list(srv.get('tags', [])) or [],
                'homepage': str(srv.get('homepage') or srv.get('url', '')),
                'repository': str(srv.get('repository') or srv.get('repo', '')),
                'documentation': str(srv.get('documentation') or srv.get('docs', '')),
                'registry_url': str(
                    srv.get('registry_url', f'https://mcp.run/servers/{srv.get("id", "")}')
                ),
                'protocol_version': str(srv.get('protocol_version', '1.0')),
                'implementation': str(srv.get('implementation', '')),
                'type': str(srv.get('protocol', srv.get('type', 'stdio'))),
                'user_config_required': True,
                'source': 'mcp-registry',
                'installable': True,
            }
            items.append(item)

        if items:
            MCP_REGISTRY_CACHE['ts'] = now
            MCP_REGISTRY_CACHE['data'] = items
            return items[:limit]
    except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError):
        pass

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
    return _fetch_official_mcp_registry(limit)


def _parse_mcp_command_from_page(html: str):
    text = unescape(str(html or ''))

    cmd_match = re.search(r'"command"\s*:\s*"([^"]+)"', text, flags=re.IGNORECASE)
    args_match = re.search(r'"args"\s*:\s*\[(.*?)\]', text, flags=re.IGNORECASE | re.DOTALL)
    if cmd_match:
        command = cmd_match.group(1).strip()
        args = []
        if args_match:
            raw_args = args_match.group(1)
            args = re.findall(r'"([^"]+)"', raw_args)
        return {'type': 'stdio', 'command': command, 'args': args}

    line_match = re.search(r'(npx|uvx|python3?|node)\s+([^\n<`]+)', text, flags=re.IGNORECASE)
    if line_match:
        line = f"{line_match.group(1)} {line_match.group(2)}".strip()
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if parts:
            return {'type': 'stdio', 'command': parts[0], 'args': parts[1:]}

    url_match = re.search(r'https?://[^\s"\'<>]+', text)
    if url_match:
        return {'type': 'http', 'url': url_match.group(0).strip()}

    return None


def _get_market_paging_args():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 30, type=int)
    query = str(request.args.get('query', '') or '').strip().lower()
    page = max(1, int(page or 1))
    page_size = max(5, min(100, int(page_size or 30)))
    return page, page_size, query


def _run_smithery_search_attempts(attempts):
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
            if line:
                text_rows.append(line)
        if text_rows:
            break

    return payload, text_rows, errors[:5]


def _rows_to_smithery_items(query, text_rows):
    items = []
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
    return items


def _query_smithery_market(page, page_size, query, cli):
    effective_query = query or 'github'
    attempts = [
        ['--json', 'mcp', 'search', effective_query, '--page', str(page)],
        ['mcp', 'search', effective_query, '--page', str(page)],
        ['--json', 'mcp', 'search', effective_query],
        ['mcp', 'search', effective_query],
    ]

    payload, text_rows, errors = _run_smithery_search_attempts(attempts)

    items = _normalize_smithery_mcp_items(payload) if payload is not None else []
    has_more = bool((payload or {}).get('hasMore')) if isinstance(payload, dict) else False
    total = (page - 1) * page_size + len(items) + (1 if has_more else 0)

    if not items and text_rows:
        items = _rows_to_smithery_items(query, text_rows)
        has_more = False
        total = (page - 1) * page_size + len(items)

    _mcp_smithery_cache_set(
        _mcp_smithery_cache_key(query, f'{cli}|p{page}|ps{page_size}'),
        items,
        {
            'mode': 'smithery_cli',
            'errors': errors,
            'cli': cli,
            'cached': False,
            'has_more': has_more,
            'total': total,
            'effective_query': effective_query,
        }
    )

    return {
        'items': items,
        'has_more': has_more,
        'total': total,
        'effective_query': effective_query,
        'errors': errors,
    }


def _register_market_catalog_route(systems_bp):
    @systems_bp.route('/mcp/market', methods=['GET'])
    def list_mcp_market_catalog():
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': MCP_MARKET_CATALOG,
            'count': len(MCP_MARKET_CATALOG)
        })


def _register_market_install_route(systems_bp):
    @systems_bp.route('/mcp/market/install', methods=['POST'])
    def install_mcp_market_item():
        try:
            data = get_json_body()
            item_id = str(data.get('id', '')).strip()
            if not item_id:
                return jsonify({'code': 400, 'message': 'id is required'}), 400

            market_item = next((x for x in MCP_MARKET_CATALOG if x.get('id') == item_id), None)
            if market_item is None:
                return jsonify({'code': 404, 'message': 'Market item not found'}), 404

            manager = get_mcp_manager()
            servers = manager.list_servers(enabled_only=False)
            for s in servers:
                current_name = (s.get('name') or '').strip().lower()
                target_name = (market_item.get('name') or '').strip().lower()
                if current_name == target_name:
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
                capabilities={
                    'tags': list(market_item.get('tags', []) or []),
                    'source': 'market',
                }
            )

            if server.type in ('http', 'sse'):
                server.url = market_item.get('url', '')

            server_id = manager.add_server(server)
            return jsonify({
                'code': 0,
                'message': 'Server installed',
                'data': {'id': server_id, 'name': server.name, 'exists': False}
            }), 201
        except BAD_REQUEST_EXCEPTIONS as e:
            return jsonify({'code': 400, 'message': str(e)}), 400


def _register_smithery_search_routes(systems_bp):
    @systems_bp.route('/mcp/market/smithery/search', methods=['GET'])
    @systems_bp.route('/mcp/market/registry', methods=['GET'])
    @systems_bp.route('/mcp/market/mcpmarket', methods=['GET'])
    def list_mcpmarket_items():
        try:
            page, page_size, query = _get_market_paging_args()

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

            result = _query_smithery_market(page, page_size, query, cli)
            items = result['items']
            has_more = bool(result['has_more'])
            total = int(result['total'])
            effective_query = str(result['effective_query'])
            errors = list(result['errors'])

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
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
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


def _handle_smithery_install_request():
    try:
        data = get_json_body()
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
            return jsonify(
                {'code': 500, 'message': 'Smithery MCP 接入失败', 'details': errors}
            ), 500

        return jsonify({
            'code': 0,
            'message': f'Smithery MCP 接入完成: {target_ref}',
            'data': {
                'target': target_ref,
                'stdout': (ok_result.get('stdout') or '')[-1200:],
                'cli': _find_smithery_cli(),
            }
        })
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400


def _register_smithery_alias_routes(systems_bp):
    @systems_bp.route('/mcp/market/registry/install', methods=['POST'])
    @systems_bp.route('/mcp/market/mcpmarket/install', methods=['POST'])
    def install_mcpmarket_item_from_url():
        return _handle_smithery_install_request()


def _register_smithery_status_routes(systems_bp):
    @systems_bp.route('/mcp/market/smithery/status', methods=['GET'])
    def mcp_smithery_status():
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
                except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError):
                    continue
            data = {'installed': installed, 'cli': cli, 'version': version, 'mode': mode}
            MCP_SMITHERY_STATUS_CACHE['ts'] = now
            MCP_SMITHERY_STATUS_CACHE['data'] = dict(data)
            return jsonify({'code': 0, 'message': 'success', 'data': data})
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500


def _register_smithery_cli_install_routes(systems_bp):
    @systems_bp.route('/mcp/market/smithery/cli/install', methods=['POST'])
    def install_mcp_smithery_cli():
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
                    'status_url': (
                        f"/api/systems/mcp/market/smithery/cli/install/jobs/{job.get('job_id')}"
                    ),
                }
            })
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500


def _register_smithery_install_job_routes(systems_bp):
    @systems_bp.route('/mcp/market/smithery/cli/install/jobs/<job_id>', methods=['GET'])
    def mcp_smithery_install_job(job_id):
        try:
            job = _smithery_install_job_snapshot(str(job_id).strip())
            if not job:
                return jsonify({'code': 404, 'message': 'job not found'}), 404
            return jsonify({'code': 0, 'message': 'success', 'data': job})
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500


def _register_smithery_install_routes(systems_bp):
    @systems_bp.route('/mcp/market/smithery/install', methods=['POST'])
    def install_mcp_smithery_item():
        return _handle_smithery_install_request()


def _register_dify_market_routes(systems_bp):
    def _get_extra_cli_specs():
        return {
            'kimi': {
                'label': 'Kimi CLI',
                'command': 'kimi',
                'docs_url': 'https://www.kimi.com/code/docs/en/kimi-cli/guides/getting-started.html',
                'official_guide_only': True,
                'guide_commands': [
                    '# Windows (PowerShell)',
                    'Invoke-RestMethod https://code.kimi.com/install.ps1 | Invoke-Expression',
                    'kimi --version',
                ],
            },
            'minimax': {
                'label': 'MiniMax Codex CLI',
                'command': 'codex',
                'docs_url': 'https://platform.minimaxi.com/docs/token-plan/codex-cli',
                'official_guide_only': True,
                'guide_commands': [
                    '# 建议版本',
                    'npm i -g @openai/codex@0.57.0',
                    '# 配置 ~/.codex/config.toml 的 MiniMax provider 与 profile',
                    '# 设置 API Key 后运行',
                    'codex --profile m27',
                ],
            }
        }

    def _find_extra_cli_binary(cli_name: str):
        specs = _get_extra_cli_specs()
        spec = specs.get(str(cli_name or '').strip().lower())
        if not spec:
            return ''
        return str(shutil.which(str(spec.get('command') or '').strip()) or '').strip()

    def _extra_cli_job_prune_locked(now=None):
        now = now or time.time()
        stale_ids = []
        for job_id, job in list(EXTRA_CLI_INSTALL_JOBS.items()):
            updated_at = float(job.get('updated_at') or job.get('created_at') or 0.0)
            if job.get('status') in ('running', 'queued'):
                continue
            if (now - updated_at) > EXTRA_CLI_INSTALL_JOB_TTL:
                stale_ids.append(job_id)
        for job_id in stale_ids:
            EXTRA_CLI_INSTALL_JOBS.pop(job_id, None)

    def _extra_cli_job_snapshot(job_id: str):
        with EXTRA_CLI_INSTALL_JOBS_LOCK:
            _extra_cli_job_prune_locked()
            job = EXTRA_CLI_INSTALL_JOBS.get(job_id)
            if not job:
                return None
            return {
                'job_id': job.get('job_id', job_id),
                'cli_name': job.get('cli_name', ''),
                'cli_label': job.get('cli_label', ''),
                'status': job.get('status', 'queued'),
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at'),
                'command_display': job.get('command_display', ''),
                'returncode': job.get('returncode'),
                'message': job.get('message', ''),
                'logs': list(job.get('logs') or []),
                'installed': bool(job.get('status') == 'success'),
            }

    def _extra_cli_job_append(job_id: str, line: str):
        text = str(line or '').replace('\r', '').rstrip('\n')
        if not text.strip():
            return
        now = time.time()
        with EXTRA_CLI_INSTALL_JOBS_LOCK:
            job = EXTRA_CLI_INSTALL_JOBS.get(job_id)
            if not job:
                return
            logs = list(job.get('logs') or [])
            logs.append(text)
            if len(logs) > 400:
                logs = logs[-400:]
            job['logs'] = logs
            job['updated_at'] = now

    def _extra_cli_job_finish(job_id: str, status: str, message: str, returncode: int = None):
        now = time.time()
        with EXTRA_CLI_INSTALL_JOBS_LOCK:
            job = EXTRA_CLI_INSTALL_JOBS.get(job_id)
            if not job:
                return
            job['status'] = status
            job['message'] = str(message or '')
            job['updated_at'] = now
            if returncode is not None:
                job['returncode'] = int(returncode)

    def _resolve_install_cmd(cmd):
        if not cmd:
            return None
        first = str(cmd[0] or '').strip()
        if not first:
            return None
        if os.path.isabs(first) and os.path.exists(first):
            return list(cmd)
        if first in ('python', 'python3') and str(sys.executable or '').strip():
            out = list(cmd)
            out[0] = str(sys.executable)
            return out
        found = shutil.which(first)
        if not found:
            return None
        out = list(cmd)
        out[0] = found
        return out

    def _start_extra_cli_install_job(cli_name: str):
        name = str(cli_name or '').strip().lower()
        specs = _get_extra_cli_specs()
        spec = specs.get(name)
        if not spec:
            raise RuntimeError('不支持的 CLI 类型')

        if bool(spec.get('official_guide_only')):
            raise RuntimeError(f"{spec.get('label') or name} 当前仅支持官方文档引导安装")

        attempts = []
        for cmd in list(spec.get('install_attempts') or []):
            resolved = _resolve_install_cmd(cmd)
            if resolved:
                attempts.append(resolved)

        if not attempts:
            raise RuntimeError('未找到可用安装器（npm/pipx/python），请手动安装')

        label = str(spec.get('label') or name)
        docs_url = str(spec.get('docs_url') or '')
        job_id = uuid.uuid4().hex
        now = time.time()
        base_path = PROJECT_ROOT

        with EXTRA_CLI_INSTALL_JOBS_LOCK:
            _extra_cli_job_prune_locked(now)
            EXTRA_CLI_INSTALL_JOBS[job_id] = {
                'job_id': job_id,
                'cli_name': name,
                'cli_label': label,
                'status': 'queued',
                'created_at': now,
                'updated_at': now,
                'command_display': ' / '.join([' '.join(x) for x in attempts]),
                'returncode': None,
                'message': f'准备启动 {label} 安装',
                'logs': [
                    f'准备安装 {label}',
                    f'官方文档: {docs_url}',
                ],
            }

        def _runner():
            process = None
            try:
                with EXTRA_CLI_INSTALL_JOBS_LOCK:
                    job = EXTRA_CLI_INSTALL_JOBS.get(job_id)
                    if job:
                        job['status'] = 'running'
                        job['updated_at'] = time.time()

                _extra_cli_job_append(job_id, f'工作目录: {base_path}')

                for idx, cmd in enumerate(attempts, start=1):
                    cmd_display = ' '.join([str(x) for x in cmd])
                    _extra_cli_job_append(job_id, f'[{idx}/{len(attempts)}] 尝试安装命令: {cmd_display}')
                    with subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        cwd=base_path,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    ) as process:
                        if process.stdout:
                            for raw_line in iter(process.stdout.readline, ''):
                                if raw_line == '':
                                    break
                                _extra_cli_job_append(job_id, raw_line.strip('\n'))
                        returncode = process.wait()

                    if returncode == 0:
                        binary = _find_extra_cli_binary(name)
                        if binary:
                            _extra_cli_job_append(job_id, f'检测到 CLI: {binary}')
                            _extra_cli_job_finish(job_id, 'success', f'{label} 安装完成', 0)
                            return
                        _extra_cli_job_append(job_id, '安装命令成功但未检测到可执行命令，继续尝试后续方案')
                    else:
                        _extra_cli_job_append(job_id, f'命令退出码: {returncode}')

                _extra_cli_job_finish(job_id, 'error', f'{label} 安装失败，请查看日志并按官方文档手动安装', -1)
            except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, TypeError) as exc:
                _extra_cli_job_append(job_id, f'安装异常: {exc}')
                _extra_cli_job_finish(job_id, 'error', str(exc), -1)
            finally:
                try:
                    if process and process.stdout:
                        process.stdout.close()
                except OSError:
                    pass

        threading.Thread(target=_runner, daemon=True).start()
        return _extra_cli_job_snapshot(job_id)

    def _find_dify_cli():
        return str(shutil.which('dify') or '').strip()

    def _dify_install_job_prune_locked(now=None):
        now = now or time.time()
        stale_ids = []
        for job_id, job in list(DIFY_CLI_INSTALL_JOBS.items()):
            updated_at = float(job.get('updated_at') or job.get('created_at') or 0.0)
            if job.get('status') in ('running', 'queued'):
                continue
            if (now - updated_at) > DIFY_CLI_INSTALL_JOB_TTL:
                stale_ids.append(job_id)
        for job_id in stale_ids:
            DIFY_CLI_INSTALL_JOBS.pop(job_id, None)

    def _dify_install_job_snapshot(job_id: str):
        with DIFY_CLI_INSTALL_JOBS_LOCK:
            _dify_install_job_prune_locked()
            job = DIFY_CLI_INSTALL_JOBS.get(job_id)
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

    def _dify_install_job_append(job_id: str, line: str):
        text = str(line or '').replace('\r', '').rstrip('\n')
        if not text.strip():
            return
        now = time.time()
        with DIFY_CLI_INSTALL_JOBS_LOCK:
            job = DIFY_CLI_INSTALL_JOBS.get(job_id)
            if not job:
                return
            logs = list(job.get('logs') or [])
            logs.append(text)
            if len(logs) > 400:
                logs = logs[-400:]
            job['logs'] = logs
            job['updated_at'] = now

    def _dify_install_job_finish(job_id: str, status: str, message: str, returncode: int = None):
        now = time.time()
        with DIFY_CLI_INSTALL_JOBS_LOCK:
            job = DIFY_CLI_INSTALL_JOBS.get(job_id)
            if not job:
                return
            job['status'] = status
            job['message'] = str(message or '')
            job['updated_at'] = now
            if returncode is not None:
                job['returncode'] = int(returncode)

    def _get_dify_install_plan():
        docs_url = 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli'
        brew = shutil.which('brew')

        if brew:
            return {
                'commands': [
                    [brew, 'tap', 'langgenius/dify'],
                    [brew, 'install', 'dify'],
                ],
                'display': 'brew tap langgenius/dify && brew install dify',
                'mode': 'brew',
                'docs_url': docs_url,
            }

        raise RuntimeError('当前环境未检测到 Homebrew。请按 Dify 官方文档手动安装 CLI。')

    def _start_dify_install_job():
        plan = _get_dify_install_plan()
        commands = list(plan.get('commands') or [])
        command_display = str(plan.get('display') or '').strip()
        mode = str(plan.get('mode') or 'manual')
        docs_url = str(plan.get('docs_url') or '')

        base_path = PROJECT_ROOT
        job_id = uuid.uuid4().hex
        now = time.time()

        with DIFY_CLI_INSTALL_JOBS_LOCK:
            _dify_install_job_prune_locked(now)
            DIFY_CLI_INSTALL_JOBS[job_id] = {
                'job_id': job_id,
                'status': 'queued',
                'created_at': now,
                'updated_at': now,
                'command_display': command_display,
                'returncode': None,
                'message': '准备启动 Dify CLI 安装',
                'logs': [
                    f'准备安装 Dify CLI（模式: {mode}）',
                    f'命令: {command_display}',
                    f'官方文档: {docs_url}',
                ],
            }

        def _runner():
            process = None
            try:
                with DIFY_CLI_INSTALL_JOBS_LOCK:
                    job = DIFY_CLI_INSTALL_JOBS.get(job_id)
                    if job:
                        job['status'] = 'running'
                        job['updated_at'] = time.time()

                _dify_install_job_append(job_id, f'工作目录: {base_path}')

                for idx, cmd in enumerate(commands, start=1):
                    cmd_display = ' '.join([str(x) for x in cmd])
                    _dify_install_job_append(job_id, f'[{idx}/{len(commands)}] 执行: {cmd_display}')

                    with subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        cwd=base_path,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    ) as process:
                        if process.stdout:
                            for raw_line in iter(process.stdout.readline, ''):
                                if raw_line == '':
                                    break
                                _dify_install_job_append(job_id, raw_line.strip('\n'))

                        returncode = process.wait()
                    if returncode != 0:
                        _dify_install_job_append(job_id, f'命令退出码: {returncode}')
                        _dify_install_job_finish(job_id, 'error', 'Dify CLI 安装失败，请查看日志', returncode)
                        return

                cli = _find_dify_cli()
                _dify_install_job_append(job_id, f'检测到 CLI: {cli or "未检测到"}')
                if cli:
                    _dify_install_job_finish(job_id, 'success', 'Dify CLI 安装完成', 0)
                else:
                    _dify_install_job_finish(job_id, 'error', '安装执行完毕，但未检测到 dify 命令', -1)
            except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, TypeError) as exc:
                _dify_install_job_append(job_id, f'安装异常: {exc}')
                _dify_install_job_finish(job_id, 'error', str(exc), -1)
            finally:
                try:
                    if process and process.stdout:
                        process.stdout.close()
                except OSError:
                    pass

        threading.Thread(target=_runner, daemon=True).start()
        return _dify_install_job_snapshot(job_id)

    @systems_bp.route('/dify/market/search', methods=['GET'])
    def list_dify_market_items():
        query = str(request.args.get('query', '') or '').strip().lower()
        page = max(1, int(request.args.get('page', 1) or 1))
        page_size = max(5, min(100, int(request.args.get('page_size', 24) or 24)))

        items = list(DIFY_MARKET_CATALOG)
        if query:
            items = [
                x for x in items
                if query in str(x.get('id', '')).lower()
                or query in str(x.get('name', '')).lower()
                or query in str(x.get('description', '')).lower()
            ]

        start = (page - 1) * page_size
        end = start + page_size
        paged = items[start:end]
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': paged,
            'count': len(paged),
            'page': page,
            'page_size': page_size,
            'total': len(items),
            'has_more': end < len(items),
            'query': query,
            'mode': 'official_docs_only'
        })

    @systems_bp.route('/dify/market/cli/status', methods=['GET'])
    def dify_cli_status():
        now = time.time()
        cached_data = DIFY_CLI_STATUS_CACHE.get('data')
        cached_ts = float(DIFY_CLI_STATUS_CACHE.get('ts') or 0.0)
        if cached_data is not None and (now - cached_ts) <= DIFY_CLI_STATUS_CACHE_TTL:
            return jsonify({'code': 0, 'message': 'success', 'data': dict(cached_data)})

        dify_bin = shutil.which('dify')
        if not dify_bin:
            data = {
                'installed': False,
                'cli': '',
                'version': '',
                'mode': 'missing',
                'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli'
            }
            DIFY_CLI_STATUS_CACHE['ts'] = now
            DIFY_CLI_STATUS_CACHE['data'] = dict(data)
            return jsonify({
                'code': 0,
                'message': 'success',
                'data': data
            })

        version = ''
        try:
            proc = subprocess.run(
                [dify_bin, '--version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=3,
                check=False,
            )
            version = ((proc.stdout or proc.stderr or '').strip().splitlines() or [''])[0]
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError):
            version = ''

        data = {
            'installed': True,
            'cli': dify_bin,
            'version': version,
            'mode': 'global',
            'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli'
        }
        DIFY_CLI_STATUS_CACHE['ts'] = now
        DIFY_CLI_STATUS_CACHE['data'] = dict(data)

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': data
        })

    @systems_bp.route('/dify/market/cli/install', methods=['POST'])
    def dify_cli_install_guide():
        data = get_json_body()
        auto_install = bool(data.get('auto_install'))
        docs_url = 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli'

        if auto_install:
            try:
                job = _start_dify_install_job()
                return jsonify({
                    'code': 0,
                    'message': 'Dify CLI 一键安装已在后台启动',
                    'data': {
                        'mode': 'one_click_install',
                        'docs_url': docs_url,
                        'installed': False,
                        'job_id': job.get('job_id'),
                        'status': job.get('status', 'queued'),
                        'command': job.get('command_display', ''),
                        'logs': list(job.get('logs') or []),
                        'status_url': (
                            f"/api/systems/dify/market/cli/install/jobs/{job.get('job_id')}"
                        ),
                    }
                })
            except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
                return jsonify({'code': 500, 'message': str(e)}), 500

        return jsonify({
            'code': 0,
            'message': 'Dify CLI 安装指引',
            'data': {
                'mode': 'official_guide',
                'docs_url': docs_url,
                'commands': [
                    'brew tap langgenius/dify',
                    'brew install dify',
                    'dify version'
                ],
                'note': '可点击一键安装自动尝试安装；若环境不支持，将按官方文档手动安装。'
            }
        })

    @systems_bp.route('/dify/market/cli/install/jobs/<job_id>', methods=['GET'])
    def dify_cli_install_job(job_id):
        try:
            job = _dify_install_job_snapshot(str(job_id).strip())
            if not job:
                return jsonify({'code': 404, 'message': 'job not found'}), 404
            return jsonify({'code': 0, 'message': 'success', 'data': job})
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500

    @systems_bp.route('/dify/market/install', methods=['POST'])
    def dify_market_install_template():
        data = get_json_body()
        template_id = str(data.get('id') or data.get('template') or '').strip().lower()
        item = next((x for x in DIFY_MARKET_CATALOG if str(x.get('id') or '').lower() == template_id), None)
        if not item:
            return jsonify({'code': 404, 'message': 'Template not found'}), 404

        return jsonify({
            'code': 0,
            'message': f'已选择官方模板: {item.get("name")}',
            'data': {
                'template': item,
                'mode': 'official_docs_only',
                'next_steps': [
                    'dify plugin init',
                    f'在交互式向导中选择模板: {item.get("id")}',
                    'cp .env.example .env',
                    'pip install -r requirements.txt',
                    'python -m main'
                ],
                'docs_url': 'https://docs.dify.ai/zh/develop-plugin/getting-started/cli'
            }
        })

    @systems_bp.route('/cli/<cli_name>/status', methods=['GET'])
    @systems_bp.route('/market/cli/<cli_name>/status', methods=['GET'])
    def extra_cli_status(cli_name):
        name = str(cli_name or '').strip().lower()
        specs = _get_extra_cli_specs()
        spec = specs.get(name)
        if not spec:
            return jsonify({'code': 404, 'message': 'Unsupported CLI'}), 404

        cli_bin = _find_extra_cli_binary(name)
        if not cli_bin:
            return jsonify({
                'code': 0,
                'message': 'success',
                'data': {
                    'installed': False,
                    'cli': '',
                    'version': '',
                    'mode': 'missing',
                    'label': spec.get('label'),
                    'docs_url': spec.get('docs_url')
                }
            })

        version = ''
        try:
            proc = subprocess.run(
                [cli_bin, '--version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
                check=False,
            )
            version = ((proc.stdout or proc.stderr or '').strip().splitlines() or [''])[0]
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError):
            version = ''

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'installed': True,
                'cli': cli_bin,
                'version': version,
                'mode': 'global',
                'label': spec.get('label'),
                'docs_url': spec.get('docs_url')
            }
        })

    @systems_bp.route('/cli/<cli_name>/install', methods=['POST'])
    @systems_bp.route('/market/cli/<cli_name>/install', methods=['POST'])
    def extra_cli_install(cli_name):
        name = str(cli_name or '').strip().lower()
        specs = _get_extra_cli_specs()
        spec = specs.get(name)
        if not spec:
            return jsonify({'code': 404, 'message': 'Unsupported CLI'}), 404

        data = get_json_body()
        auto_install = bool(data.get('auto_install'))
        if (not auto_install) or bool(spec.get('official_guide_only')):
            return jsonify({
                'code': 0,
                'message': f"{spec.get('label')} 安装指引",
                'data': {
                    'mode': 'official_guide',
                    'docs_url': spec.get('docs_url'),
                    'commands': list(spec.get('guide_commands') or []),
                    'note': '请严格参考官方文档安装。'
                }
            })

        try:
            job = _start_extra_cli_install_job(name)
            return jsonify({
                'code': 0,
                'message': f"{spec.get('label')} 一键安装已在后台启动",
                'data': {
                    'mode': 'one_click_install',
                    'docs_url': spec.get('docs_url'),
                    'job_id': job.get('job_id'),
                    'status': job.get('status', 'queued'),
                    'command': job.get('command_display', ''),
                    'logs': list(job.get('logs') or []),
                    'status_url': f"/api/systems/cli/{name}/install/jobs/{job.get('job_id')}",
                }
            })
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500

    @systems_bp.route('/cli/<cli_name>/install/jobs/<job_id>', methods=['GET'])
    @systems_bp.route('/market/cli/<cli_name>/install/jobs/<job_id>', methods=['GET'])
    def extra_cli_install_job(cli_name, job_id):
        name = str(cli_name or '').strip().lower()
        specs = _get_extra_cli_specs()
        if name not in specs:
            return jsonify({'code': 404, 'message': 'Unsupported CLI'}), 404
        try:
            job = _extra_cli_job_snapshot(str(job_id).strip())
            if not job or str(job.get('cli_name') or '').strip().lower() != name:
                return jsonify({'code': 404, 'message': 'job not found'}), 404
            return jsonify({'code': 0, 'message': 'success', 'data': job})
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as e:
            return jsonify({'code': 500, 'message': str(e)}), 500


def register_market_routes(systems_bp):
    """Register all MCP market and Smithery routes on the provided blueprint."""
    _register_market_catalog_route(systems_bp)
    _register_market_install_route(systems_bp)
    _register_smithery_search_routes(systems_bp)
    _register_smithery_alias_routes(systems_bp)
    _register_smithery_status_routes(systems_bp)
    _register_smithery_cli_install_routes(systems_bp)
    _register_smithery_install_job_routes(systems_bp)
    _register_smithery_install_routes(systems_bp)
    _register_dify_market_routes(systems_bp)

    return systems_bp
