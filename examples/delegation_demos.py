"""Delegation demos including parallel Scout fan-out."""

from __future__ import annotations

import os

from obsidian_orchestration.graph import run_objective
from obsidian_orchestration.vault_adapter import InMemoryVault, ObsidianTunnelVault, get_default_vault


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
    result = run_objective(
        "Improve the Research Scout system prompt versioning and source attribution",
        vault=InMemoryVault(),
    )
    print("Status:", result.get("status"))
    print((result.get("final_output") or "")[:400])


def demo_3_critic() -> None:
    print("\n=== Demo 3: Primary → Evaluation Critic ===")
    result = run_objective(
        "Critique and evaluate the draft synthesis on inter-agent protocols for quality",
        vault=InMemoryVault(),
    )
    print("Status:", result.get("status"))
    print((result.get("final_output") or "")[:400])


def demo_4_parallel_scout() -> None:
    print("\n=== Demo 4: Parallel Scout fan-out ===")
    vault = InMemoryVault()
    seed_vault(vault)
    # Force parallel path via keywords the heuristic recognizes
    result = run_objective(
        "Survey and compare multiple aspects of LangGraph multi-agent orchestration landscape",
        vault=vault,
    )
    print("Status:", result.get("status"))
    print("Scout results count:", len(result.get("scout_results") or []))
    print("Vault refs:", result.get("vault_refs"))
    print((result.get("final_output") or "")[:600])


def demo_5_live_vault_note() -> None:
    print("\n=== Demo 5: Live ObsidianTunnelVault ===")
    if not os.getenv("OBSIDIAN_API_KEY") and os.getenv("OBSIDIAN_USE_LIVE") != "1":
        print(
            "Set OBSIDIAN_API_KEY (and optionally OBSIDIAN_API_URL) to exercise the live adapter.\n"
            "Example:\n"
            "  export OBSIDIAN_API_URL=https://127.0.0.1:27124\n"
            "  export OBSIDIAN_API_KEY=your-bearer-token\n"
            "  python -m examples.delegation_demos"
        )
        return
    vault = ObsidianTunnelVault()
    try:
        files = vault.list("")
        print("Live vault root entries:", files[:10])
        result = run_objective("Research agents folder structure", vault=vault)
        print("Status:", result.get("status"))
    except Exception as e:
        print("Live vault error:", e)


def main() -> None:
    demo_1_scout()
    demo_2_architect()
    demo_3_critic()
    demo_4_parallel_scout()
    demo_5_live_vault_note()
    print("\nAll demos finished.")


if __name__ == "__main__":
    main()
