"""Evaluation Critic agent node."""

from __future__ import annotations

from obsidian_orchestration.agents.base import GraphState, append_message, last_message
from obsidian_orchestration.schemas.iacp import AgentName, Performative
from obsidian_orchestration.vault_adapter import VaultAdapter


def _critique_target(vault: VaultAdapter, objective: str, context_refs: list[str]) -> tuple[str, str, list[str]]:
    """Load vault material for the objective; return (body, verdict, paths)."""
    paths: list[str] = list(context_refs or [])
    bodies: list[str] = []

    # Prefer explicit refs, then search
    for p in paths[:8]:
        try:
            bodies.append(f"## {p}\n{vault.read(p)}")
        except Exception:
            bodies.append(f"## {p}\n(unreadable)")

    if not bodies:
        hits = vault.search(objective) or vault.search("Domain")
        for h in hits[:6]:
            p = str(h.get("path") or "")
            if not p:
                continue
            paths.append(p)
            try:
                bodies.append(f"## {p}\n{vault.read(p)}")
            except Exception:
                snippet = str(h.get("snippet") or "")
                bodies.append(f"## {p}\n{snippet}")

    joined = "\n\n".join(bodies).strip()
    if not joined:
        return (
            "No Domain / target notes found in vault for critique.",
            "Revise",
            paths,
        )

    # Lightweight rubric (deterministic, no LLM required)
    issues: list[str] = []
    strengths: list[str] = []
    lower = joined.lower()

    if len(joined) < 200:
        issues.append("Target notes are very short (<200 chars); need more substance.")
    else:
        strengths.append("Notes have non-trivial length.")

    if "todo" in lower or "tbd" in lower or "placeholder" in lower:
        issues.append("Contains TODO/TBD/placeholder markers.")
    if "[[" not in joined and "](" not in joined:
        issues.append("Few or no internal links / citations.")
    else:
        strengths.append("Contains links or markdown references.")

    if "domain" in lower or "iacp" in lower or "agent" in lower:
        strengths.append("On-topic Domain / agent vocabulary present.")

    if issues:
        verdict = "Revise"
        summary = "Needs revision before Accept."
    else:
        verdict = "Accept"
        summary = "Meets baseline Domain-note quality bar."

    review_body = (
        f"### Critic Review — {objective}\n"
        f"- **Summary judgment**: {summary}\n"
        f"- **Sources examined**: {', '.join(f'`{p}`' for p in paths) or '(none)'}\n"
        f"- **Strengths**: {'; '.join(strengths) or 'n/a'}\n"
        f"- **Critical issues**: {'; '.join(issues) or 'None'}\n"
        f"- **Required fixes**: {'; '.join(issues) or 'None'}\n"
        f"- **Final verdict**: **{verdict}**\n"
    )
    return review_body, verdict, paths


def evaluation_critic(state: GraphState, vault: VaultAdapter) -> dict:
    req = last_message(state)
    if req is None or req.performative != Performative.REQUEST:
        return {"status": "failed", "final_output": "Critic received no valid REQUEST"}

    refs = list(req.task.context_refs or []) + list(state.get("vault_refs") or [])
    review, verdict, paths = _critique_target(vault, req.task.objective, refs)

    out_path = f"Research/Experiments/critic_{req.task.id}.md"
    try:
        vault.write(out_path, review)
    except Exception:
        out_path = f"(write-failed)/critic_{req.task.id}.md"

    inform = req.reply(
        from_agent=AgentName.EVALUATION_CRITIC,
        performative=Performative.INFORM,
        payload={
            "review": review,
            "verdict": verdict,
            "vault_path": out_path,
            "examined": paths,
        },
        confidence=0.85 if verdict == "Accept" else 0.7,
        rationale="Domain-note rubric applied",
    )
    out = append_message(state, inform)
    out["next_agent"] = AgentName.PRIMARY.value
    out["vault_refs"] = [out_path, *paths]
    return out

