"""Prompt Architect agent node."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def prompt_architect(state: GraphState, vault: VaultAdapter) -> dict:
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Architect received no valid REQUEST"}

    objective = req.task.objective
    changelog = (
        f"### Prompt Architect Result\n"
        f"- **Objective**: {objective}\n"
        f"- **Action**: Would archive previous version and write vNext\n"
        f"- **Suggested tests**: Invoke Scout with weak sources; expect confidence flags\n"
    )
    path = f"Agents/archive/architect_result_{req.task.id}.md"
    vault.write(path, changelog)

    inform = req.reply(
        from_agent=AgentName.PROMPT_ARCHITECT,
        performative=Performative.INFORM,
        payload={"report": changelog, "vault_path": path},
        confidence=0.8,
        rationale="Prompt change plan prepared (demo implementation)",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = list(set((state.get("vault_refs") or []) + [path]))
    return out
