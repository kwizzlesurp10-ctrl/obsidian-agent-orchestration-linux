"""Allowed research tools: web_search, fetch_url, save_note."""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from obsidian_orchestration.vault_adapter import VaultAdapter

USER_AGENT = (
    "ObsidianResearchAgent/0.3 (+local; citation-backed research; httpx)"
)


class ToolError(RuntimeError):
    pass


def web_search(query: str, *, max_results: int = 5, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Discover candidate URLs (DuckDuckGo HTML). Never invents results on hard failure."""
    query = (query or "").strip()
    if not query:
        raise ToolError("web_search requires a non-empty query")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
    }
    url = "https://html.duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.post(url, data={"q": query})
            r.raise_for_status()
            html = r.text
    except Exception as e:
        raise ToolError(f"web_search failed: {e}") from e

    results: list[dict[str, Any]] = []
    # DDG result anchors: class result__a
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    ):
        href = unescape(m.group(1))
        title = re.sub(r"<[^>]+>", "", unescape(m.group(2))).strip()
        href = _unwrap_ddg_redirect(href)
        if not href.startswith("http"):
            continue
        # snippet nearby
        snippet = ""
        results.append({"url": href, "title": title, "snippet": snippet})
        if len(results) >= max_results:
            break

    # Fallback pattern
    if not results:
        for m in re.finditer(r'uddg=([^&"]+)', html):
            href = unquote(m.group(1))
            if href.startswith("http"):
                results.append({"url": href, "title": "", "snippet": ""})
            if len(results) >= max_results:
                break

    return results


def _unwrap_ddg_redirect(href: str) -> str:
    if "duckduckgo.com/l/?" in href or "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return href


def fetch_url(url: str, *, timeout: float = 25.0, max_chars: int = 12_000) -> dict[str, Any]:
    """Fetch a URL and return extracted text. Only call for discovered URLs."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ToolError(f"fetch_url rejects non-http URL: {url!r}")

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            body = r.text
            final_url = str(r.url)
    except Exception as e:
        raise ToolError(f"fetch_url failed for {url}: {e}") from e

    title = ""
    tm = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.I | re.S)
    if tm:
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", unescape(tm.group(1)))).strip()

    text = body
    if "html" in ctype.lower() or "<html" in body[:500].lower():
        text = _html_to_text(body)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…[truncated]"

    return {
        "url": final_url,
        "final_url": final_url,
        "title": title,
        "content_type": ctype,
        "text": text,
        "char_count": len(text),
    }


def _html_to_text(html: str) -> str:
    # Drop script/style
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n\n", html)
    html = re.sub(r"(?i)</(div|h[1-6]|li|tr)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_note(
    vault: VaultAdapter,
    path: str,
    content: str,
    *,
    mode: str = "write",
) -> str:
    """Persist a note into the Obsidian vault. Unlimited within session."""
    path = path.lstrip("/")
    if mode == "append":
        try:
            vault.append(path, content if content.startswith("\n") else "\n" + content)
        except Exception:
            # fallback read+write
            try:
                prev = vault.read(path)
            except Exception:
                prev = ""
            vault.write(path, prev + (content if content.startswith("\n") else "\n" + content))
    else:
        vault.write(path, content)
    return path
