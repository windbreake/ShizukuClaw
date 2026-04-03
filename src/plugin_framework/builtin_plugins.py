# -*- coding: utf-8 -*-
"""Built-in plugins for the new modular framework."""

import datetime
import re

from .base import PluginResult

PLUGIN_META = {
    "name": "builtin.basic",
    "version": "1.1.0",
    "description": "Built-in plugin commands and common rules",
    "author": "ShizukuNyaBot",
    "dependencies": []
}


def register(registry, manager):
    plugin_name = "builtin.basic"

    def cmd_plugins(ctx, arg):
        sub = (arg or "").strip().lower()
        if sub == "reload":
            if not ctx.is_admin:
                return PluginResult(handled=True, response="权限不足：仅管理员可执行插件热重载。")
            manager.reload_all()
            return PluginResult(handled=True, response="插件已热重载完成。")

        lines = ["当前已加载插件:"]
        for name in manager.get_loaded_plugins():
            lines.append(f"- {name}")
        lines.append("\n可用命令:")
        for command in manager.get_registered_commands():
            lines.append(f"- /{command}")
        lines.append("\n生命周期:")
        lines.append("- on_startup/on_shutdown/on_message/on_response/on_error")
        lines.append("\n管理命令:")
        lines.append("- /plugins reload")
        return PluginResult(handled=True, response="\n".join(lines))

    def cmd_echo(ctx, arg):
        text = (arg or "").strip()
        if not text:
            text = "(empty)"
        return PluginResult(handled=True, response=text)

    def rule_time(ctx, match):
        now = datetime.datetime.now()
        return PluginResult(
            handled=True,
            response=f"现在时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def response_trim(ctx, response_text):
        # Keep response cleaner when extra spaces are produced by chained hooks.
        return re.sub(r"\s+", " ", response_text).strip()

    registry.register_command("plugins", cmd_plugins, plugin_name)
    registry.register_command("echo", cmd_echo, plugin_name)
    registry.register_regex_rule(r"(现在几点|当前时间|今天几号|今天日期)", rule_time, plugin_name, flags=re.IGNORECASE, priority=50)
    registry.register_response_handler(response_trim, plugin_name)
