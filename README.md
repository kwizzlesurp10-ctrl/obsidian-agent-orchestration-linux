# Obsidian Agent Orchestration

LangGraph multi-agent system that implements the **Inter-Agent Communication Protocol (IACP/1.0)** designed for the Obsidian vault agent stack.

**Agents**
- **Primary** — planner / synthesizer / supervisor
- **Research Scout** — fast vault-first retrieval
- **Prompt Architect** — versioned prompt design
- **Evaluation Critic** — quality gate (Accept / Revise / Reject)

**Key features**
- Typed IACP message envelopes (performative, confidence, rationale)
- Vault-as-blackboard pattern
- LangGraph state machine with conditional edges
- Ready to wire to Obsidian Local REST API / Tunnel tools
- Five concrete delegation examples as executable demos

## Quick Start

```bash
pip install -e ".[dev]"
python -m examples.delegation_demos
pytest tests/ -v
```

## Architecture

```
User goal
  → primary_plan
      ├─ REQUEST → research_scout   → INFORM → primary_join
      ├─ REQUEST → prompt_architect → INFORM → primary_join
      ├─ REQUEST → evaluation_critic→ INFORM → primary_join
      └─ direct synthesize
  → primary_synthesize → END
```

## Protocol

See `src/obsidian_orchestration/schemas/iacp.py` and the companion vault notes:
- `Agents/Inter-Agent Communication Protocol.md`
- `Agents/Delegation Examples.md`

## GitHub

https://github.com/kwizzlesurp10-ctrl/obsidian-agent-orchestration

Built for Local AI Integrations / Sovereign Forge.
