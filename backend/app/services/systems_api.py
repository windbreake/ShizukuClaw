# -*- coding: utf-8 -*-
"""
系统集成模块 - 整合所有新系统的API接口
"""

from flask import Blueprint, jsonify, request
import json

# 导入各个系统
from app.utils.enhanced_logging import get_enhanced_logger
from app.agent.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
from app.frameworks.mcp_manager import get_mcp_manager, MCPServer
from app.frameworks.knowledge_base_manager import get_knowledge_base_manager, KnowledgeEntry, EntryType
from app.frameworks.instruction_manager import (
    get_instruction_manager, AgentInstruction, Personality,
    BehaviorRule, InstructionType
)
from app.utils.api_utils import BAD_REQUEST_EXCEPTIONS, get_json_body
from app.services.systems_market_api import register_market_routes

try:
    from app.tools.benchmark_evaluator import GitHubBenchmarkEvaluator, BenchmarkRunError
    BENCHMARK_AVAILABLE = True
    BENCHMARK_IMPORT_ERROR = ''
except ImportError as _benchmark_import_error:
    GitHubBenchmarkEvaluator = None

    class BenchmarkRunError(RuntimeError):
        pass

    BENCHMARK_AVAILABLE = False
    BENCHMARK_IMPORT_ERROR = str(_benchmark_import_error)

# 创建蓝图
systems_bp = Blueprint('systems', __name__, url_prefix='/api/systems')
register_market_routes(systems_bp)

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
        'count': len(tasks),
        'scheduler_available': bool(getattr(scheduler, 'scheduler_available', True))
    })

@systems_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    try:
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
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
        data = get_json_body()
        scheduler = get_task_scheduler()
        task = scheduler.update_task(task_id, data)

        if not task:
            return jsonify({'code': 404, 'message': 'Task not found'}), 404

        return jsonify({
            'code': 0,
            'message': 'Task updated',
            'data': task.to_dict()
        })
    except BAD_REQUEST_EXCEPTIONS as e:
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
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
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
        data = get_json_body()
        manager = get_mcp_manager()
        server = manager.update_server(server_id, data)

        if not server:
            return jsonify({'code': 404, 'message': 'Server not found'}), 404

        return jsonify({
            'code': 0,
            'message': 'Server updated',
            'data': server.to_dict()
        })
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/mcp/servers/<server_id>', methods=['DELETE'])
def delete_mcp_server(server_id):
    """删除MCP服务器"""
    manager = get_mcp_manager()
    if manager.delete_server(server_id):
        return jsonify({'code': 0, 'message': 'Server deleted'})
    return jsonify({'code': 404, 'message': 'Server not found'}), 404


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
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400


@systems_bp.route('/knowledge/import', methods=['POST'])
def import_knowledge_entries():
    """批量导入知识库条目"""
    try:
        data = get_json_body()
        dedup_mode = str(data.get('dedup_mode') or 'title_content').strip().lower()
        if dedup_mode not in {'none', 'title', 'title_content'}:
            dedup_mode = 'title_content'
        raw_entries = data.get('entries')
        if raw_entries is None:
            raw_text = str(data.get('payload') or '').strip()
            if raw_text:
                raw_entries = json.loads(raw_text)

        if not isinstance(raw_entries, list):
            return jsonify({'code': 400, 'message': 'entries must be a list'}), 400

        manager = get_knowledge_base_manager()
        imported = 0
        skipped = 0
        dedup_skipped = 0
        ids = []
        errors = []

        existing_entries = manager.list_entries(enabled_only=False)
        existing_title_set = set()
        existing_title_content_set = set()
        for ex in existing_entries:
            title_key = str(ex.get('title') or '').strip().lower()
            content_key = str(ex.get('content') or '').strip().lower()
            if title_key:
                existing_title_set.add(title_key)
            if title_key or content_key:
                existing_title_content_set.add(f'{title_key}||{content_key}')

        for idx, item in enumerate(raw_entries):
            if not isinstance(item, dict):
                skipped += 1
                errors.append(f'#{idx + 1}: item is not an object')
                continue

            title = str(item.get('title') or '').strip()
            content = str(item.get('content') or '').strip()
            if not title or not content:
                skipped += 1
                errors.append(f'#{idx + 1}: title/content is required')
                continue

            title_key = title.lower()
            pair_key = f'{title_key}||{content.lower()}'
            if dedup_mode == 'title' and title_key in existing_title_set:
                skipped += 1
                dedup_skipped += 1
                continue
            if dedup_mode == 'title_content' and pair_key in existing_title_content_set:
                skipped += 1
                dedup_skipped += 1
                continue

            tags = item.get('tags') or []
            if isinstance(tags, str):
                tags = [x.strip() for x in tags.split(',') if x.strip()]
            if not isinstance(tags, list):
                tags = []

            keywords = item.get('keywords') or []
            if isinstance(keywords, str):
                keywords = [x.strip() for x in keywords.split(',') if x.strip()]
            if not isinstance(keywords, list):
                keywords = []

            entry = KnowledgeEntry(
                title=title,
                content=content,
                entry_type=str(item.get('type') or item.get('entry_type') or EntryType.KNOWLEDGE.value),
                category=str(item.get('category') or ''),
                tags=[str(x) for x in tags],
                keywords=[str(x) for x in keywords],
                priority=int(item.get('priority', 0) or 0),
                weight=float(item.get('weight', 1.0) or 1.0),
                author=str(item.get('author') or ''),
                source=str(item.get('source') or 'import')
            )
            entry_id = manager.add_entry(entry)
            ids.append(entry_id)
            imported += 1
            existing_title_set.add(title_key)
            existing_title_content_set.add(pair_key)

        return jsonify({
            'code': 0,
            'message': 'import completed',
            'data': {
                'imported': imported,
                'skipped': skipped,
                'dedup_mode': dedup_mode,
                'dedup_skipped': dedup_skipped,
                'ids': ids,
                'errors': errors[:20]
            }
        })
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except (TypeError, ValueError, json.JSONDecodeError) as e:
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
        data = get_json_body()
        manager = get_knowledge_base_manager()
        entry = manager.update_entry(entry_id, data)

        if not entry:
            return jsonify({'code': 404, 'message': 'Entry not found'}), 404

        return jsonify({
            'code': 0,
            'message': 'Entry updated',
            'data': entry.to_dict()
        })
    except BAD_REQUEST_EXCEPTIONS as e:
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
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400

