"""Shared agent node helpers and graph state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from obsidian_orchestration.schemas.iacp import IACPMessage


def _merge_messages(left: list[IACPMessage], right: list[IACPMessage]) -> list[IACPMessage]:
    return (left or []) + (right or [])


def _merge_refs(left: list[str], right: list[str]) -> list[str]:
    return list(dict.fromkeys((left or []) + (right or [])))


class GraphState(TypedDict, total=False):
    messages: Annotated[list[IACPMessage], _merge_messages]
    vault_refs: Annotated[list[str], _merge_refs]
    current_task_objective: str
    final_output: str | None
    status: str
    next_agent: str | None
    sub_queries: list[str]
    scout_results: Annotated[list[dict[str, Any]], operator.add]


def last_message(state: GraphState) -> IACPMessage | None:
    msgs = state.get("messages") or []
    return msgs[-1] if msgs else None


def append_message(state: GraphState, msg: IACPMessage) -> dict[str, Any]:
    return {"messages": [msg]}
