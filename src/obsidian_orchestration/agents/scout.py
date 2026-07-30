"""Research Scout agent node."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def research_scout(state: GraphState, vault: VaultAdapter) -> dict:
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Scout received no valid REQUEST"}

    objective = req.task.objective
    hits = vault.search(objective)
    report_lines = [
        f"### Scout Report — {objective}",
        f"- **Query**: {objective}",
        f"- **Vault hits**: {len(hits)}",
    ]
    for h in hits[:5]:
        report_lines.append(f"  - `{h['path']}`: {h.get('snippet', '')[:120]}")
    if not hits:
        report_lines.append("- **Gaps**: No vault matches; external research recommended")
    report_lines.append("- **Recommended next action**: Synthesize or escalate to Critic")
    report = "\n".join(report_lines)

    # Blackboard write
    path = f"Research/Inbox/scout_{req.task.id}.md"
    vault.write(path, report)

    inform = req.reply(
        from_agent=AgentName.RESEARCH_SCOUT,
        performative=Performative.INFORM,
        payload={"report": report, "vault_path": path, "hit_count": len(hits)},
        confidence=0.75 if hits else 0.4,
        rationale="Vault search completed",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = list(set((state.get("vault_refs") or []) + [path]))
    return out
