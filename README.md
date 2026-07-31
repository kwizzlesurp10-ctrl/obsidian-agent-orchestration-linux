# Obsidian Agent Orchestration

LangGraph multi-agent system implementing **IACP/1.0** for the Obsidian vault agent stack.

## Features

- **IACP envelopes** — typed REQUEST / INFORM / ESCALATE messages
- **LLM routing** in `primary_plan` (OpenAI-compatible or Ollama; heuristic fallback)
- **Parallel Scout fan-out** via LangGraph `Send` API
- **Live `ObsidianTunnelVault`** — talks to Local REST API / Tunnel (`OBSIDIAN_API_URL` + `OBSIDIAN_API_KEY`)
- **`max_iterations`** — Primary re-plan budget; Critic `Revise` re-enters until Accept or cap
- **Checkpointer** — `MemorySaver` by default (`thread_id` for durable/resumable runs)
- Four agents: Primary, Research Scout, Prompt Architect, Evaluation Critic

## Quick Start

```bash
pip install -e ".[dev]"
python -m examples.delegation_demos
pytest -v
```

### Live Obsidian vault

```bash
export OBSIDIAN_API_URL=https://127.0.0.1:27124
export OBSIDIAN_API_KEY=your-local-rest-api-bearer-token
python -m examples.delegation_demos
```

### LLM routing (optional)

```bash
# OpenAI-compatible
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini

# or Ollama
export LLM_BASE_URL=http://127.0.0.1:11434/v1
export LLM_MODEL=llama3.2
export LLM_ALLOW_NO_KEY=1
```

Without an LLM key the router falls back to keyword heuristics (still supports parallel-scout).

### max_iterations + checkpointer

```python
from obsidian_orchestration.graph import run_objective, build_graph

# Budgeted run with default MemorySaver checkpointer
result = run_objective(
    "Evaluate and critique Domain notes",
    max_iterations=5,
    thread_id="session-42",
)

# Disable checkpointing (unit tests / one-shots)
result = run_objective("...", checkpointer=False, max_iterations=3)

# Resume / inspect state
from langgraph.checkpoint.memory import MemorySaver
graph = build_graph(checkpointer=MemorySaver())
# ... invoke with config={"configurable": {"thread_id": "session-42"}}
# graph.get_state(config)
```

## Architecture

```
User goal
  → primary_plan          # LLM or heuristic route; iteration++
      ├─ research_scout
      ├─ parallel-scout → Send × N → research_scout_worker (parallel)
      ├─ prompt_architect
      └─ evaluation_critic ─(Revise & under max_iterations)→ primary_plan
  → primary_synthesize → END
```

## Repo

https://github.com/kwizzlesurp10-ctrl/obsidian-agent-orchestration
