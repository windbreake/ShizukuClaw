"""Smoke tests covering the major systems API and market routes."""

# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=too-few-public-methods,unused-argument,redefined-outer-name,line-too-long

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from src import systems_api as systems_module
from src import systems_market_api as market_module
from src.benchmark_evaluator import BenchmarkRunError
from src.systems_api import systems_bp


class Record:
    def __init__(self, **data):
        self.__dict__.update(data)

    def to_dict(self):
        return dict(self.__dict__)


class FakeLogger:
    def __init__(self):
        self.log_entries = [{'message': 'hello'}]

    def get_entries(self, level=None, limit=100):
        return self.log_entries[:limit]

    def clear_entries(self):
        self.log_entries.clear()


class FakeScheduler:
    def __init__(self):
        self.scheduler = SimpleNamespace(running=True)
        self.tasks = {}
        self._results = {}
        self._next_id = 1

    def list_tasks(self, status=None):
        items = [task.to_dict() for task in self.tasks.values()]
        if status:
            items = [task for task in items if task.get('status') == status]
        return items

    def add_task(self, task):
        task_id = str(self._next_id)
        self._next_id += 1
        data = getattr(task, '__dict__', {}).copy()
        data.update({'id': task_id, 'status': 'pending'})
        self.tasks[task_id] = Record(**data)
        self._results[task_id] = [{'id': 'result-1'}]
        return task_id

    def get_task(self, task_id):
        return self.tasks.get(str(task_id))

    def update_task(self, task_id, data):
        task = self.tasks.get(str(task_id))
        if not task:
            return None
        task.__dict__.update(data)
        return task

    def delete_task(self, task_id):
        return self.tasks.pop(str(task_id), None) is not None

    def cancel_task(self, task_id):
        task = self.tasks.get(str(task_id))
        if not task:
            return False
        task.status = 'cancelled'
        return True

    def get_task_results(self, task_id, limit):
        return list(self._results.get(str(task_id), []))[:limit]


class FakeMcpManager:
    def __init__(self):
        self.servers = {}
        self.resources = []
        self.tools = []
        self._next_id = 1

    def list_servers(self, enabled_only=False):
        items = [server.to_dict() for server in self.servers.values()]
        if enabled_only:
            items = [server for server in items if server.get('enabled', True)]
        return items

    def add_server(self, server):
        server_id = str(self._next_id)
        self._next_id += 1
        data = getattr(server, '__dict__', {}).copy()
        data.update({'id': server_id})
        self.servers[server_id] = Record(**data)
        return server_id

    def get_server(self, server_id):
        return self.servers.get(str(server_id))

    def update_server(self, server_id, data):
        server = self.servers.get(str(server_id))
        if not server:
            return None
        server.__dict__.update(data)
        return server

    def delete_server(self, server_id):
        return self.servers.pop(str(server_id), None) is not None


class FakeKnowledgeManager:
    def __init__(self):
        self.entries = {}
        self.glossaries = []
        self._next_id = 1

    def list_entries(self, category=None, entry_type=None):
        return [entry.to_dict() for entry in self.entries.values()]

    def search_entries(self, query, limit):
        return [entry.to_dict() for entry in self.entries.values()][:limit]

    def add_entry(self, entry):
        entry_id = str(self._next_id)
        self._next_id += 1
        data = getattr(entry, '__dict__', {}).copy()
        data.update({'id': entry_id, 'access_count': 0})
        self.entries[entry_id] = Record(**data)
        return entry_id

    def get_entry(self, entry_id):
        return self.entries.get(str(entry_id))

    def update_entry(self, entry_id, data):
        entry = self.entries.get(str(entry_id))
        if not entry:
            return None
        entry.__dict__.update(data)
        return entry

    def delete_entry(self, entry_id):
        return self.entries.pop(str(entry_id), None) is not None

    def get_categories(self):
        return ['general']


