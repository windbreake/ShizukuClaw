# -*- coding: utf-8 -*-
"""Selective web crawler plugin with a Kemono-focused crawler mode."""

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, List, Tuple
from urllib.parse import urljoin, urlparse

import requests

from app.plugin_framework.base import PluginResult

PLUGIN_NAME = "crawler.kemono"
PLUGIN_META = {
    "name": "crawler.kemono",
    "version": "0.2.0",
    "description": "Selective web content crawler + Kemono post crawler",
    "author": "ShizukuNyaBot",
    "dependencies": ["builtin.basic"]
}


def _load_config() -> dict:
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(cfg_path):
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


@dataclass
class CrawlSummary:
    url: str
    title: str
    paragraphs: List[str]


class SelectiveCrawler:
    def __init__(self, plugin_name: str, plugin_manager):
        self.plugin_name = plugin_name
        self.plugin_manager = plugin_manager
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def _allow_url(self, url: str) -> Tuple[bool, str]:
        return self.plugin_manager.validate_url_for_plugin(self.plugin_name, url)

    def _safe_get(self, url: str, timeout: int = 20, verify: bool = True):
        try:
            return self.session.get(url, timeout=timeout, verify=verify)
        except requests.exceptions.SSLError:
            return self.session.get(url, timeout=timeout, verify=False)

    def crawl_selectively(self, url: str, max_paragraphs: int = 8) -> CrawlSummary:
        cfg = _load_config()
        allowed, reason = self._allow_url(url)
        if not allowed:
            raise ValueError(reason)

        timeout = int(cfg.get("request_timeout", 20))
        verify = bool(cfg.get("use_ssl_verify", True))
        response = self._safe_get(url, timeout=timeout, verify=verify)
        response.raise_for_status()
        html = response.text

        title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = unescape(title_match.group(1).strip()) if title_match else "(no title)"

        blocks = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = []
        for block in blocks:
            text = re.sub(r"<[^>]+>", "", block)
            text = unescape(re.sub(r"\s+", " ", text)).strip()
            if text:
                cleaned.append(text)
            if len(cleaned) >= max_paragraphs:
                break

        if not cleaned:
            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", unescape(text)).strip()
            if text:
                cleaned = [text[:1200]]

        return CrawlSummary(url=url, title=title[:200], paragraphs=cleaned)


