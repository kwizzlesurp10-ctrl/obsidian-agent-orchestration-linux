"""Five concrete delegation demos matching the vault note Delegation Examples.md."""

from __future__ import annotations

from obsidian_orchestration.graph import run_objective
from obsidian_orchestration.vault_adapter import InMemoryVault


def seed_vault(vault: InMemoryVault) -> None:
    vault.write(
        "Agents/Inter-Agent Communication Protocol.md",
        "IACP/1.0 — MCP for tools, A2A for agents. ACP merged into A2A in 2025.",
    )
    vault.write(
        "Research/2026-07-30 Obsidian Agent Bootstrap.md",
        "Bootstrap of the Obsidian multi-agent system and tunnel.",
    )


def demo_1_scout() -> None:
    print("\n=== Demo 1: Primary → Research Scout ===")
    vault = InMemoryVault()
    seed_vault(vault)
    result = run_objective(
        "Find current best practices on inter-agent protocols MCP and A2A",
        vault=vault,
    )
    print("Status:", result.get("status"))
    print("Final output preview:\n", (result.get("final_output") or "")[:500])


def demo_2_architect() -> None:
    print("\n=== Demo 2: Primary → Prompt Architect ===")
    vault = InMemoryVault()
    result = run_objective(
        "Improve the Research Scout system prompt versioning and source attribution",
        vault=vault,
    )
    print("Status:", result.get("status"))
    print("Final output preview:\n", (result.get("final_output") or "")[:500])


def demo_3_critic() -> None:
    print("\n=== Demo 3: Primary → Evaluation Critic ===")
    vault = InMemoryVault()
    result = run_objective(
        "Critique and evaluate the draft synthesis on inter-agent protocols for quality",
        vault=vault,
    )
    print("Status:", result.get("status"))
    print("Final output preview:\n", (result.get("final_output") or "")[:500])


def demo_4_hierarchical() -> None:
    print("\n=== Demo 4: Hierarchical default (scout path) ===")
    vault = InMemoryVault()
    seed_vault(vault)
    result = run_objective("Research the state of LangGraph multi-agent orchestration in 2026", vault=vault)
    print("Status:", result.get("status"))
    print("Vault refs:", result.get("vault_refs"))


def demo_5_parallel_note() -> None:
    print("\n=== Demo 5: Parallel fan-out (documented pattern) ===")
    print(
        "In production, Primary emits multiple Scout REQUESTs with different "
        "sub-questions, runs them as parallel LangGraph nodes or asyncio tasks, "
        "then joins INFORM results before synthesize. "
        "This skeleton uses sequential routing; extend graph.py with a fan-out node."
    )


def main() -> None:
    demo_1_scout()
    demo_2_architect()
    demo_3_critic()
    demo_4_hierarchical()
    demo_5_parallel_note()
    print("\nAll demos finished.")


if __name__ == "__main__":
    main()