@systems_bp.route('/instructions/<instruction_id>', methods=['PUT'])
def update_instruction(instruction_id):
    """更新指令"""
    try:
        data = get_json_body()
        manager = get_instruction_manager()
        instruction = manager.update_instruction(instruction_id, data)

        if not instruction:
            return jsonify({'code': 404, 'message': 'Instruction not found'}), 404

        return jsonify({
            'code': 0,
            'message': 'Instruction updated',
            'data': instruction.to_dict()
        })
    except BAD_REQUEST_EXCEPTIONS as e:
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
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400


@systems_bp.route('/personalities/<personality_id>', methods=['DELETE'])
def delete_personality(personality_id):
    """删除人格"""
    manager = get_instruction_manager()
    if manager.delete_personality(personality_id):
        return jsonify({'code': 0, 'message': 'Personality deleted'})
    return jsonify({'code': 404, 'message': 'Personality not found'}), 404

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
        data = get_json_body()

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
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400


@systems_bp.route('/benchmark/targets', methods=['GET'])
def list_benchmark_targets():
    """列出可执行的跑分目标。"""
    if not BENCHMARK_AVAILABLE:
        return jsonify({
            'code': 503,
            'message': 'benchmark module unavailable',
            'data': [],
            'count': 0,
            'error': BENCHMARK_IMPORT_ERROR,
        }), 503

    targets = GitHubBenchmarkEvaluator().list_targets()
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': targets,
        'count': len(targets)
    })


@systems_bp.route('/benchmark/run', methods=['POST'])
def run_benchmark():
    """执行基于 GitHub 开源工具 pytest-benchmark 的性能评估。"""
    if not BENCHMARK_AVAILABLE:
        return jsonify({
            'code': 503,
            'message': 'benchmark module unavailable',
            'error': BENCHMARK_IMPORT_ERROR,
        }), 503

    try:
        data = get_json_body()
        target = str(data.get('target') or 'systems_api_helpers').strip()
        timeout = int(data.get('timeout_seconds') or 180)
        timeout = max(30, min(timeout, 1800))

        evaluator = GitHubBenchmarkEvaluator()
        result = evaluator.run(target=target, timeout_seconds=timeout)
        status_code = 200 if result.get('ok') else 500
        return jsonify({
            'code': 0 if result.get('ok') else 500,
            'message': 'success' if result.get('ok') else 'benchmark failed',
            'data': result,
        }), status_code
    except BenchmarkRunError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except BAD_REQUEST_EXCEPTIONS as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except (OSError, RuntimeError, ValueError, TypeError) as e:
        return jsonify({'code': 500, 'message': str(e)}), 500

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
                'pending_tasks': len(
                    [t for t in scheduler.tasks.values() if t.status == 'pending']
                ),
                'completed_tasks': len(
                    [t for t in scheduler.tasks.values() if t.status == 'completed']
                )
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
            },
            'benchmark': {
                'available': BENCHMARK_AVAILABLE,
                'error': None if BENCHMARK_AVAILABLE else BENCHMARK_IMPORT_ERROR,
            }
        }
    })
