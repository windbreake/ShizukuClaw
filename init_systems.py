# -*- coding: utf-8 -*-
"""
系统初始化脚本 - 初始化所有新增系统的基础配置和演示
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def init_systems():
    """初始化所有系统"""
    print("=" * 60)
    print("🚀 Shizuku 项目系统初始化")
    print("=" * 60)
    
    # 1. 初始化日志系统
    print("\n📝 初始化增强型日志系统...")
    from src.enhanced_logging import get_enhanced_logger
    logger = get_enhanced_logger()
    logger.info("系统初始化开始")
    logger.success("日志系统已启动")
    
    # 2. 初始化任务调度系统
    print("⏰ 初始化定时任务系统...")
    from src.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
    scheduler = get_task_scheduler()
    print(f"   - 任务调度器已启动，运行状态: {scheduler.scheduler.running}")
    logger.info(f"任务调度器已初始化，当前任务数: {len(scheduler.tasks)}")
    
    # 3. 初始化MCP系统
    print("🔌 初始化MCP管理系统...")
    from src.mcp_manager import get_mcp_manager
    mcp_manager = get_mcp_manager()
    print(f"   - MCP服务器数: {len(mcp_manager.servers)}")
    print(f"   - MCP资源数: {len(mcp_manager.resources)}")
    print(f"   - MCP工具数: {len(mcp_manager.tools)}")
    logger.info("MCP管理系统已初始化")
    
    # 4. 初始化知识库系统
    print("📚 初始化知识库/词库系统...")
    from src.knowledge_base_manager import get_knowledge_base_manager, KnowledgeEntry, Glossary, EntryType
    kb_manager = get_knowledge_base_manager()
    print(f"   - 知识库条目数: {len(kb_manager.entries)}")
    print(f"   - 词库数: {len(kb_manager.glossaries)}")
    print(f"   - 知识分类数: {len(kb_manager.get_categories())}")
    logger.info("知识库系统已初始化")
    
    # 5. 初始化指令系统
    print("🎭 初始化自定义指令系统...")
    from src.instruction_manager import (
        get_instruction_manager, AgentInstruction, Personality, BehaviorRule,
        InstructionType
    )
    instr_manager = get_instruction_manager()
    print(f"   - 指令数: {len(instr_manager.instructions)}")
    print(f"   - 人格配置数: {len(instr_manager.personalities)}")
    print(f"   - 行为规则数: {len(instr_manager.behavior_rules)}")
    logger.info("指令系统已初始化")
    
    # 6. 创建默认配置（仅在首次运行时）
    if len(instr_manager.personalities) == 0:
        print("\n💫 创建默认人格配置...")
        default_personality = Personality(
            name="小雫",
            description="友善聪慧的AI助手小雫",
            traits={
                "cheerfulness": 0.85,
                "helpfulness": 0.9,
                "humor": 0.7,
                "professionalism": 0.6
            },
            tone="casual",
            speaking_style="cute",
            emoji_usage=True,
            response_length="medium"
        )
        instr_manager.add_personality(default_personality)
        logger.success("默认人格已创建: 小雫")
    
    if len(instr_manager.instructions) == 0:
        print("📋 创建默认系统指令...")
        sys_prompt = AgentInstruction(
            name="系统基础指令",
            instruction_type=InstructionType.SYSTEM_PROMPT.value,
            content="你是一个友善、聪慧的AI助手小雫。你很喜欢和用户交流，总是以积极、热情的态度对待每一个对话。",
            priority=100,
            enabled=True
        )
        instr_manager.add_instruction(sys_prompt)
        logger.success("默认系统指令已创建")
    
    if len(kb_manager.entries) == 0:
        print("📖 创建默认知识库条目...")
        knowledge = KnowledgeEntry(
            title="项目介绍",
            content="这是Shizuku机器人项目，一个功能完整的AI对话系统。",
            entry_type=EntryType.KNOWLEDGE.value,
            category="项目信息",
            tags=["项目", "介绍"],
            keywords=["Shizuku", "机器人"],
            priority=10,
            author="系统",
            source="内置"
        )
        kb_manager.add_entry(knowledge)
        logger.success("默认知识库条目已创建")
    
    # 7. 创建示例定时任务
    if len(scheduler.tasks) == 0:
        print("⏲️  创建示例定时任务...")
        
        # 示例1：一次性提醒任务
        tomorrow_2pm = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
        reminder_task = AgentTask(
            name="下午喝水提醒",
            description="提醒用户下午喝水",
            task_type=TaskType.ONE_TIME.value,
            scheduled_time=tomorrow_2pm.isoformat(),
            command="remind_water",
            args={"message": "该喝水啦！💧"},
            enabled=False  # 默认禁用
        )
        
        def remind_water(message):
            logger.info(f"💧 提醒: {message}")
            return {"status": "success", "message": message}
        
        scheduler.add_task(reminder_task, callback=remind_water)
        logger.info(f"示例任务已创建: {reminder_task.name}")
        print(f"   - 任务已创建但默认禁用（可通过API启用）")
    
    print("\n" + "=" * 60)
    logger.success("✨ 所有系统初始化完成！")
    print("=" * 60)
    
    # 打印系统统计信息
    print("\n📊 系统统计信息:")
    print(f"   📝 日志条目: {len(logger.log_entries)}")
    print(f"   ⏰ 定时任务: {len(scheduler.tasks)}")
    print(f"   🔌 MCP服务: {len(mcp_manager.servers)}")
    print(f"   📚 知识库条目: {len(kb_manager.entries)}")
    print(f"   🎭 指令集: {len(instr_manager.instructions)}")
    print(f"      - 人格配置: {len(instr_manager.personalities)}")
    print(f"      - 行为规则: {len(instr_manager.behavior_rules)}")
    
    print("\n🌐 API访问地址:")
    print("   - 日志：GET http://localhost:8888/api/systems/logs")
    print("   - 任务: POST http://localhost:8888/api/systems/tasks")
    print("   - MCP: GET http://localhost:8888/api/systems/mcp/servers")
    print("   - 知识库: GET http://localhost:8888/api/systems/knowledge/entries")
    print("   - 指令: GET http://localhost:8888/api/systems/instructions")
    
    print("\n📖 详细文档:")
    print("   - 查看 SYSTEMS_README.md 了解各系统使用方法")
    
    return logger, scheduler, mcp_manager, kb_manager, instr_manager


if __name__ == '__main__':
    try:
        init_systems()
        print("\n✅ 初始化成功！项目已准备就绪。")
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