class FakeInstructionManager:
    def __init__(self):
        self.instructions = {}
        self.personalities = {}
        self.behavior_rules = {}
        self._next_id = 1

    def list_instructions(self, instruction_type=None, agent_id=None):
        return [instruction.to_dict() for instruction in self.instructions.values()]

    def add_instruction(self, instruction):
        instruction_id = str(self._next_id)
        self._next_id += 1
        data = getattr(instruction, '__dict__', {}).copy()
        data.update({'id': instruction_id})
        self.instructions[instruction_id] = Record(**data)
        return instruction_id

    def update_instruction(self, instruction_id, data):
        instruction = self.instructions.get(str(instruction_id))
        if not instruction:
            return None
        instruction.__dict__.update(data)
        return instruction

    def delete_instruction(self, instruction_id):
        return self.instructions.pop(str(instruction_id), None) is not None

    def list_personalities(self):
        return [personality.to_dict() for personality in self.personalities.values()]

    def add_personality(self, personality):
        personality_id = str(self._next_id)
        self._next_id += 1
        data = getattr(personality, '__dict__', {}).copy()
        data.update({'id': personality_id})
        self.personalities[personality_id] = Record(**data)
        return personality_id

    def delete_personality(self, personality_id):
        return self.personalities.pop(str(personality_id), None) is not None

    def list_behavior_rules(self):
        return [rule.to_dict() for rule in self.behavior_rules.values()]

    def add_behavior_rule(self, rule):
        rule_id = str(self._next_id)
        self._next_id += 1
        data = getattr(rule, '__dict__', {}).copy()
        data.update({'id': rule_id})
        self.behavior_rules[rule_id] = Record(**data)
        return rule_id


class FakeBenchmarkEvaluator:
    def list_targets(self):
        return [{'key': 'systems_api_helpers', 'description': 'smoke'}]

    def run(self, target, timeout_seconds=180):
        return {'ok': True, 'target': target, 'summary': {'benchmarks_count': 1}}


@pytest.fixture()
def client(monkeypatch):
    logger = FakeLogger()
    scheduler = FakeScheduler()
    mcp_manager = FakeMcpManager()
    knowledge_manager = FakeKnowledgeManager()
    instruction_manager = FakeInstructionManager()

    monkeypatch.setattr(systems_module, 'get_enhanced_logger', lambda: logger)
    monkeypatch.setattr(systems_module, 'get_task_scheduler', lambda: scheduler)
    monkeypatch.setattr(systems_module, 'get_mcp_manager', lambda: mcp_manager)
    monkeypatch.setattr(systems_module, 'get_knowledge_base_manager', lambda: knowledge_manager)
    monkeypatch.setattr(systems_module, 'get_instruction_manager', lambda: instruction_manager)
    monkeypatch.setattr(systems_module, 'GitHubBenchmarkEvaluator', FakeBenchmarkEvaluator)
    monkeypatch.setattr(market_module, 'get_mcp_manager', lambda: mcp_manager)

    monkeypatch.setattr(market_module, '_find_smithery_cli', lambda: 'smithery')
    monkeypatch.setattr(market_module, '_mcp_smithery_cache_get', lambda key: None)
    monkeypatch.setattr(
        market_module,
        '_query_smithery_market',
        lambda page, page_size, query, cli: {
            'items': [{'id': 'smithery-1', 'name': 'demo'}],
            'has_more': False,
            'total': 1,
            'effective_query': query or 'github',
            'errors': [],
        },
    )
    monkeypatch.setattr(
        market_module,
        '_start_smithery_install_job',
        lambda: {'job_id': 'job-1', 'status': 'queued', 'command_display': 'install', 'logs': []},
    )
    monkeypatch.setattr(
        market_module,
        '_smithery_install_job_snapshot',
        lambda job_id: (
            {
                'job_id': job_id,
                'status': 'queued',
                'command_display': 'install',
                'logs': [],
                'installed': False,
            }
            if job_id == 'job-1'
            else None
        ),
    )
    monkeypatch.setattr(
        market_module,
        '_smithery_runner_info',
        lambda: {'cli': 'smithery', 'installed': True, 'mode': 'global'},
    )
    monkeypatch.setattr(
        market_module,
        '_run_smithery_cli',
        lambda args, timeout=45: {'ok': True, 'stdout': 'smithery 1.0.0\n', 'stderr': '', 'code': 0},
    )

    app = Flask(__name__)
    app.register_blueprint(systems_bp)
    app.testing = True
    return app.test_client()


