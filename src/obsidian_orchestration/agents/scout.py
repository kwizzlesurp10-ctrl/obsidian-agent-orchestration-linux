"""Research Scout agent node (single + parallel worker)."""

from __future__ import annotations

from typing import Any

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def _run_search(vault: VaultAdapter, query: str) -> tuple[str, str, int]:
    hits = vault.search(query)
    lines = [
        f"### Scout Report — {query}",
        f"- **Query**: {query}",
        f"- **Vault hits**: {len(hits)}",
    ]
    for h in hits[:5]:
        lines.append(f"  - `{h.get('path', '')}`: {str(h.get('snippet', ''))[:120]}")
    if not hits:
        lines.append("- **Gaps**: No vault matches; external research recommended")
    lines.append("- **Recommended next action**: Synthesize or escalate to Critic")
    report = "\n".join(lines)
    path = f"Research/Inbox/scout_{abs(hash(query)) % 10_000_000}.md"
    try:
        vault.write(path, report)
    except Exception:
        path = f"(write-failed)/scout_{abs(hash(query)) % 10_000_000}.md"
    return report, path, len(hits)


def research_scout(state: GraphState, vault: VaultAdapter) -> dict:
    """Single-query scout (sequential path)."""
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Scout received no valid REQUEST"}

    objective = req.task.objective
    report, path, hit_count = _run_search(vault, objective)

    inform = req.reply(
        from_agent=AgentName.RESEARCH_SCOUT,
        performative=Performative.INFORM,
        payload={"report": report, "vault_path": path, "hit_count": hit_count},
        confidence=0.75 if hit_count else 0.4,
        rationale="Vault search completed",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = [path]
    return out


def research_scout_worker(state: GraphState, vault: VaultAdapter) -> dict:
    """Parallel fan-out worker: expects state['current_task_objective'] to be one sub-query."""
    query = state.get("current_task_objective") or ""
    report, path, hit_count = _run_search(vault, query)
    result: dict[str, Any] = {
        "query": query,
        "report": report,
        "vault_path": path,
        "hit_count": hit_count,
    }
    return {
        "scout_results": [result],
        "vault_refs": [path],
    }
