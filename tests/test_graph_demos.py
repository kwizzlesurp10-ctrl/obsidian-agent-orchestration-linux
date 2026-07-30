from obsidian_orchestration.graph import run_objective
from obsidian_orchestration.vault_adapter import InMemoryVault


def test_scout_path():
    vault = InMemoryVault()
    vault.write("Agents/Inter-Agent Communication Protocol.md", "MCP and A2A notes")
    result = run_objective("Research inter-agent communication protocols", vault=vault)
    assert result["status"] == "completed"
    assert result["final_output"]
    assert any("scout" in (p or "").lower() for p in (result.get("vault_refs") or []))


def test_architect_path():
    result = run_objective("Refine the system prompt versioning rules")
    assert result["status"] == "completed"


def test_critic_path():
    result = run_objective("Evaluate and critique the latest research draft")
    assert result["status"] == "completed"
    assert "Accept" in (result.get("final_output") or "")
