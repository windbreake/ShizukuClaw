# -*- coding: utf-8 -*-
"""Built-in plugins for the new modular framework."""

import datetime
import re
import requests
from urllib.parse import quote_plus

from .base import PluginResult

PLUGIN_META = {
    "name": "builtin.basic",
    "version": "1.2.0",
    "description": "Built-in plugin commands, common rules and data query helpers",
    "author": "ShizukuNyaBot",
    "dependencies": []
}


def _truncate(text, limit=260):
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _http_get(plugin_name, manager, url, timeout=8):
    ok, reason = manager.validate_url_for_plugin(plugin_name, url)
    if not ok:
        return None, reason

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ShizukuNyaBot/1.0"})
        resp.raise_for_status()
        return resp, ""
    except Exception as exc:
        return None, str(exc)


def _load_builtin_config(manager, plugin_name):
    defaults = {
        "description": "Built-in basic plugin configuration",
        "version": "1.2.0",
        "enabled": True,
        "weather_default_city": "Beijing",
        "weather_lang": "zh",
        "wiki_default_lang": "zh",
        "news_default_query": "technology",
        "news_limit": 5,
        "request_timeout_seconds": 10,
    }

    try:
        cfg = manager.get_plugin_runtime_config(plugin_name)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    merged = dict(defaults)
    merged.update(cfg)

    # 自愈缺省字段，避免快捷配置面板出现空对象。
    if merged != cfg:
        try:
            manager.update_plugin_runtime_config(plugin_name, merged)
        except Exception:
            pass

    return merged


