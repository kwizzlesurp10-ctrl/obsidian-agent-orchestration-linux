from obsidian_orchestration.graph import run_objective
from obsidian_orchestration.llm import _heuristic_route, route_objective
from obsidian_orchestration.vault_adapter import InMemoryVault


def test_heuristic_parallel():
    d = _heuristic_route("Survey and compare multiple aspects of agent protocols")
    assert d["route"] == "parallel-scout"
    assert len(d["sub_queries"]) >= 2


def test_parallel_fanout_runs():
    vault = InMemoryVault()
    vault.write("Agents/Inter-Agent Communication Protocol.md", "MCP A2A notes")
    result = run_objective(
        "Survey and compare multiple aspects of inter-agent protocols",
        vault=vault,
    )
    assert result["status"] == "completed"
    # Parallel path should produce scout_results
    assert len(result.get("scout_results") or []) >= 2


def test_route_objective_fallback():
    # Without API key, should still return a valid route dict
    d = route_objective("Find sources on MCP")
    assert "route" in d
    assert d["route"] in {
        "research-scout",
        "prompt-architect",
        "evaluation-critic",
        "parallel-scout",
    }
