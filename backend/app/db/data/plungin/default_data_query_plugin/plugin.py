# -*- coding: utf-8 -*-
"""Default data query plugin: weather/wiki/news."""

import requests
import re
from urllib.parse import quote_plus

try:
    from app.plugin_framework.base import PluginResult
except Exception:
    from plugin_framework.base import PluginResult

PLUGIN_META = {
    "name": "default.data_query",
    "version": "1.0.0",
    "description": "默认数据查询插件（天气/百科/新闻）",
    "author": "ShizukuNyaBot",
    "dependencies": []
}


def _truncate(text, limit=260):
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _read_cfg(manager, plugin_name):
    defaults = {
        "weather_default_city": "Beijing",
        "weather_lang": "zh",
        "wiki_default_lang": "zh",
        "news_default_query": "technology",
        "news_limit": 5,
        "request_timeout_seconds": 10
    }
    try:
        cfg = manager.get_plugin_runtime_config(plugin_name)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    merged = dict(defaults)
    merged.update(cfg)
    if merged != cfg:
        try:
            manager.update_plugin_runtime_config(plugin_name, merged)
        except Exception:
            pass
    return merged


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


def register(registry, manager):
    plugin_name = "default.data_query"
    manager.ensure_plugin_policy(
        plugin_name,
        {
            "enabled": True,
            "allow_network": True,
            "allowed_domains": ["wttr.in", "wikipedia.org", "en.wikipedia.org", "zh.wikipedia.org", "hn.algolia.com"],
            "allowed_commands": ["weather", "wiki", "news"],
            "max_execution_ms": 12000,
        },
        persist=False,
    )

    _read_cfg(manager, plugin_name)

    def cmd_weather(ctx, arg):
        cfg = _read_cfg(manager, plugin_name)
        city = (arg or "").strip() or str(cfg.get("weather_default_city") or "Beijing")
        try:
            timeout = max(3, int(cfg.get("request_timeout_seconds", 10)))
        except Exception:
            timeout = 10

        url = f"https://wttr.in/{quote_plus(city)}?format=j1"
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
                        f"Current weather in {city}: {weather_desc}\n"
                        f"Temp: {temp_c}°C (feels like {feels_like}°C)\n"
                        f"Humidity: {humidity}% | Wind: {wind} km/h"
                    )
                )

            return PluginResult(
                handled=True,
                response=(
                    f"{city} 当前天气: {weather_desc}\n"
                    f"温度: {temp_c}°C (体感 {feels_like}°C)\n"
                    f"湿度: {humidity}% | 风速: {wind} km/h"
                )
            )
        except Exception as exc:
            return PluginResult(handled=True, response=f"天气解析失败: {exc}")

    def cmd_wiki(ctx, arg):
        cfg = _read_cfg(manager, plugin_name)
        query = (arg or "").strip()
        if not query:
            return PluginResult(handled=True, response="用法: /wiki 词条，例如 /wiki 机器学习")

        lang = str(cfg.get("wiki_default_lang") or "zh").strip().lower()
        if lang not in ("zh", "en"):
            lang = "zh"

        try:
            timeout = max(3, int(cfg.get("request_timeout_seconds", 10)))
        except Exception:
            timeout = 10

        title = query.replace(" ", "_")
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
                response=(f"百科词条: {ttl}\n{desc}" + (f"\n详情: {page_url}" if page_url else ""))
            )
        except Exception as exc:
            return PluginResult(handled=True, response=f"百科解析失败: {exc}")

    def cmd_news(ctx, arg):
        cfg = _read_cfg(manager, plugin_name)
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
                lines.append(f"{idx}. {title}\n   {link}")
            return PluginResult(handled=True, response="\n".join(lines))
        except Exception as exc:
            return PluginResult(handled=True, response=f"新闻解析失败: {exc}")

    def rule_weather(ctx, match):
        city = (match.group(1) or "").strip() if match else ""
        return cmd_weather(ctx, city)

    def rule_wiki(ctx, match):
        term = (match.group(1) or "").strip() if match else ""
        return cmd_wiki(ctx, term)

    def rule_news(ctx, match):
        term = (match.group(1) or "").strip() if match else ""
        return cmd_news(ctx, term)

    registry.register_command("weather", cmd_weather, plugin_name)
    registry.register_command("wiki", cmd_wiki, plugin_name)
    registry.register_command("news", cmd_news, plugin_name)
    registry.register_regex_rule(r"天气\s*[:：]?\s*(.+)", rule_weather, plugin_name, flags=re.IGNORECASE, priority=45)
    registry.register_regex_rule(r"百科\s*[:：]?\s*(.+)", rule_wiki, plugin_name, flags=re.IGNORECASE, priority=45)
    registry.register_regex_rule(r"新闻\s*[:：]?\s*(.+)", rule_news, plugin_name, flags=re.IGNORECASE, priority=45)
