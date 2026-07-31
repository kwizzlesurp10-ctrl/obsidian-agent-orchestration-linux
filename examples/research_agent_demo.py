"""Run the layered research agent against the vault (live tunnel if configured)."""

from __future__ import annotations

import os
import sys

from obsidian_orchestration.research import run_research
from obsidian_orchestration.vault_adapter import get_default_vault


def main() -> int:
    goal = " ".join(sys.argv[1:]) or (
        "Produce a citation-backed brief on inter-agent protocols MCP and A2A for Obsidian agents"
    )
    vault = get_default_vault()
    print("Vault:", type(vault).__name__)
    print("Goal:", goal)

    brief = run_research(
        goal,
        vault,
        search_budget=int(os.getenv("RESEARCH_SEARCH_BUDGET", "6")),
        fetch_budget=int(os.getenv("RESEARCH_FETCH_BUDGET", "4")),
    )
    print("Status:", brief.status)
    print("Notes:", brief.notes_path)
    print("Brief:", brief.brief_path)
    print("Findings:", len(brief.findings))
    print("Validation:", brief.validation.as_yes_no())
    print("JSON:", brief.to_compact_json()[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
