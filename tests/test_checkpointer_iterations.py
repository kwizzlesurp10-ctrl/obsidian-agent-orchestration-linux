"""Tests for max_iterations budget and MemorySaver checkpointer."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from obsidian_orchestration.graph import build_graph, run_objective
from obsidian_orchestration.vault_adapter import InMemoryVault


def _seed_strong_domain(vault: InMemoryVault) -> None:
    body = """---
type: domain
tags: [domain, agents]
---
# Domain — Inter-Agent Protocols

This Domain note covers IACP/1.0, MCP tool calling, and A2A agent messaging.
See also [[Inter-Agent Communication Protocol]] and [IACP schema](./iacp.md).

## Core concepts
- REQUEST / INFORM / ESCALATE performatives
- Primary supervisor with Research Scout, Prompt Architect, Evaluation Critic
- Vault-first retrieval when the Obsidian Tunnel is up

Enough substance for the Critic baseline rubric to Accept.
"""
    vault.write("Domain/Inter-Agent Protocols.md", body)
    vault.write(
        "Agents/Inter-Agent Communication Protocol.md",
        "IACP/1.0 — MCP for tools, A2A for agents. Link: [[Domain/Inter-Agent Protocols]]",
    )


def test_run_objective_tracks_iteration():
    vault = InMemoryVault()
    _seed_strong_domain(vault)
    result = run_objective(
        "Evaluate and critique Domain notes on inter-agent protocols",
        vault=vault,
        max_iterations=5,
        checkpointer=False,
    )
    assert result["status"] == "completed"
    assert result.get("iteration", 0) >= 1
    assert result.get("max_iterations") == 5
    assert "Accept" in (result.get("final_output") or "")


def test_max_iterations_caps_critic_revise_loop():
    """Empty vault → Critic Revise → re-plan until max_iterations, then stop."""
    vault = InMemoryVault()
    result = run_objective(
        "Evaluate and critique the Domain notes quality",
        vault=vault,
        max_iterations=2,
        checkpointer=False,
    )
    assert result.get("iteration") == 2
    assert result["status"] == "completed"
    # Should have at least one Revise review in the transcript
    out = result.get("final_output") or ""
    assert "Revise" in out or "Critic" in out or "review" in out.lower()


def test_checkpointer_persists_thread_state():
    vault = InMemoryVault()
    _seed_strong_domain(vault)
    saver = MemorySaver()
    thread = "test-thread-domain-1"

    graph = build_graph(vault, checkpointer=saver)
    initial = {
        "messages": [],
        "vault_refs": [],
        "current_task_objective": "Evaluate and critique Domain notes on protocols",
        "final_output": None,
        "status": "running",
        "next_agent": None,
        "sub_queries": [],
        "scout_results": [],
        "iteration": 0,
        "max_iterations": 5,
    }
    config = {"configurable": {"thread_id": thread}, "recursion_limit": 40}
    result = graph.invoke(initial, config)
    assert result["status"] == "completed"

    # Checkpoint exists and get_state returns the finished snapshot
    snap = graph.get_state(config)
    assert snap.values.get("status") == "completed"
    assert snap.values.get("final_output")
    assert snap.values.get("iteration", 0) >= 1


def test_run_objective_with_explicit_thread_id():
    vault = InMemoryVault()
    vault.write("Agents/x.md", "MCP and A2A " + ("notes " * 40) + "[[link]]")
    result = run_objective(
        "Research inter-agent communication protocols",
        vault=vault,
        thread_id="scout-thread-1",
        max_iterations=3,
    )
    assert result["status"] == "completed"
