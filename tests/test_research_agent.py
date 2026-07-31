"""Unit tests for layered research agent (mocked tools)."""

from __future__ import annotations

from obsidian_orchestration.research import GoalSpec, ResearchAgent, ToolBudgets
from obsidian_orchestration.research import agent as agent_mod
from obsidian_orchestration.vault_adapter import InMemoryVault


def test_research_agent_partial_without_network(monkeypatch):
    vault = InMemoryVault()

    def fake_search(query, max_results=5, timeout=20.0):
        return [
            {"url": "https://example.com/a", "title": "Doc A", "snippet": ""},
            {"url": "https://example.com/b", "title": "Doc B", "snippet": ""},
            {"url": "https://example.com/c", "title": "Doc C", "snippet": ""},
        ]

    def fake_fetch(url, timeout=25.0, max_chars=12000):
        bodies = {
            "https://example.com/a": (
                "MCP is a protocol for connecting AI models to tools and data sources. "
                "It standardizes tool discovery and invocation across hosts."
            ),
            "https://example.com/b": (
                "A2A enables agent-to-agent messaging with structured tasks and replies. "
                "It complements tool-centric protocols rather than replacing them."
            ),
            "https://example.com/c": (
                "Best practice is to keep vault-first retrieval local and only escalate "
                "to web research when notes are insufficient."
            ),
        }
        text = bodies.get(url, "Generic page content about agents and protocols for testing.")
        return {
            "url": url,
            "final_url": url,
            "title": url.rsplit("/", 1)[-1].upper(),
            "content_type": "text/html",
            "text": text * 3,
            "char_count": len(text) * 3,
        }

    monkeypatch.setattr(agent_mod, "web_search", fake_search)
    monkeypatch.setattr(agent_mod, "fetch_url", fake_fetch)

    agent = ResearchAgent(
        vault,
        budgets=ToolBudgets(web_search=5, fetch_url=5),
        session_id="testsession1",
    )
    brief = agent.run(
        GoalSpec(
            goal="Compare MCP and A2A for multi-agent systems",
            findings_count=3,
            min_fetched_sources=3,
            summary_word_min=40,
            summary_word_max=200,
        )
    )

    assert brief.status in {"FINAL", "PARTIAL"}
    assert brief.notes_path and vault.read(brief.notes_path)
    assert brief.brief_path and vault.read(brief.brief_path)
    assert len(brief.findings) >= 1
    for f in brief.findings:
        assert f.source_url.startswith("http")
    # No fabricated URLs outside fetch set
    assert all(f.source_url.startswith("https://example.com/") for f in brief.findings)
    assert "validation" in brief.validation.as_yes_no() or brief.validation is not None


def test_save_note_and_dead_end_on_search_error(monkeypatch):
    vault = InMemoryVault()

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(agent_mod, "web_search", boom)

    agent = ResearchAgent(
        vault,
        budgets=ToolBudgets(web_search=2, fetch_url=2),
        session_id="deadend1",
    )
    brief = agent.run("Topic that cannot be searched")
    assert brief.status == "PARTIAL"
    assert brief.dead_ends
    assert brief.notes_path
    notes = vault.read(brief.notes_path)
    assert "DEAD_END" in notes or "dead" in notes.lower() or brief.dead_ends
