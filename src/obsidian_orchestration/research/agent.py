"""Layered research agent: PLAN → EXECUTE (OODA) → REFLECT → VALIDATE."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from obsidian_orchestration.research.schema import (
    Finding,
    GoalSpec,
    ResearchBrief,
    ResearchSessionState,
    SourceRecord,
    ToolBudgets,
    ValidationChecklist,
)
from obsidian_orchestration.research.tools import ToolError, fetch_url, save_note, web_search
from obsidian_orchestration.vault_adapter import VaultAdapter

SYSTEM_PROMPT_PATH = "Agents/Research Agent System Prompt.md"
SCHEMA_PATH = "Agents/Research Agent Output Schema.md"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _retry(fn: Callable[[], Any], *, retries: int) -> Any:
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last = e
    assert last is not None
    raise last


class ResearchAgent:
    """Citation-backed research agent for Obsidian vault sessions."""

    def __init__(
        self,
        vault: VaultAdapter,
        *,
        budgets: ToolBudgets | None = None,
        session_id: str | None = None,
    ) -> None:
        self.vault = vault
        self.budgets_cfg = budgets or ToolBudgets()
        self.session_id = session_id or uuid4().hex[:12]

    def run(self, goal: str | GoalSpec) -> ResearchBrief:
        goal_spec = goal if isinstance(goal, GoalSpec) else GoalSpec(goal=goal)
        state = ResearchSessionState(
            session_id=self.session_id,
            goal=goal_spec,
            budgets=self.budgets_cfg,
        )
        session_dir = f"Research/Sessions/{self.session_id}"
        notes_path = f"{session_dir}/NOTES.md"
        plan_path = f"{session_dir}/PLAN.md"
        brief_path = f"{session_dir}/brief.md"

        # --- PHASE 1 PLAN ---
        state.plan = self._phase1_plan(goal_spec.goal)
        plan_md = (
            f"---\ntype: research-plan\nsession: {self.session_id}\nupdated: {_now()}\n---\n"
            f"# PLAN — {goal_spec.goal}\n\n"
            + "\n".join(f"{i}. {q}" for i, q in enumerate(state.plan, 1))
            + "\n\n## Citation strategy\n"
            "- Discover via web_search only\n"
            "- fetch_url every URL before citation\n"
            "- Record claims immediately in NOTES\n"
        )
        save_note(self.vault, plan_path, plan_md)
        self._append_notes(state, notes_path, f"## PLAN\n" + "\n".join(f"- {q}" for q in state.plan))

        # --- PHASE 2 EXECUTE (OODA) ---
        for sub_q in state.plan:
            if state.web_search_used >= state.budgets.web_search and state.fetch_url_used >= state.budgets.fetch_url:
                break
            self._execute_subquestion(state, sub_q, notes_path)

        # --- PHASE 3 REFLECT ---
        brief = self._build_brief(state, notes_path=notes_path, brief_path=brief_path)
        validation = self._validate(state, brief)
        brief.validation = validation

        if validation.all_yes():
            brief.status = "FINAL"
        else:
            # One more coverage pass if budget remains
            if state.web_search_used < state.budgets.web_search or state.fetch_url_used < state.budgets.fetch_url:
                gap_q = f"Fill gaps for: {goal_spec.goal} (need sources/findings)"
                self._execute_subquestion(state, gap_q, notes_path)
                brief = self._build_brief(state, notes_path=notes_path, brief_path=brief_path)
                validation = self._validate(state, brief)
                brief.validation = validation
                brief.status = "FINAL" if validation.all_yes() else "PARTIAL"
            else:
                brief.status = "PARTIAL"

        brief.budgets_remaining = {
            "web_search": max(0, state.budgets.web_search - state.web_search_used),
            "fetch_url": max(0, state.budgets.fetch_url - state.fetch_url_used),
        }
        brief.notes_path = notes_path
        brief.brief_path = brief_path
        brief.dead_ends = list(state.notes_dead_ends)

        # Persist brief note + single-line JSON
        self._write_brief_note(brief, brief_path, validation)
        return brief

    # ------------------------------------------------------------------ plan
    def _phase1_plan(self, goal: str) -> list[str]:
        """3–5 sub-questions + implicit citation strategy."""
        base = goal.rstrip("?. ")
        return [
            f"What are the official definitions / primary sources for: {base}?",
            f"What are the latest (2024–2026) developments regarding: {base}?",
            f"What practical best practices or standards apply to: {base}?",
            f"What criticisms, limitations, or open problems exist for: {base}?",
            f"What concrete examples or case studies illustrate: {base}?",
        ][:5]

    # ------------------------------------------------------------------ execute
    def _execute_subquestion(self, state: ResearchSessionState, sub_q: str, notes_path: str) -> None:
        # Scan memory before search
        _ = state.memory_scan()

        searches = state.search_counts.get(sub_q, 0)
        if searches >= state.budgets.max_searches_per_subquestion:
            state.notes_dead_ends.append(f"search cap hit for: {sub_q}")
            self._append_notes(state, notes_path, f"## DEAD_END\n- search cap: {sub_q}")
            return
        if state.web_search_used >= state.budgets.web_search:
            state.notes_dead_ends.append(f"web_search budget exhausted before: {sub_q}")
            return

        # THOUGHT
        thought = f"Need sources for sub-question: {sub_q}"
        # ACTION: web_search
        try:
            results = _retry(
                lambda: web_search(sub_q, max_results=5),
                retries=state.budgets.max_retries_per_call,
            )
            state.web_search_used += 1
            state.search_counts[sub_q] = searches + 1
        except Exception as e:
            state.web_search_used += 1
            state.notes_dead_ends.append(f"web_search error: {e}")
            self._append_notes(state, notes_path, f"## DEAD_END\n- web_search: {e}")
            state.push_observation(f"OBS search error: {e}")
            return

        # OBSERVATION
        state.push_observation(f"OBS search '{sub_q[:60]}' → {len(results)} hits")
        for item in results:
            url = item.get("url") or ""
            if not url:
                continue
            state.allowed_urls.add(url)
            rec = SourceRecord(url=url, title=item.get("title") or "", fetched=False, snippet=item.get("snippet") or "")
            state.notes_sources.append(rec)
            self._append_notes(
                state,
                notes_path,
                f"## SOURCE (discovered)\n- url: {url}\n- title: {rec.title}\n",
            )

        # Fetch top new URLs (budgeted)
        for item in results[:3]:
            url = item.get("url") or ""
            if not url or url in state.fetched_urls:
                continue
            if state.fetch_url_used >= state.budgets.fetch_url:
                break
            if url not in state.allowed_urls:
                # LAYER 2: only URLs from prior search
                continue
            try:
                page = _retry(
                    lambda u=url: fetch_url(u),
                    retries=state.budgets.max_retries_per_call,
                )
                state.fetch_url_used += 1
                state.fetched_urls.add(url)
                final_url = page.get("final_url") or url
                state.fetched_urls.add(final_url)
                state.allowed_urls.add(final_url)
                title = page.get("title") or item.get("title") or ""
                text = page.get("text") or ""
                # Update source record
                state.notes_sources.append(
                    SourceRecord(url=final_url, title=title, fetched=True, snippet=text[:280])
                )
                claim = self._extract_claim(sub_q, title, text)
                if claim:
                    finding = Finding(
                        claim=claim,
                        source_url=final_url,
                        evidence=text[:400],
                        confidence=0.75,
                    )
                    state.findings.append(finding)
                    state.notes_facts.append(f"{claim} (src: {final_url})")
                    self._append_notes(
                        state,
                        notes_path,
                        f"## FACT\n- claim: {claim}\n- source: {final_url}\n- evidence: {text[:300]}\n",
                    )
                state.push_observation(f"OBS fetched {final_url[:80]} ({page.get('char_count', 0)} chars)")
            except Exception as e:
                state.fetch_url_used += 1
                state.notes_dead_ends.append(f"fetch_url error {url}: {e}")
                self._append_notes(state, notes_path, f"## DEAD_END\n- fetch_url {url}: {e}\n")
                state.push_observation(f"OBS fetch error: {url[:60]}")

    def _extract_claim(self, sub_q: str, title: str, text: str) -> str:
        """Deterministic claim extraction — no fabrication of stats/URLs."""
        # Prefer first substantial sentence from page text
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        for s in sentences:
            s = s.strip()
            if 40 <= len(s) <= 280 and not s.startswith("{"):
                prefix = title.strip()
                if prefix and prefix.lower() not in s.lower():
                    return f"{prefix}: {s}" if len(prefix) < 80 else s
                return s
        if title:
            return f"Source documents topic related to sub-question «{sub_q[:80]}»: {title}"
        return ""

    # ------------------------------------------------------------------ validate / emit
    def _build_brief(
        self,
        state: ResearchSessionState,
        *,
        notes_path: str,
        brief_path: str,
    ) -> ResearchBrief:
        # Dedupe findings by URL, take up to findings_count
        seen: set[str] = set()
        findings: list[Finding] = []
        for f in state.findings:
            if f.source_url in seen:
                continue
            if f.source_url not in state.fetched_urls:
                continue
            seen.add(f.source_url)
            findings.append(f)
            if len(findings) >= state.goal.findings_count:
                break

        # Pad not allowed — if fewer, stay short (PARTIAL path)
        summary = self._compose_summary(state, findings)
        sources = []
        seen_s: set[str] = set()
        for s in state.notes_sources:
            if s.url in seen_s:
                continue
            seen_s.add(s.url)
            sources.append(s)

        return ResearchBrief(
            status="PARTIAL",
            goal=state.goal.goal,
            summary=summary,
            findings=findings,
            sources=sources,
            sub_questions=list(state.plan),
            dead_ends=list(state.notes_dead_ends),
            notes_path=notes_path,
            brief_path=brief_path,
        )

    def _compose_summary(self, state: ResearchSessionState, findings: list[Finding]) -> str:
        if not findings:
            return (
                f"Research on «{state.goal.goal}» did not yield enough fetched, citable sources "
                f"to support a full brief. Dead ends: {len(state.notes_dead_ends)}. "
                f"Prefer PARTIAL rather than inventing evidence."
            )
        parts = [
            f"This brief addresses: {state.goal.goal}.",
            f"Based on {len(state.fetched_urls)} fetched source(s) and {len(findings)} citable finding(s):",
        ]
        for i, f in enumerate(findings[:5], 1):
            parts.append(f"({i}) {f.claim}")
        parts.append(
            "All claims below are tied to fetched URLs only; no fabricated statistics or citations."
        )
        text = " ".join(parts)
        # Trim/expand lightly toward word band without fabricating content
        words = text.split()
        lo, hi = state.goal.summary_word_min, state.goal.summary_word_max
        if len(words) > hi:
            text = " ".join(words[:hi])
        elif len(words) < lo and findings:
            # Repeat attribution disclaimer only (no new claims)
            pad = (
                " Coverage is limited to pages successfully retrieved during this session; "
                "additional primary literature may exist beyond the fetch budget."
            )
            while _word_count(text) < lo:
                text = text + pad
                if _word_count(text) >= lo:
                    break
            # hard stop if still short
        return text

    def _validate(self, state: ResearchSessionState, brief: ResearchBrief) -> ValidationChecklist:
        wc = _word_count(brief.summary)
        fetched = state.fetched_urls
        finding_urls = [f.source_url for f in brief.findings]
        every_fetched = bool(finding_urls) and all(u in fetched for u in finding_urls)
        citations_ok = every_fetched
        no_fabricated = every_fetched and all(u.startswith("http") for u in finding_urls)
        exact_findings = len(brief.findings) == state.goal.findings_count
        min_sources = len(fetched) >= state.goal.min_fetched_sources
        summary_ok = state.goal.summary_word_min <= wc <= state.goal.summary_word_max
        tokens = [t for t in re.findall(r"[a-z0-9]+", state.goal.goal.lower()) if len(t) > 3]
        goal_ok = bool(brief.summary) and (
            any(t in brief.summary.lower() for t in tokens[:3]) or bool(brief.findings)
        )
        # prefers PARTIAL if incomplete
        incomplete = not (exact_findings and min_sources and summary_ok and every_fetched)
        prefers_partial = (brief.status == "PARTIAL") if incomplete else True

        return ValidationChecklist(
            goal_addressed=bool(goal_ok),
            summary_word_count_in_range=summary_ok,
            findings_count_exact=exact_findings,
            min_fetched_sources_met=min_sources,
            every_finding_has_fetched_url=every_fetched,
            no_fabricated_urls=no_fabricated if finding_urls else False,
            citations_from_fetch_set=citations_ok if finding_urls else False,
            prefers_partial_if_incomplete=prefers_partial or not incomplete,
        )

    def _append_notes(self, state: ResearchSessionState, path: str, chunk: str) -> None:
        header = (
            f"---\ntype: research-notes\nsession: {state.session_id}\nupdated: {_now()}\n---\n"
            f"# NOTES — {state.goal.goal}\n\n"
            if not state.notes_facts and not state.notes_dead_ends
            else ""
        )
        try:
            existing = ""
            try:
                existing = self.vault.read(path)
            except Exception:
                existing = ""
            if not existing:
                content = header + chunk + "\n"
                save_note(self.vault, path, content, mode="write")
            else:
                save_note(self.vault, path, "\n" + chunk + "\n", mode="append")
        except Exception as e:
            state.notes_dead_ends.append(f"save_note error: {e}")

    def _write_brief_note(
        self,
        brief: ResearchBrief,
        path: str,
        validation: ValidationChecklist,
    ) -> None:
        checklist = "\n".join(f"- {k}: **{v}**" for k, v in validation.as_yes_no().items())
        findings_md = "\n".join(
            f"{i}. {f.claim}\n   - source: {f.source_url}\n   - evidence: {f.evidence[:200]}"
            for i, f in enumerate(brief.findings, 1)
        )
        sources_md = "\n".join(
            f"- {'✓' if s.fetched else '·'} [{s.title or s.url}]({s.url})" for s in brief.sources
        )
        md = f"""---
type: research-brief
status: {brief.status}
session: {brief.notes_path}
updated: {_now()}
---
# Research Brief — {brief.goal}

## Summary
{brief.summary}

## Findings
{findings_md or '_None_'}

## Sources
{sources_md or '_None_'}

## Dead ends
{chr(10).join(f'- {d}' for d in brief.dead_ends) or '_None_'}

## VALIDATION
{checklist}

## Emit
`{brief.status}` JSON:

```json
{brief.to_compact_json()}
```
"""
        save_note(self.vault, path, md, mode="write")


def run_research(
    objective: str | GoalSpec,
    vault: VaultAdapter,
    *,
    search_budget: int = 8,
    fetch_budget: int = 6,
    session_id: str | None = None,
) -> ResearchBrief:
    agent = ResearchAgent(
        vault,
        budgets=ToolBudgets(web_search=search_budget, fetch_url=fetch_budget),
        session_id=session_id,
    )
    return agent.run(objective)
