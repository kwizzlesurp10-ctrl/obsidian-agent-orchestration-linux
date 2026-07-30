"""LangGraph wiring for the four-agent system."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from obsidian_orchestration.agents.architect import prompt_architect
from obsidian_orchestration.agents.base import GraphState
from obsidian_orchestration.agents.critic import evaluation_critic
from obsidian_orchestration.agents.primary import primary_plan, primary_synthesize
from obsidian_orchestration.agents.scout import research_scout
from obsidian_orchestration.schemas.iacp import AgentName
from obsidian_orchestration.vault_adapter import InMemoryVault, VaultAdapter


def _route_after_plan(state: GraphState) -> Literal["research_scout", "prompt_architect", "evaluation_critic", "primary_synthesize"]:
    nxt = (state.get("next_agent") or "").lower()
    if nxt == AgentName.RESEARCH_SCOUT.value:
        return "research_scout"
    if nxt == AgentName.PROMPT_ARCHITECT.value:
        return "prompt_architect"
    if nxt == AgentName.EVALUATION_CRITIC.value:
        return "evaluation_critic"
    return "primary_synthesize"


def build_graph(vault: VaultAdapter | None = None):
    vault = vault or InMemoryVault()

    def plan_node(state: GraphState) -> dict:
        return primary_plan(state, vault)

    def scout_node(state: GraphState) -> dict:
        return research_scout(state, vault)

    def architect_node(state: GraphState) -> dict:
        return prompt_architect(state, vault)

    def critic_node(state: GraphState) -> dict:
        return evaluation_critic(state, vault)

    def synth_node(state: GraphState) -> dict:
        return primary_synthesize(state, vault)

    g = StateGraph(GraphState)
    g.add_node("primary_plan", plan_node)
    g.add_node("research_scout", scout_node)
    g.add_node("prompt_architect", architect_node)
    g.add_node("evaluation_critic", critic_node)
    g.add_node("primary_synthesize", synth_node)

    g.set_entry_point("primary_plan")
    g.add_conditional_edges("primary_plan", _route_after_plan)
    g.add_edge("research_scout", "primary_synthesize")
    g.add_edge("prompt_architect", "primary_synthesize")
    g.add_edge("evaluation_critic", "primary_synthesize")
    g.add_edge("primary_synthesize", END)

    return g.compile()


def run_objective(objective: str, vault: VaultAdapter | None = None) -> dict[str, Any]:
    graph = build_graph(vault)
    initial: GraphState = {
        "messages": [],
        "vault_refs": [],
        "current_task_objective": objective,
        "final_output": None,
        "status": "running",
        "next_agent": None,
    }
    return graph.invoke(initial)
