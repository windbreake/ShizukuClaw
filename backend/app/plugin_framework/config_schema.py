# -*- coding: utf-8 -*-
"""Plugin configuration schema and UI generator.

This module provides a declarative way to define plugin settings UI through JSON schemas.
Plugins can define their configuration forms without writing frontend code.

Example usage in plugin.py:
    PLUGIN_CONFIG_SCHEMA = {
        "title": "我的插件设置",
        "description": "配置我的插件参数",
        "sections": [
            {
                "title": "基础设置",
                "fields": [
                    {
                        "key": "enabled",
                        "type": "switch",
                        "label": "启用插件",
                        "default": True,
                        "description": "开启或关闭插件功能"
                    },
                    {
                        "key": "api_key",
                        "type": "password",
                        "label": "API密钥",
                        "placeholder": "请输入API Key",
                        "required": True
                    }
                ]
            }
        ]
    }
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ConfigField:
    """Configuration field definition."""
    key: str  # 配置键名
    type: str  # 字段类型: switch, text, number, password, textarea, select, slider, color, date, time
    label: str  # 显示标签
    default: Any = None  # 默认值
    description: str = ""  # 描述文本
    placeholder: str = ""  # 占位符
    required: bool = False  # 是否必填
    min: Optional[float] = None  # 最小值（用于number/slider）
    max: Optional[float] = None  # 最大值（用于number/slider）
    step: Optional[float] = None  # 步长（用于number/slider）
    options: List[Dict[str, str]] = field(default_factory=list)  # 选项列表（用于select）[{value, label}]
    pattern: Optional[str] = None  # 正则验证模式
    validation_message: Optional[str] = None  # 验证失败提示
    disabled: bool = False  # 是否禁用
    hidden: bool = False  # 是否隐藏
    depends_on: Optional[Dict[str, Any]] = None  # 依赖条件 {field_key: expected_value}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "key": self.key,
            "type": self.type,
            "label": self.label,
            "default": self.default,
            "description": self.description,
            "placeholder": self.placeholder,
            "required": self.required,
            "disabled": self.disabled,
            "hidden": self.hidden
        }
        
        # Add optional fields only if they exist
        if self.min is not None:
            data["min"] = self.min
        if self.max is not None:
            data["max"] = self.max
        if self.step is not None:
            data["step"] = self.step
        if self.options:
            data["options"] = self.options
        if self.pattern:
            data["pattern"] = self.pattern
        if self.validation_message:
            data["validation_message"] = self.validation_message
        if self.depends_on:
            data["depends_on"] = self.depends_on
            
        return data


@dataclass
class ConfigSection:
    """Configuration section grouping multiple fields."""
    title: str  # 区块标题
    description: str = ""  # 区块描述
    collapsed: bool = False  # 是否默认折叠
    fields: List[ConfigField] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "collapsed": self.collapsed,
            "fields": [f.to_dict() for f in self.fields]
        }


@dataclass
class ConfigSchema:
    """Complete configuration schema for a plugin."""
    title: str = "插件配置"  # 配置页面标题
    description: str = ""  # 配置页面描述
    version: str = "1.0.0"  # 配置schema版本
    sections: List[ConfigSection] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConfigSchema':
        """Create ConfigSchema from dictionary."""
        sections = []
        for section_data in data.get("sections", []):
            fields = []
            for field_data in section_data.get("fields", []):
                field = ConfigField(
                    key=field_data["key"],
                    type=field_data["type"],
                    label=field_data["label"],
                    default=field_data.get("default"),
                    description=field_data.get("description", ""),
                    placeholder=field_data.get("placeholder", ""),
                    required=field_data.get("required", False),
                    min=field_data.get("min"),
                    max=field_data.get("max"),
                    step=field_data.get("step"),
                    options=field_data.get("options", []),
                    pattern=field_data.get("pattern"),
                    validation_message=field_data.get("validation_message"),
                    disabled=field_data.get("disabled", False),
                    hidden=field_data.get("hidden", False),
                    depends_on=field_data.get("depends_on")
                )
                fields.append(field)
            
            section = ConfigSection(
                title=section_data["title"],
                description=section_data.get("description", ""),
                collapsed=section_data.get("collapsed", False),
                fields=fields
            )
            sections.append(section)
        
        return cls(
            title=data.get("title", "插件配置"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            sections=sections
        )


# 预定义的常用字段类型
class FieldTypes:
    """Common field type constants."""
    SWITCH = "switch"  # 开关
    TEXT = "text"  # 单行文本
    NUMBER = "number"  # 数字
    PASSWORD = "password"  # 密码
    TEXTAREA = "textarea"  # 多行文本
    SELECT = "select"  # 下拉选择
    SLIDER = "slider"  # 滑块
    COLOR = "color"  # 颜色选择器
    DATE = "date"  # 日期
    TIME = "time"  # 时间
    EMAIL = "email"  # 邮箱
    URL = "url"  # URL地址
    TAGS = "tags"  # 标签输入


# 示例配置
def create_example_schema() -> dict:
    """Create an example configuration schema."""
    schema = ConfigSchema(
        title="示例插件配置",
        description="展示所有可用的配置字段类型",
        sections=[
            ConfigSection(
                title="基础设置",
                description="插件的基本功能开关",
                fields=[
                    ConfigField(
                        key="enabled",
                        type=FieldTypes.SWITCH,
                        label="启用插件",
                        default=True,
                        description="开启或关闭插件功能"
                    ),
                    ConfigField(
                        key="debug_mode",
                        type=FieldTypes.SWITCH,
                        label="调试模式",
                        default=False,
                        description="开启后会输出详细日志"
                    )
                ]
            ),
            ConfigSection(
                title="API配置",
                description="配置外部API连接信息",
                fields=[
                    ConfigField(
                        key="api_key",
                        type=FieldTypes.PASSWORD,
                        label="API密钥",
                        placeholder="请输入API Key",
                        required=True,
                        description="从服务商获取的API密钥"
                    ),
                    ConfigField(
                        key="api_url",
                        type=FieldTypes.URL,
                        label="API地址",
                        default="https://api.example.com/v1",
                        placeholder="https://api.example.com/v1"
                    ),
                    ConfigField(
                        key="timeout",
                        type=FieldTypes.NUMBER,
                        label="超时时间",
                        default=30,
                        min=1,
                        max=300,
                        step=1,
                        description="请求超时时间（秒）"
                    )
                ]
            ),
            ConfigSection(
                title="高级设置",
                description="高级用户可调整的参数",
                collapsed=True,
                fields=[
                    ConfigField(
                        key="model",
                        type=FieldTypes.SELECT,
                        label="模型选择",
                        default="gpt-4",
                        options=[
                            {"value": "gpt-4", "label": "GPT-4"},
                            {"value": "gpt-3.5", "label": "GPT-3.5"},
                            {"value": "claude", "label": "Claude"}
                        ]
                    ),
                    ConfigField(
                        key="temperature",
                        type=FieldTypes.SLIDER,
                        label="温度参数",
                        default=0.7,
                        min=0,
                        max=2,
                        step=0.1,
                        description="控制输出的随机性"
                    ),
                    ConfigField(
                        key="system_prompt",
                        type=FieldTypes.TEXTAREA,
                        label="系统提示词",
                        default="你是一个有用的助手",
                        placeholder="输入自定义的系统提示词...",
                        description="定义AI助手的角色和行为"
                    ),
                    ConfigField(
                        key="theme_color",
                        type=FieldTypes.COLOR,
                        label="主题颜色",
                        default="#4CAF50",
                        description="界面主题色"
                    )
                ]
            )
        ]
    )
    
    return schema.to_dict()
