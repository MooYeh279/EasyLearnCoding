"""Built-in tools for the agent loop: web_search and web_fetch."""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from logger import get_logger

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = get_logger("tools")

# ── Constants ──────────────────────────────────────────────────────────
WEB_FETCH_MAX_CHARS = 8000
WEB_SEARCH_MAX_RESULTS = 5
WEB_SEARCH_TIMEOUT = 15
WEB_FETCH_TIMEOUT = 15
WEB_FETCH_MAX_REDIRECTS = 5
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web. Returns titles, URLs, and snippets. "
                "Use this to find current information, documentation, or answers to factual questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-10, default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch and extract readable content from a URL. "
                "Use this to read the full content of a page found via web_search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch content from",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


def get_tool_definitions() -> list[dict]:
    """Return tool definitions in OpenAI function-calling format."""
    return _TOOL_DEFINITIONS


# ── HTML helpers (from nanobot reference) ──────────────────────────────

def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL scheme and domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


def _html_to_markdown(html_content: str) -> str:
    """Convert HTML to markdown (simplified, no external dep)."""
    text = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        lambda m: f'[{_strip_tags(m[2])}]({m[1]})',
        html_content, flags=re.I,
    )
    text = re.sub(
        r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
        lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n',
        text, flags=re.I,
    )
    text = re.sub(
        r'<li[^>]*>([\s\S]*?)</li>',
        lambda m: f'\n- {_strip_tags(m[1])}',
        text, flags=re.I,
    )
    text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
    text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
    return _normalize(_strip_tags(text))


# ── web_search ─────────────────────────────────────────────────────────

def _format_search_results(query: str, items: list[dict[str, Any]], n: int) -> list[dict]:
    """Format raw search results into structured output."""
    results = []
    for item in items[:n]:
        title = _normalize(_strip_tags(item.get("title", "")))
        snippet = _normalize(_strip_tags(item.get("content", item.get("body", ""))))
        results.append({
            "title": title,
            "url": item.get("url", item.get("href", "")),
            "snippet": snippet,
        })
    return results


def _search_duckduckgo(query: str, n: int) -> list[dict]:
    """Search using DuckDuckGo (synchronous, run in thread by caller)."""
    try:
        with DDGS(timeout=WEB_SEARCH_TIMEOUT) as ddgs:
            raw = list(ddgs.text(query, max_results=n))
            return _format_search_results(query, raw, n)
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
        return []


async def _search_tavily(query: str, n: int) -> list[dict]:
    """Search using Tavily API."""
    _, api_key, _ = _read_db_search_settings()
    if not api_key:
        logger.warning("TAVILY_API_KEY not set, falling back to DuckDuckGo")
        return await asyncio.to_thread(_search_duckduckgo, query, n)

    try:
        async with httpx.AsyncClient(timeout=WEB_SEARCH_TIMEOUT) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query, "max_results": n},
            )
            r.raise_for_status()
        return _format_search_results(query, r.json().get("results", []), n)
    except Exception as e:
        logger.warning("Tavily search failed: %s, falling back to DuckDuckGo", e)
        return await asyncio.to_thread(_search_duckduckgo, query, n)


def _read_db_search_settings() -> tuple[str, str, bool]:
    """Read web search settings from DB.
    Falls back to environment variables if DB has no value.
    Returns (provider, tavily_api_key, enabled).
    """
    try:
        from database import SessionLocal
        from models import AppSetting
        db = SessionLocal()
        try:
            rows = {r.key: r.value for r in db.query(AppSetting).filter(
                AppSetting.key.in_({"web_search_provider", "tavily_api_key", "web_search_enabled"})
            ).all()}
        finally:
            db.close()
        provider = rows.get("web_search_provider") or os.environ.get("WEB_SEARCH_PROVIDER", "")
        api_key = rows.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY", "")
        enabled = rows.get("web_search_enabled", "").lower() == "true"
        return provider.strip().lower(), api_key.strip(), enabled
    except Exception:
        return (
            os.environ.get("WEB_SEARCH_PROVIDER", "").strip().lower(),
            os.environ.get("TAVILY_API_KEY", "").strip(),
            False,
        )


def _get_search_provider() -> str:
    """Return configured search provider name."""
    provider, _, _ = _read_db_search_settings()
    return provider or "duckduckgo"


def is_web_search_enabled() -> bool:
    """Return whether web search is globally enabled."""
    _, _, enabled = _read_db_search_settings()
    return enabled


async def web_search(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> list[dict]:
    """Search the web and return structured results.

    Provider is determined by WEB_SEARCH_PROVIDER env var:
    - 'duckduckgo' (default): no API key needed
    - 'tavily': requires TAVILY_API_KEY env var
    """
    n = min(max(max_results, 1), 10)
    provider = _get_search_provider()

    if provider == "tavily":
        return await _search_tavily(query, n)

    return await asyncio.to_thread(_search_duckduckgo, query, n)


# ── web_fetch ──────────────────────────────────────────────────────────

async def _fetch_and_extract(url: str, max_chars: int) -> dict:
    """Fetch URL and extract readable content. Returns result dict."""
    is_valid, error_msg = _validate_url(url)
    if not is_valid:
        return {"error": f"Invalid URL: {error_msg}", "url": url}

    try:
        original_domain = urlparse(url).netloc
        async with httpx.AsyncClient(
            timeout=WEB_FETCH_TIMEOUT,
            follow_redirects=True,
            max_redirects=WEB_FETCH_MAX_REDIRECTS,
        ) as client:
            response = await client.get(url, headers={"User-Agent": _USER_AGENT})
            response.raise_for_status()

        # Cross-domain redirect check
        final_domain = urlparse(str(response.url)).netloc
        if original_domain and final_domain and final_domain != original_domain:
            return {"error": f"Blocked cross-domain redirect from {original_domain} to {final_domain}", "url": url}

        # Extract content based on content type
        ctype = response.headers.get("content-type", "")
        text = _extract_content(response.text, ctype)

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]

        return {
            "url": url,
            "final_url": str(response.url),
            "truncated": truncated,
            "text": text,
        }

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "url": url}
    except httpx.TimeoutException:
        return {"error": "Timeout", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


def _extract_content(raw: str, content_type: str) -> str:
    """Extract readable text from response based on content type."""
    if "application/json" in content_type:
        try:
            return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return raw

    if "text/html" in content_type or raw[:256].lower().startswith(("<!doctype", "<html")):
        return _extract_html(raw)

    return _normalize(raw)


def _extract_html(html_text: str) -> str:
    """Extract main content from HTML using readability."""
    try:
        from readability import Document
        doc = Document(html_text)
        title = doc.title()
        content = _html_to_markdown(doc.summary())
        return f"# {title}\n\n{content}" if title else content
    except Exception:
        logger.debug("readability failed, falling back to tag stripping")
        return _normalize(_strip_tags(html_text))


async def web_fetch(url: str, max_chars: int = WEB_FETCH_MAX_CHARS) -> str:
    """Fetch a URL and return extracted text content, truncated.

    Blocks cross-domain redirects to prevent open redirect abuse.
    """
    result = await _fetch_and_extract(url, max_chars)

    if "error" in result:
        logger.warning("web_fetch %s: %s", result.get("url", url), result["error"])
        return f"[{result['error']} when fetching {result.get('url', url)}]"

    text = result["text"]
    if result.get("truncated"):
        text += "\n\n[Content truncated]"
    return text


TOOL_MAP = {
    "web_search": web_search,
    "web_fetch": web_fetch,
}