def test_logs_and_tasks_flow(client):
    response = client.get('/api/systems/logs?limit=5')
    assert response.status_code == 200
    assert response.get_json()['code'] == 0

    response = client.post('/api/systems/tasks', json={'name': 'demo task', 'command': 'echo hi'})
    assert response.status_code == 201
    task_id = response.get_json()['data']['id']

    response = client.get(f'/api/systems/tasks/{task_id}')
    assert response.status_code == 200
    assert response.get_json()['data']['name'] == 'demo task'

    response = client.put(f'/api/systems/tasks/{task_id}', json={'description': 'updated'})
    assert response.status_code == 200
    assert response.get_json()['data']['description'] == 'updated'

    response = client.get(f'/api/systems/tasks/{task_id}/results')
    assert response.status_code == 200
    assert response.get_json()['count'] == 1

    response = client.post(f'/api/systems/tasks/{task_id}/cancel')
    assert response.status_code == 200

    response = client.delete(f'/api/systems/tasks/{task_id}')
    assert response.status_code == 200


def test_mcp_knowledge_and_instruction_flows(client):
    response = client.get('/api/systems/mcp/servers')
    assert response.status_code == 200

    response = client.post('/api/systems/mcp/servers', json={'name': 'mcp-a', 'type': 'stdio'})
    assert response.status_code == 201
    server_id = response.get_json()['data']['id']

    response = client.get(f'/api/systems/mcp/servers/{server_id}')
    assert response.status_code == 200
    assert response.get_json()['data']['name'] == 'mcp-a'

    response = client.put(f'/api/systems/mcp/servers/{server_id}', json={'enabled': False})
    assert response.status_code == 200
    assert response.get_json()['data']['enabled'] is False

    response = client.get('/api/systems/knowledge/categories')
    assert response.status_code == 200

    response = client.post('/api/systems/knowledge/entries', json={'title': 'kb', 'content': 'hello'})
    assert response.status_code == 201
    entry_id = response.get_json()['data']['id']

    response = client.get(f'/api/systems/knowledge/entries/{entry_id}')
    assert response.status_code == 200
    assert response.get_json()['data']['title'] == 'kb'

    response = client.post('/api/systems/instructions', json={'name': 'instr', 'content': 'x'})
    assert response.status_code == 201
    instruction_id = response.get_json()['data']['id']

    response = client.get('/api/systems/personalities')
    assert response.status_code == 200

    response = client.post('/api/systems/personalities', json={'name': 'persona'})
    assert response.status_code == 201
    personality_id = response.get_json()['data']['id']

    response = client.get('/api/systems/behavior-rules')
    assert response.status_code == 200

    response = client.post('/api/systems/behavior-rules', json={'name': 'rule', 'trigger_pattern': 'x'})
    assert response.status_code == 201

    response = client.delete(f'/api/systems/personalities/{personality_id}')
    assert response.status_code == 200

    response = client.delete(f'/api/systems/instructions/{instruction_id}')
    assert response.status_code == 200