class KemonoCrawler:
    def __init__(self, plugin_name: str, plugin_manager):
        self.plugin_name = plugin_name
        self.plugin_manager = plugin_manager
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/json,*/*;q=0.8",
                "Referer": "https://kemono.su/",
            }
        )

    def _ensure_kemono_domain(self, url: str) -> None:
        allowed, reason = self.plugin_manager.validate_url_for_plugin(self.plugin_name, url)
        if not allowed:
            raise ValueError(reason)

        host = (urlparse(url).hostname or "").lower()
        if host not in ("kemono.su", "kemono.cr"):
            raise ValueError("Only kemono.su / kemono.cr is allowed for kemono crawler")

    @staticmethod
    def _parse_post_url(post_url: str) -> Tuple[str, str, str, str]:
        parsed = urlparse(post_url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 5 or parts[1] != "user" or parts[3] != "post":
            raise ValueError(f"Unsupported Kemono post URL: {post_url}")
        service = parts[0]
        user_id = parts[2]
        post_id = parts[4]
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin, service, user_id, post_id

    def _request_json(self, url: str, timeout: int, verify: bool) -> dict:
        try:
            response = self.session.get(url, timeout=timeout, verify=verify)
        except requests.exceptions.SSLError:
            response = self.session.get(url, timeout=timeout, verify=False)
        response.raise_for_status()
        return response.json()

    def _extract_post_from_next_data(self, html_text: str) -> dict:
        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return {}
        raw = unescape(match.group(1))
        payload = json.loads(raw)
        return self._find_post_like_node(payload) or {}

    def _find_post_like_node(self, obj: Any) -> dict:
        if isinstance(obj, dict):
            if "attachments" in obj and isinstance(obj.get("attachments"), list):
                return obj
            if "post" in obj and isinstance(obj["post"], dict):
                candidate = obj["post"]
                if "attachments" in candidate or "file" in candidate:
                    return candidate
            for value in obj.values():
                found = self._find_post_like_node(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self._find_post_like_node(item)
                if found:
                    return found
        return {}

    @staticmethod
    def _collect_media(post_data: dict, origin: str, allowed_ext: List[str]) -> List[dict]:
        out: List[dict] = []
        candidates = []
        if isinstance(post_data.get("file"), dict):
            candidates.append(post_data["file"])
        if isinstance(post_data.get("attachments"), list):
            candidates.extend([x for x in post_data["attachments"] if isinstance(x, dict)])

        seen = set()
        for item in candidates:
            raw_url = item.get("path") or item.get("url") or ""
            if not raw_url:
                continue
            full_url = raw_url if str(raw_url).startswith("http") else urljoin(origin, raw_url)
            if full_url in seen:
                continue
            seen.add(full_url)
            name = item.get("name") or os.path.basename(urlparse(full_url).path) or f"media_{len(out)+1}.bin"
            if allowed_ext:
                ext = os.path.splitext(name)[1].lower()
                if ext and ext not in allowed_ext:
                    continue
            out.append({"name": name, "url": full_url})
        return out

    def fetch_post_media(self, post_url: str) -> dict:
        cfg = _load_config()
        self._ensure_kemono_domain(post_url)
        origin, service, user_id, post_id = self._parse_post_url(post_url)
        timeout = int(cfg.get("request_timeout", 20))
        verify = bool(cfg.get("use_ssl_verify", True))
        mirrors = cfg.get("kemono_mirrors", ["https://kemono.su", "https://kemono.cr"])
        if not isinstance(mirrors, list) or not mirrors:
            mirrors = ["https://kemono.su", "https://kemono.cr"]
        allowed_ext = cfg.get("allowed_file_extensions", [])
        if not isinstance(allowed_ext, list):
            allowed_ext = []
        allowed_ext = [str(x).lower() for x in allowed_ext]

        origins = [origin] + [m for m in mirrors if m != origin]
        last_error = ""
        for base in origins:
            try:
                api_url = f"{base}/api/v1/{service}/user/{user_id}/post/{post_id}"
                data = self._request_json(api_url, timeout=timeout, verify=verify)
                media = self._collect_media(data, base, allowed_ext)
                if media:
                    return {"source": base, "post_id": post_id, "media": media}

                page_url = f"{base}/{service}/user/{user_id}/post/{post_id}"
                try:
                    html_resp = self.session.get(page_url, timeout=timeout, verify=verify)
                except requests.exceptions.SSLError:
                    html_resp = self.session.get(page_url, timeout=timeout, verify=False)
                html = html_resp.text
                data2 = self._extract_post_from_next_data(html)
                media2 = self._collect_media(data2, base, allowed_ext)
                if media2:
                    return {"source": base, "post_id": post_id, "media": media2}
            except Exception as exc:
                last_error = str(exc)
                continue

        raise RuntimeError(f"No media found from mirrors. Last error: {last_error}")


def on_startup():
    print("[crawler.kemono] startup")


def on_shutdown():
    print("[crawler.kemono] shutdown")


def register(registry, manager):
    selective = SelectiveCrawler(PLUGIN_NAME, manager)
    kemono = KemonoCrawler(PLUGIN_NAME, manager)

    manager.ensure_plugin_policy(
        PLUGIN_NAME,
        {
            "enabled": True,
            "allow_network": True,
            "allowed_domains": ["kemono.su", "kemono.cr", "example.com"],
            "allowed_commands": ["crawl", "kemono_crawl"],
            "max_execution_ms": 30000,
        },
        persist=False,
    )

    def cmd_crawl(ctx, arg):
        cfg = _load_config()
        parts = (arg or "").strip().split()
        if not parts:
            return PluginResult(handled=True, response="Usage: /crawl <url> [max_paragraphs]")

        url = parts[0]
        max_paragraphs = int(cfg.get("default_max_paragraphs", 8))
        if len(parts) > 1:
            try:
                max_paragraphs = max(1, min(20, int(parts[1])))
            except Exception:
                pass

        summary = selective.crawl_selectively(url, max_paragraphs=max_paragraphs)
        body = "\n".join([f"- {p}" for p in summary.paragraphs[:max_paragraphs]])
        return PluginResult(
            handled=True,
            response=(
                f"[crawl] title: {summary.title}\n"
                f"[crawl] url: {summary.url}\n"
                f"[crawl] extracted:\n{body if body else '- (empty)'}"
            ),
        )

    def cmd_kemono_crawl(ctx, arg):
        post_url = (arg or "").strip()
        if not post_url:
            return PluginResult(handled=True, response="Usage: /kemono_crawl <kemono_post_url>")

        result = kemono.fetch_post_media(post_url)
        media = result.get("media", [])
        preview_lines = []
        for item in media[:10]:
            preview_lines.append(f"- {item['name']} | {item['url']}")

        more = ""
        if len(media) > 10:
            more = f"\n... and {len(media)-10} more"

        return PluginResult(
            handled=True,
            response=(
                f"[kemono] source: {result.get('source')}\n"
                f"[kemono] post_id: {result.get('post_id')}\n"
                f"[kemono] media_count: {len(media)}\n"
                f"[kemono] preview:\n" + ("\n".join(preview_lines) if preview_lines else "- (none)") + more
            ),
        )

    registry.register_command("crawl", cmd_crawl, PLUGIN_NAME)
    registry.register_command("kemono_crawl", cmd_kemono_crawl, PLUGIN_NAME)
