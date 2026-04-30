"""Framework manager exports for backward-compatible imports."""

from .instruction_manager import (
	AgentInstruction,
	BehaviorRule,
	InstructionType,
	Personality,
	get_instruction_manager,
)
from .knowledge_base_manager import KnowledgeEntry, EntryType, get_knowledge_base_manager
from .mcp_manager import MCPManager, MCPResource, MCPServer, MCPTool, get_mcp_manager

__all__ = [
	"MCPManager",
	"MCPServer",
	"MCPResource",
	"MCPTool",
	"get_mcp_manager",
	"KnowledgeEntry",
	"EntryType",
	"get_knowledge_base_manager",
	"AgentInstruction",
	"BehaviorRule",
	"InstructionType",
	"Personality",
	"get_instruction_manager",
]
