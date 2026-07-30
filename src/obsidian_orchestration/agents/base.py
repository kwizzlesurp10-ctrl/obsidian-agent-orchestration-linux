"""Shared agent node helpers."""

from __future__ import annotations

from typing import Any, TypedDict

from obsidian_orchestration.schemas.iacp import IACPMessage
from obsidian_orchestration.vault_adapter import VaultAdapter


class GraphState(TypedDict, total=False):
    messages: list[IACPMessage]
    vault_refs: list[str]
    current_task_objective: str
    final_output: str | None
    status: str
    next_agent: str | None


def last_message(state: GraphState) -> IACPMessage | None:
    msgs = state.get("messages") or []
    return msgs[-1] if msgs else None


def append_message(state: GraphState, msg: IACPMessage) -> dict[str, Any]:
    msgs = list(state.get("messages") or [])
    msgs.append(msg)
    return {"messages": msgs}
