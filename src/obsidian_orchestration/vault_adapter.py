"""Vault adapter interface.

In production this talks to the Obsidian Local REST API / Tunnel.
The default implementation is an in-memory blackboard so demos and tests
run without a live tunnel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
    """Simple dict-backed vault for demos and unit tests."""

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
    """Adapter that calls the live Obsidian Tunnel connected tools.

    In this remote Grok environment the tools are available as
    `obsidian_tunnel___vault_*`. When running as a standalone Python
    service you would replace the method bodies with HTTP calls to the
    Local REST API (https://127.0.0.1:27124) using the bearer token.
    """

    def __init__(self, base_url: str = "https://127.0.0.1:27124", api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def list(self, path: str = "") -> list[str]:
        raise NotImplementedError(
            "Wire to obsidian_tunnel___vault_list or Local REST API GET /vault/"
        )

    def read(self, path: str) -> str:
        raise NotImplementedError(
            "Wire to obsidian_tunnel___vault_read or Local REST API GET /vault/{path}"
        )

    def write(self, path: str, content: str) -> None:
        raise NotImplementedError(
            "Wire to obsidian_tunnel___vault_write or Local REST API PUT /vault/{path}"
        )

    def append(self, path: str, content: str) -> None:
        raise NotImplementedError(
            "Wire to obsidian_tunnel___vault_append or Local REST API POST /vault/{path}"
        )

    def search(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Wire to obsidian_tunnel___search_simple or Local REST API search endpoint"
        )
