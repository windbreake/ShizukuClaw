# -*- coding: utf-8 -*-
"""
Agent定时任务系统 - 支持灵活的任务调度
例如：明天下午14:00提醒我喝水
"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, asdict, field
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import os


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"        # 待处理
    RUNNING = "running"        # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class TaskType(Enum):
    """任务类型"""
    ONE_TIME = "one_time"      # 一次性任务
    RECURRING = "recurring"    # 循环任务
    CRON = "cron"             # Cron任务


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    status: str
    output: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class AgentTask:
    """Agent定时任务定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    task_type: str = TaskType.ONE_TIME.value
    status: str = TaskStatus.PENDING.value
    
    # 执行配置
    command: str = ""           # 要执行的命令或回调
    args: Dict[str, Any] = field(default_factory=dict)
    
    # 调度配置
    scheduled_time: Optional[str] = None  # ISO格式时间: 2026-04-05T14:00:00
    cron_expression: Optional[str] = None # Cron表达式: "0 14 * * *"
    interval_seconds: Optional[int] = None # 间隔秒数
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    run_count: int = 0
    
    # 重试配置
    max_retries: int = 3
    retry_count: int = 0
    
    enabled: bool = True
    notify_on_complete: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        return data


class AgentTaskScheduler:
    """Agent任务调度器"""
    
    def __init__(self, storage_dir: str = 'data/tasks'):
        """
        初始化任务调度器
        
        Args:
            storage_dir: 任务存储目录
        """
        self.storage_dir = storage_dir
        self.tasks_file = os.path.join(storage_dir, 'tasks.json')
        self.scheduler = BackgroundScheduler()
        self.tasks: Dict[str, AgentTask] = {}
        self.task_callbacks: Dict[str, Callable] = {}
        self.task_results: Dict[str, List[TaskResult]] = {}
        
        # 创建存储目录
        os.makedirs(storage_dir, exist_ok=True)
        
        # 加载已保存的任务
        self._load_tasks()
        
        # 启动调度器
        if not self.scheduler.running:
            self.scheduler.start()
    
    def _load_tasks(self):
        """从文件加载任务"""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_dict in data:
                        task = AgentTask(**task_dict)
                        self.tasks[task.id] = task
            except Exception as e:
                print(f"Error loading tasks: {e}")
    
    def _save_tasks(self):
        """保存任务到文件"""
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                data = [task.to_dict() for task in self.tasks.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving tasks: {e}")
    
    def add_task(self, task: AgentTask, callback: Optional[Callable] = None) -> str:
        """
        添加任务
        
        Args:
            task: AgentTask对象
            callback: 任务执行时的回调函数
            
        Returns:
            任务ID
        """
        self.tasks[task.id] = task
        
        if callback:
            self.task_callbacks[task.id] = callback
        
        self.task_results[task.id] = []
        
        # 调度任务
        if task.enabled:
            self._schedule_task(task)
        
        self._save_tasks()
        return task.id
    
    def _schedule_task(self, task: AgentTask):
        """调度任务执行"""
        if task.task_type == TaskType.ONE_TIME.value:
            if task.scheduled_time:
                run_time = datetime.fromisoformat(task.scheduled_time)
                self.scheduler.add_job(
                    self._execute_task,
                    DateTrigger(run_date=run_time),
                    args=[task.id],
                    id=task.id,
                    replace_existing=True
                )
                task.next_run_time = task.scheduled_time
        
        elif task.task_type == TaskType.CRON.value:
            if task.cron_expression:
                self.scheduler.add_job(
                    self._execute_task,
                    CronTrigger.from_crontab(task.cron_expression),
                    args=[task.id],
                    id=task.id,
                    replace_existing=True
                )
        
        elif task.task_type == TaskType.RECURRING.value:
            if task.interval_seconds:
                self.scheduler.add_job(
                    self._execute_task,
                    'interval',
                    seconds=task.interval_seconds,
                    args=[task.id],
                    id=task.id,
                    replace_existing=True
                )
    
    def _execute_task(self, task_id: str):
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatus.RUNNING.value
        start_time = datetime.now()
        
        try:
            # 执行回调或命令
            output = None
            if task_id in self.task_callbacks:
                callback = self.task_callbacks[task_id]
                output = callback(**task.args)
            else:
                # 这里可以扩展为执行其他类型的命令
                output = f"Executed: {task.command}"
            
            # 记录成功结果
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED.value,
                output=output,
                executed_at=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            task.status = TaskStatus.COMPLETED.value
            task.run_count += 1
            task.last_run_time = datetime.now().isoformat()
            task.retry_count = 0
            
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED.value,
                error=str(e),
                executed_at=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            task.retry_count += 1
            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED.value
            else:
                task.status = TaskStatus.PENDING.value
        
        # 保存结果
        self.task_results[task_id].append(result)
        task.updated_at = datetime.now().isoformat()
        self._save_tasks()
        
        return result
    
    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列表查询任务
        
        Args:
            status: 过滤状态
            
        Returns:
            任务列表
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return [t.to_dict() for t in tasks]
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[AgentTask]:
        """更新任务"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        # 更新字段
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        task.updated_at = datetime.now().isoformat()
        
        # 重新调度
        self.scheduler.remove_job(task_id)
        if task.enabled:
            self._schedule_task(task)
        
        self._save_tasks()
        return task
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.CANCELLED.value
        task.updated_at = datetime.now().isoformat()
        
        try:
            self.scheduler.remove_job(task_id)
        except:
            pass
        
        self._save_tasks()
        return True
    
    def get_task_results(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取任务执行结果"""
        results = self.task_results.get(task_id, [])
        return [asdict(r) for r in results[-limit:]]
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            
            try:
                self.scheduler.remove_job(task_id)
            except:
                pass
            
            if task_id in self.task_callbacks:
                del self.task_callbacks[task_id]
            
            if task_id in self.task_results:
                del self.task_results[task_id]
            
            self._save_tasks()
            return True
        
        return False
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()


# 全局调度器实例
_scheduler_instance: Optional[AgentTaskScheduler] = None


def get_task_scheduler() -> AgentTaskScheduler:
    """获取或创建任务调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AgentTaskScheduler()
    return _scheduler_instance
