"""Primary (supervisor) agent node with LLM-powered routing."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message
from obsidian_orchestration.llm import route_objective
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
    """Decompose objective via LLM (or heuristic) and set next_agent / sub_queries."""
    objective = state.get("current_task_objective") or "No objective provided"
    decision = route_objective(objective)

    route = decision["route"]
    sub_queries = decision.get("sub_queries") or []
    confidence = float(decision.get("confidence", 0.7))
    rationale = decision.get("rationale") or ""

    if route == "parallel-scout":
        next_agent = "parallel-scout"
        task_type = TaskType.SCOUT
        to_agent: AgentName | str = AgentName.RESEARCH_SCOUT
    elif route == "prompt-architect":
        next_agent = AgentName.PROMPT_ARCHITECT.value
        task_type = TaskType.DESIGN_PROMPT
        to_agent = AgentName.PROMPT_ARCHITECT
    elif route == "evaluation-critic":
        next_agent = AgentName.EVALUATION_CRITIC.value
        task_type = TaskType.CRITIQUE
        to_agent = AgentName.EVALUATION_CRITIC
    else:
        next_agent = AgentName.RESEARCH_SCOUT.value
        task_type = TaskType.SCOUT
        to_agent = AgentName.RESEARCH_SCOUT

    task = TaskEnvelope(
        type=task_type,
        objective=objective,
        constraints=["Prefer vault sources", "Return structured output"],
        priority=Priority.HIGH,
        context_refs=state.get("vault_refs") or [],
    )
    req = IACPMessage(
        from_agent=AgentName.PRIMARY,
        to_agent=to_agent,
        performative=Performative.REQUEST,
        task=task,
        payload={"sub_queries": sub_queries} if sub_queries else {},
        confidence=confidence,
        rationale=rationale,
        expected_output="Structured specialist result",
    )
    out = append_message(state, req)
    out["next_agent"] = next_agent
    out["sub_queries"] = sub_queries
    out["status"] = "running"
    return out


def primary_synthesize(state: GraphState, vault: VaultAdapter) -> dict:
    """Join INFORM messages + parallel scout_results into final output."""
    msgs = state.get("messages") or []
    informs = [m for m in msgs if m.performative == Performative.INFORM]
    parts: list[str] = []

    for m in informs:
        body = m.payload.get("report") or m.payload.get("review") or str(m.payload)
        parts.append(f"### From {m.from_agent.value}\n{body}")

    for sr in state.get("scout_results") or []:
        parts.append(f"### Parallel Scout — {sr.get('query', '')}\n{sr.get('report', '')}")

    final = "\n\n".join(parts) if parts else "No specialist results to synthesize."
    conv = msgs[-1].conversation_id if msgs else "unknown"
    path = f"Research/Experiments/synthesis_{conv}.md"
    try:
        vault.write(path, final)
    except Exception:
        path = f"(write-failed)/synthesis_{conv}.md"

    return {
        "final_output": final,
        "status": "completed",
        "vault_refs": [path],
        "next_agent": None,
    }
