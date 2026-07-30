"""Vault adapter interface + live Obsidian Local REST API / Tunnel client."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

import httpx


class VaultAdapter(ABC):
    @abstractmethod
    def list(self, path: str = "") -> list[str]:
        ...

    @abstractmethod
    def read(self, path: str) -> str:
        ...

    @abstractmethod
    def write(self, path: str, content: str) -> None:
        ...

    @abstractmethod
    def append(self, path: str, content: str) -> None:
        ...

    @abstractmethod
    def search(self, query: str) -> list[dict[str, Any]]:
        ...


class InMemoryVault(VaultAdapter):
    """Dict-backed vault for demos and unit tests."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    def list(self, path: str = "") -> list[str]:
        if not path:
            return sorted({p.split("/")[0] for p in self._files})
        prefix = path.rstrip("/") + "/"
        return sorted(
            {
                p[len(prefix) :].split("/")[0]
                for p in self._files
                if p.startswith(prefix)
            }
        )

    def read(self, path: str) -> str:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]

    def write(self, path: str, content: str) -> None:
        self._files[path] = content

    def append(self, path: str, content: str) -> None:
        self._files[path] = self._files.get(path, "") + content

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        hits = []
        for path, body in self._files.items():
            if q in path.lower() or q in body.lower():
                hits.append({"path": path, "snippet": body[:200]})
        return hits


class ObsidianTunnelVault(VaultAdapter):
    """Live adapter for Obsidian Local REST API (the backend behind Obsidian Tunnel).

    Environment variables:
      OBSIDIAN_API_URL   default https://127.0.0.1:27124
      OBSIDIAN_API_KEY   Bearer token from Local REST API plugin settings

    When running locally, point at 127.0.0.1. When using a public tunnel, point
    at the tunnel URL instead.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = (base_url or os.getenv("OBSIDIAN_API_URL", "https://127.0.0.1:27124")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("OBSIDIAN_API_KEY", "")
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "text/markdown", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )

    def list(self, path: str = "") -> list[str]:
        suffix = f"/vault/{quote(path.strip('/'), safe='/')}/" if path.strip("/") else "/vault/"
        with self._client() as c:
            r = c.get(suffix)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return [item.get("path", item) if isinstance(item, dict) else str(item) for item in data]
            if isinstance(data, dict) and "files" in data:
                return list(data["files"])
            return []

    def read(self, path: str) -> str:
        with self._client() as c:
            r = c.get(f"/vault/{quote(path, safe='/')}")
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if "application/json" in ctype:
                data = r.json()
                return data.get("content", data.get("data", str(data)))
            return r.text

    def write(self, path: str, content: str) -> None:
        with self._client() as c:
            r = c.put(f"/vault/{quote(path, safe='/')}", content=content.encode("utf-8"))
            r.raise_for_status()

    def append(self, path: str, content: str) -> None:
        with self._client() as c:
            r = c.post(f"/vault/{quote(path, safe='/')}", content=content.encode("utf-8"))
            r.raise_for_status()

    def search(self, query: str) -> list[dict[str, Any]]:
        with self._client() as c:
            try:
                r = c.post("/search/simple/", json={"query": query})
                r.raise_for_status()
                data = r.json()
            except Exception:
                r = c.get("/search/simple/", params={"query": query})
                r.raise_for_status()
                data = r.json()

        hits: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    hits.append(
                        {
                            "path": item.get("filename") or item.get("path") or "",
                            "snippet": str(item.get("matches") or item.get("score") or "")[:300],
                        }
                    )
                else:
                    hits.append({"path": str(item), "snippet": ""})
        return hits


def get_default_vault() -> VaultAdapter:
    """Prefer live tunnel when OBSIDIAN_API_KEY is set; otherwise in-memory."""
    if os.getenv("OBSIDIAN_API_KEY") or os.getenv("OBSIDIAN_USE_LIVE") == "1":
        return ObsidianTunnelVault()
    return InMemoryVault()
