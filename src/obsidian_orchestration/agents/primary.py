"""Primary (supervisor) agent node."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import (
    AgentName,
    IACPMessage,
    Performative,
    Priority,
    TaskEnvelope,
    TaskType,
)
from obsidian_orchestration.vault_adapter import VaultAdapter


def primary_plan(state: GraphState, vault: VaultAdapter) -> dict:
    """Decompose the user objective and decide the next specialist."""
    objective = state.get("current_task_objective") or "No objective provided"
    objective_l = objective.lower()

    # Simple routing heuristic (replace with LLM call in production)
    if any(k in objective_l for k in ("search", "find", "scout", "research", "source")):
        next_agent = AgentName.RESEARCH_SCOUT
        task_type = TaskType.SCOUT
    elif any(k in objective_l for k in ("prompt", "system prompt", "version", "architect")):
        next_agent = AgentName.PROMPT_ARCHITECT
        task_type = TaskType.DESIGN_PROMPT
    elif any(k in objective_l for k in ("critique", "review", "evaluate", "quality")):
        next_agent = AgentName.EVALUATION_CRITIC
        task_type = TaskType.CRITIQUE
    else:
        # Default: scout first
        next_agent = AgentName.RESEARCH_SCOUT
        task_type = TaskType.SCOUT

    task = TaskEnvelope(
        type=task_type,
        objective=objective,
        constraints=["Prefer vault sources", "Return structured output"],
        priority=Priority.HIGH,
        context_refs=state.get("vault_refs") or [],
    )
    req = IACPMessage(
        from_agent=AgentName.PRIMARY,
        to_agent=next_agent,
        performative=Performative.REQUEST,
        task=task,
        confidence=0.85,
        rationale=f"Routing to {next_agent.value} based on objective keywords",
        expected_output="Structured specialist result",
    )
    out = append_message(state, req)
    out["next_agent"] = next_agent.value
    out["status"] = "running"
    return out


def primary_synthesize(state: GraphState, vault: VaultAdapter) -> dict:
    """Collect INFORM results and produce final output."""
    msgs = state.get("messages") or []
    informs = [m for m in msgs if m.performative == Performative.INFORM]
    parts = []
    for m in informs:
        body = m.payload.get("report") or m.payload.get("review") or str(m.payload)
        parts.append(f"### From {m.from_agent.value}\n{body}")

    final = "\n\n".join(parts) if parts else "No specialist results to synthesize."
    # Persist to blackboard
    path = f"Research/Experiments/synthesis_{msgs[-1].conversation_id if msgs else 'unknown'}.md"
    vault.write(path, final)

    return {
        "final_output": final,
        "status": "completed",
        "vault_refs": list(set((state.get("vault_refs") or []) + [path])),
        "next_agent": None,
    }