def test_market_benchmark_and_status_flows(client):
    response = client.get('/api/systems/mcp/market')
    assert response.status_code == 200

    response = client.post('/api/systems/mcp/market/install', json={'id': 'filesystem-local'})
    assert response.status_code in (200, 201)

    response = client.get('/api/systems/mcp/market/smithery/search')
    assert response.status_code == 200
    assert response.get_json()['count'] == 1

    response = client.get('/api/systems/mcp/market/smithery/status')
    assert response.status_code == 200
    assert response.get_json()['data']['installed'] is True

    response = client.post('/api/systems/mcp/market/smithery/cli/install')
    assert response.status_code == 200

    response = client.get('/api/systems/mcp/market/smithery/cli/install/jobs/job-1')
    assert response.status_code == 200

    response = client.post('/api/systems/mcp/market/smithery/install', json={'server_id': 'abc'})
    assert response.status_code == 200

    response = client.get('/api/systems/benchmark/targets')
    assert response.status_code == 200
    assert response.get_json()['count'] == 1

    response = client.post('/api/systems/benchmark/run', json={'target': 'systems_api_helpers'})
    assert response.status_code == 200
    assert response.get_json()['data']['ok'] is True

    response = client.get('/api/systems/system-status')
    assert response.status_code == 200
    payload = response.get_json()['data']
    assert payload['mcp']['servers'] >= 1
    assert payload['knowledge_base']['categories'] >= 1


def test_error_paths_for_systems_and_market_routes(client, monkeypatch):
    response = client.post('/api/systems/tasks', json=[])
    assert response.status_code == 400
    assert response.get_json()['code'] == 400

    response = client.put('/api/systems/tasks/9999', json={})
    assert response.status_code == 404

    response = client.post('/api/systems/mcp/market/install', json={})
    assert response.status_code == 400

    response = client.post('/api/systems/mcp/market/install', json={'id': 'not-exists'})
    assert response.status_code == 404

    response = client.post('/api/systems/mcp/market/smithery/install', json={})
    assert response.status_code == 400

    response = client.get('/api/systems/mcp/market/smithery/cli/install/jobs/not-found')
    assert response.status_code == 404

    monkeypatch.setattr(
        market_module,
        '_query_smithery_market',
        lambda page, page_size, query, cli: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    response = client.get('/api/systems/mcp/market/smithery/search')
    assert response.status_code == 502


def test_benchmark_run_returns_400_on_benchmark_run_error(client, monkeypatch):
    class InvalidTargetEvaluator:
        def run(self, target, timeout_seconds=180):
            raise BenchmarkRunError('unknown target')

    monkeypatch.setattr(systems_module, 'GitHubBenchmarkEvaluator', InvalidTargetEvaluator)

    response = client.post('/api/systems/benchmark/run', json={'target': 'bad-target'})
    assert response.status_code == 400
    assert response.get_json()['code'] == 400


def test_benchmark_run_returns_500_on_runtime_error(client, monkeypatch):
    class RuntimeFailureEvaluator:
        def run(self, target, timeout_seconds=180):
            raise RuntimeError('runner crashed')

    monkeypatch.setattr(systems_module, 'GitHubBenchmarkEvaluator', RuntimeFailureEvaluator)

    response = client.post('/api/systems/benchmark/run', json={'target': 'systems_api_helpers'})
    assert response.status_code == 500
    assert response.get_json()['code'] == 500


def test_benchmark_run_returns_400_on_non_object_json_body(client):
    response = client.post('/api/systems/benchmark/run', json=[])
    assert response.status_code == 400
    assert response.get_json()['code'] == 400


@pytest.mark.parametrize(
    'method,path',
    [
        ('post', '/api/systems/tasks'),
        ('put', '/api/systems/tasks/9999'),
        ('post', '/api/systems/mcp/servers'),
        ('post', '/api/systems/knowledge/entries'),
        ('post', '/api/systems/instructions'),
        ('post', '/api/systems/personalities'),
        ('post', '/api/systems/behavior-rules'),
        ('post', '/api/systems/mcp/market/install'),
        ('post', '/api/systems/mcp/market/smithery/install'),
    ],
)
def test_non_object_json_body_returns_400_consistently(client, method, path):
    response = getattr(client, method)(path, json=[])
    assert response.status_code == 400
    assert response.get_json()['code'] == 400
