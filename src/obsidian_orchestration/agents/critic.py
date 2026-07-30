"""Evaluation Critic agent node."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def evaluation_critic(state: GraphState, vault: VaultAdapter) -> dict:
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Critic received no valid REQUEST"}

    review = (
        f"### Critic Review — {req.task.objective}\n"
        f"- **Summary judgment**: Structured request received\n"
        f"- **Strengths**: Clear objective\n"
        f"- **Critical issues**: None in demo mode\n"
        f"- **Required fixes**: None\n"
        f"- **Final verdict**: **Accept**\n"
    )
    path = f"Research/Experiments/critic_{req.task.id}.md"
    try:
        vault.write(path, review)
    except Exception:
        path = f"(write-failed)/critic_{req.task.id}.md"

    inform = req.reply(
        from_agent=AgentName.EVALUATION_CRITIC,
        performative=Performative.INFORM,
        payload={"review": review, "verdict": "Accept", "vault_path": path},
        confidence=0.9,
        rationale="Rubric applied",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = [path]
    return out
