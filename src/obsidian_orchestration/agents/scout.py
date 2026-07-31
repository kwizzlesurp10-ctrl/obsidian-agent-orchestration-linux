"""Research Scout agent node (vault search + layered web research agent)."""

from __future__ import annotations

import os
from typing import Any

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def _vault_search_report(vault: VaultAdapter, query: str) -> tuple[str, str, int]:
    hits = vault.search(query)
    lines = [
        f"### Scout Vault Pass — {query}",
        f"- **Query**: {query}",
        f"- **Vault hits**: {len(hits)}",
    ]
    for h in hits[:5]:
        lines.append(f"  - `{h.get('path', '')}`: {str(h.get('snippet', ''))[:120]}")
    if not hits:
        lines.append("- **Gaps**: No vault matches")
    report = "\n".join(lines)
    path = f"Research/Inbox/scout_vault_{abs(hash(query)) % 10_000_000}.md"
    try:
        vault.write(path, report)
    except Exception:
        path = f"(write-failed)/scout_vault_{abs(hash(query)) % 10_000_000}.md"
    return report, path, len(hits)


def _web_research_enabled() -> bool:
    """Default ON. Set RESEARCH_AGENT=0 to disable web OODA path."""
    return os.getenv("RESEARCH_AGENT", "1") not in {"0", "false", "False", "no"}


def _run_layered_research(vault: VaultAdapter, objective: str) -> tuple[str, str, dict[str, Any]]:
    from obsidian_orchestration.research.agent import run_research

    search_budget = int(os.getenv("RESEARCH_SEARCH_BUDGET", "8"))
    fetch_budget = int(os.getenv("RESEARCH_FETCH_BUDGET", "6"))
    brief = run_research(
        objective,
        vault,
        search_budget=search_budget,
        fetch_budget=fetch_budget,
    )
    validation = brief.validation.as_yes_no()
    checklist = "\n".join(f"  - {k}: {v}" for k, v in validation.items())
    report = (
        f"### Layered Research Agent — {brief.status}\n"
        f"- **Goal**: {brief.goal}\n"
        f"- **Summary**: {brief.summary}\n"
        f"- **Findings**: {len(brief.findings)}\n"
        f"- **Fetched sources**: {sum(1 for s in brief.sources if s.fetched)}\n"
        f"- **Notes**: `{brief.notes_path}`\n"
        f"- **Brief**: `{brief.brief_path}`\n"
        f"- **VALIDATION**:\n{checklist}\n"
        f"- **Emit**: `{brief.status}`\n"
        f"```json\n{brief.to_compact_json()}\n```\n"
    )
    path = brief.brief_path or f"Research/Sessions/unknown/brief.md"
    meta = {
        "status": brief.status,
        "findings": len(brief.findings),
        "brief_path": brief.brief_path,
        "notes_path": brief.notes_path,
        "validation": validation,
        "json": brief.to_compact_json(),
    }
    return report, path, meta


def _run_search(vault: VaultAdapter, query: str) -> tuple[str, str, int, dict[str, Any]]:
    vault_report, vault_path, hit_count = _vault_search_report(vault, query)
    meta: dict[str, Any] = {"vault_hits": hit_count, "mode": "vault-only"}

    if not _web_research_enabled():
        return vault_report, vault_path, hit_count, meta

    try:
        web_report, web_path, web_meta = _run_layered_research(vault, query)
        report = vault_report + "\n\n" + web_report
        meta = {**meta, "mode": "vault+layered-research", **web_meta}
        # Prefer web brief path as primary artifact
        return report, web_path, hit_count + int(web_meta.get("findings") or 0), meta
    except Exception as e:
        report = vault_report + f"\n\n### Layered research error\n- {e}\n"
        meta = {**meta, "mode": "vault-only", "research_error": str(e)}
        return report, vault_path, hit_count, meta


def research_scout(state: GraphState, vault: VaultAdapter) -> dict:
    """Single-query scout (sequential path)."""
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Scout received no valid REQUEST"}

    objective = req.task.objective
    report, path, hit_count, meta = _run_search(vault, objective)

    inform = req.reply(
        from_agent=AgentName.RESEARCH_SCOUT,
        performative=Performative.INFORM,
        payload={
            "report": report,
            "vault_path": path,
            "hit_count": hit_count,
            "research": meta,
        },
        confidence=0.8 if meta.get("status") == "FINAL" else (0.75 if hit_count else 0.45),
        rationale="Vault search + layered research agent"
        if meta.get("mode") == "vault+layered-research"
        else "Vault search completed",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = [path]
    return out


def research_scout_worker(state: GraphState, vault: VaultAdapter) -> dict:
    """Parallel fan-out worker: expects state['current_task_objective'] to be one sub-query."""
    query = state.get("current_task_objective") or ""
    # Parallel workers stay vault-light unless RESEARCH_AGENT_PARALLEL=1
    if os.getenv("RESEARCH_AGENT_PARALLEL", "0") in {"1", "true", "True"}:
        report, path, hit_count, meta = _run_search(vault, query)
    else:
        report, path, hit_count = _vault_search_report(vault, query)
        meta = {"mode": "vault-only-parallel", "vault_hits": hit_count}
    result: dict[str, Any] = {
        "query": query,
        "report": report,
        "vault_path": path,
        "hit_count": hit_count,
        "research": meta,
    }
    return {
        "scout_results": [result],
        "vault_refs": [path],
    }