def register(registry, manager):
    plugin_name = "builtin.basic"
    _load_builtin_config(manager, plugin_name)
    required_domains = ["wttr.in", "wikipedia.org", "en.wikipedia.org", "zh.wikipedia.org", "hn.algolia.com"]
    manager.ensure_plugin_policy(
        plugin_name,
        {
            "enabled": True,
            "allow_network": True,
            "allowed_domains": required_domains,
            "allowed_commands": ["plugins", "echo", "weather", "wiki", "news"],
            "max_execution_ms": 12000,
        },
        persist=False,
    )

    # Self-heal policy drift from manual edits to avoid unexpected domain blocks.
    policy = manager.get_plugin_policy(plugin_name)
    if bool(policy.get("allow_network", True)):
        current_domains = [str(x).strip().lower() for x in (policy.get("allowed_domains") or []) if str(x).strip()]
        merged_domains = []
        for domain in current_domains + required_domains:
            d = str(domain).strip().lower()
            if d and d not in merged_domains:
                merged_domains.append(d)
        if merged_domains != current_domains:
            manager.update_plugin_policy(plugin_name, {"allowed_domains": merged_domains}, persist=True)

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

    def cmd_weather(ctx, arg):
        cfg = _load_builtin_config(manager, plugin_name)
        city = (arg or "").strip() or str(cfg.get("weather_default_city") or "Beijing")
        url = f"https://wttr.in/{quote_plus(city)}?format=j1"
        try:
            timeout = max(3, int(cfg.get("request_timeout_seconds", 10)))
        except Exception:
            timeout = 10
        resp, err = _http_get(plugin_name, manager, url, timeout=timeout)
        if resp is None:
            return PluginResult(handled=True, response=f"天气查询失败: {err}")

        try:
            data = resp.json()
            current = (data.get("current_condition") or [{}])[0]
            weather_desc = ((current.get("weatherDesc") or [{}])[0]).get("value", "-")
            temp_c = current.get("temp_C", "-")
            feels_like = current.get("FeelsLikeC", "-")
            humidity = current.get("humidity", "-")
            wind = current.get("windspeedKmph", "-")
            language = str(cfg.get("weather_lang") or "zh").lower()
            if language.startswith("en"):
                return PluginResult(
                    handled=True,
                    response=(
                        f"Current weather in {city}: {weather_desc}\\n"
                        f"Temp: {temp_c}°C (feels like {feels_like}°C)\\n"
                        f"Humidity: {humidity}% | Wind: {wind} km/h\\n"
                        f"Example: /weather Shanghai"
                    )
                )

            return PluginResult(
                handled=True,
                response=(
                    f"{city} 当前天气: {weather_desc}\\n"
                    f"温度: {temp_c}°C (体感 {feels_like}°C)\\n"
                    f"湿度: {humidity}% | 风速: {wind} km/h\\n"
                    f"命令示例: /weather 上海"
                )
            )
        except Exception as exc:
            return PluginResult(handled=True, response=f"天气解析失败: {exc}")

    def cmd_wiki(ctx, arg):
        cfg = _load_builtin_config(manager, plugin_name)
        query = (arg or "").strip()
        if not query:
            return PluginResult(handled=True, response="用法: /wiki 词条，例如 /wiki 机器学习")

        title = query.replace(" ", "_")
        lang = str(cfg.get("wiki_default_lang") or "zh").strip().lower()
        if lang not in ("zh", "en"):
            lang = "zh"

        try:
            timeout = max(3, int(cfg.get("request_timeout_seconds", 10)))
        except Exception:
            timeout = 10

        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}"
        resp, err = _http_get(plugin_name, manager, url, timeout=timeout)
        if resp is None:
            fallback_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}"
            resp, err = _http_get(plugin_name, manager, fallback_url, timeout=timeout)
        if resp is None:
            return PluginResult(handled=True, response=f"百科查询失败: {err}")

        try:
            data = resp.json()
            desc = _truncate(data.get("extract") or "未获取到摘要。", 500)
            page_url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page", "")
            ttl = data.get("title") or query
            return PluginResult(
                handled=True,
                response=(
                    f"百科词条: {ttl}\\n"
                    f"{desc}" + (f"\\n详情: {page_url}" if page_url else "")
                )
            )
        except Exception as exc:
            return PluginResult(handled=True, response=f"百科解析失败: {exc}")

    def cmd_news(ctx, arg):
        cfg = _load_builtin_config(manager, plugin_name)
        query = (arg or "").strip() or str(cfg.get("news_default_query") or "technology")
        try:
            limit = int(cfg.get("news_limit", 5))
        except Exception:
            limit = 5
        limit = max(1, min(10, limit))
        try:
            timeout = max(3, int(cfg.get("request_timeout_seconds", 10)))
        except Exception:
            timeout = 10

        url = f"https://hn.algolia.com/api/v1/search?query={quote_plus(query)}&tags=story&hitsPerPage={limit}"
        resp, err = _http_get(plugin_name, manager, url, timeout=timeout)
        if resp is None:
            return PluginResult(handled=True, response=f"新闻查询失败: {err}")

        try:
            data = resp.json()
            hits = data.get("hits") or []
            if not hits:
                return PluginResult(handled=True, response=f"未找到与 '{query}' 相关的新闻。")

            lines = [f"新闻检索: {query}"]
            for idx, item in enumerate(hits[:limit], start=1):
                title = _truncate(item.get("title") or item.get("story_title") or "(无标题)", 100)
                link = item.get("url") or "https://news.ycombinator.com/"
                lines.append(f"{idx}. {title}\\n   {link}")
            lines.append("命令示例: /news AI")
            return PluginResult(handled=True, response="\\n".join(lines))
        except Exception as exc:
            return PluginResult(handled=True, response=f"新闻解析失败: {exc}")

    def rule_time(ctx, match):
        now = datetime.datetime.now()
        return PluginResult(
            handled=True,
            response=f"现在时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def response_trim(ctx, response_text):
        # Keep response cleaner when extra spaces are produced by chained hooks.
        return re.sub(r"\s+", " ", response_text).strip()

    def rule_weather(ctx, match):
        city = (match.group(1) or "").strip() if match else ""
        return cmd_weather(ctx, city)

    def rule_wiki(ctx, match):
        term = (match.group(1) or "").strip() if match else ""
        return cmd_wiki(ctx, term)

    def rule_news(ctx, match):
        term = (match.group(1) or "").strip() if match else ""
        return cmd_news(ctx, term)

    registry.register_command("plugins", cmd_plugins, plugin_name)
    registry.register_command("echo", cmd_echo, plugin_name)
    registry.register_command("weather", cmd_weather, plugin_name)
    registry.register_command("wiki", cmd_wiki, plugin_name)
    registry.register_command("news", cmd_news, plugin_name)
    registry.register_regex_rule(r"(现在几点|当前时间|今天几号|今天日期)", rule_time, plugin_name, flags=re.IGNORECASE, priority=50)
    registry.register_regex_rule(r"天气\s*[:：]?\s*(.+)", rule_weather, plugin_name, flags=re.IGNORECASE, priority=40)
    registry.register_regex_rule(r"百科\s*[:：]?\s*(.+)", rule_wiki, plugin_name, flags=re.IGNORECASE, priority=40)
    registry.register_regex_rule(r"新闻\s*[:：]?\s*(.+)", rule_news, plugin_name, flags=re.IGNORECASE, priority=40)
    registry.register_response_handler(response_trim, plugin_name)
