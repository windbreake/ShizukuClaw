# -*- coding: utf-8 -*-
"""
系统集成模块 - 整合所有新系统的API接口
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import json

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
