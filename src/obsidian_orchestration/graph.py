"""LangGraph wiring: LLM routing + parallel Scout fan-out via Send.

Includes production controls:
- checkpointer (default MemorySaver) for durable / resumable runs
- max_iterations budget on Primary re-plans (Critic Revise can re-enter)
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from obsidian_orchestration.agents.architect import prompt_architect
from obsidian_orchestration.agents.base import GraphState
from obsidian_orchestration.agents.critic import evaluation_critic
from obsidian_orchestration.agents.primary import primary_plan, primary_synthesize
from obsidian_orchestration.agents.scout import research_scout, research_scout_worker
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter, get_default_vault

DEFAULT_MAX_ITERATIONS = 10


def _route_after_plan(
    state: GraphState,
) -> list[Send] | Literal[
    "research_scout",
    "prompt_architect",
    "evaluation_critic",
    "primary_synthesize",
]:
    if state.get("status") == "max_iterations_exceeded":
        return "primary_synthesize"

    nxt = (state.get("next_agent") or "").lower()

    if nxt in {"primary_synthesize", "synthesize", "end"}:
        return "primary_synthesize"

    if nxt == "parallel-scout":
        queries = state.get("sub_queries") or []
        if not queries:
            queries = [state.get("current_task_objective") or "research"]
        # True parallel fan-out: one Send per sub-query
        return [
            Send(
                "research_scout_worker",
                {
                    "current_task_objective": q,
                    "messages": state.get("messages") or [],
                    "vault_refs": state.get("vault_refs") or [],
                    "scout_results": [],
                    "status": "running",
                    "iteration": state.get("iteration"),
                    "max_iterations": state.get("max_iterations"),
                },
            )
            for q in queries
        ]

    if nxt == AgentName.RESEARCH_SCOUT.value:
        return "research_scout"
    if nxt == AgentName.PROMPT_ARCHITECT.value:
        return "prompt_architect"
    if nxt == AgentName.EVALUATION_CRITIC.value:
        return "evaluation_critic"
    return "primary_synthesize"


def _route_after_critic(
    state: GraphState,
) -> Literal["primary_plan", "primary_synthesize"]:
    """On Revise, re-enter Primary while under max_iterations; else synthesize."""
    msgs = state.get("messages") or []
    last = msgs[-1] if msgs else None
    verdict = "Accept"
    if last is not None and last.performative == Performative.INFORM:
        verdict = str((last.payload or {}).get("verdict") or "Accept")

    iteration = int(state.get("iteration") or 0)
    max_iterations = int(state.get("max_iterations") or DEFAULT_MAX_ITERATIONS)

    if verdict.lower() == "revise" and iteration < max_iterations:
        return "primary_plan"
    return "primary_synthesize"


def build_graph(
    vault: VaultAdapter | None = None,
    *,
    checkpointer: Any | bool | None = True,
):
    """Compile the multi-agent graph.

    checkpointer:
      True  → MemorySaver() (default; durable within process)
      False → no checkpointer
      else  → use the provided BaseCheckpointSaver instance
    """
    vault = vault or get_default_vault()

    def plan_node(state: GraphState) -> dict:
        return primary_plan(state, vault)

    def scout_node(state: GraphState) -> dict:
        return research_scout(state, vault)

    def scout_worker_node(state: GraphState) -> dict:
        return research_scout_worker(state, vault)

    def architect_node(state: GraphState) -> dict:
        return prompt_architect(state, vault)

    def critic_node(state: GraphState) -> dict:
        return evaluation_critic(state, vault)

    def synth_node(state: GraphState) -> dict:
        return primary_synthesize(state, vault)

    g = StateGraph(GraphState)
    g.add_node("primary_plan", plan_node)
    g.add_node("research_scout", scout_node)
    g.add_node("research_scout_worker", scout_worker_node)
    g.add_node("prompt_architect", architect_node)
    g.add_node("evaluation_critic", critic_node)
    g.add_node("primary_synthesize", synth_node)

    g.set_entry_point("primary_plan")
    g.add_conditional_edges("primary_plan", _route_after_plan)
    g.add_edge("research_scout", "primary_synthesize")
    g.add_edge("research_scout_worker", "primary_synthesize")
    g.add_edge("prompt_architect", "primary_synthesize")
    g.add_conditional_edges("evaluation_critic", _route_after_critic)
    g.add_edge("primary_synthesize", END)

    if checkpointer is True:
        checkpointer = MemorySaver()
    elif checkpointer is False:
        checkpointer = None

    return g.compile(checkpointer=checkpointer)


def run_objective(
    objective: str,
    vault: VaultAdapter | None = None,
    *,
    thread_id: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    checkpointer: Any | bool | None = True,
    recursion_limit: int | None = None,
) -> dict[str, Any]:
    """Run one objective through the graph.

    Args:
        objective: User goal.
        vault: Vault adapter (default live tunnel when configured, else memory).
        thread_id: Checkpoint thread id (auto-generated when checkpointer enabled).
        max_iterations: Primary re-plan budget (also scales recursion_limit).
        checkpointer: True / False / saver instance (see build_graph).
        recursion_limit: LangGraph superstep cap; defaults to max(max_iterations * 4, 25).
    """
    graph = build_graph(vault, checkpointer=checkpointer)
    initial: GraphState = {
        "messages": [],
        "vault_refs": [],
        "current_task_objective": objective,
        "final_output": None,
        "status": "running",
        "next_agent": None,
        "sub_queries": [],
        "scout_results": [],
        "iteration": 0,
        "max_iterations": max_iterations,
    }

    config: dict[str, Any] = {
        "recursion_limit": recursion_limit
        if recursion_limit is not None
        else max(max_iterations * 4, 25),
    }
    if checkpointer is not False:
        config["configurable"] = {"thread_id": thread_id or uuid4().hex}

    return graph.invoke(initial, config)
