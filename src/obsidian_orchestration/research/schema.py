"""Research brief schemas — FINAL / PARTIAL + validation checklist."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class GoalSpec(BaseModel):
    """LAYER 1 — goals / done criteria / hard constraints."""

    goal: str
    done_when: str = (
        "120–180 word summary + exactly 5 findings + ≥3 distinct fetched sources"
    )
    out_of_scope: list[str] = Field(
        default_factory=lambda: [
            "Never fabricate URLs, quotes, or stats",
            "Prefer PARTIAL over padded FINAL",
        ]
    )
    summary_word_min: int = 120
    summary_word_max: int = 180
    findings_count: int = 5
    min_fetched_sources: int = 3


class ToolBudgets(BaseModel):
    """LAYER 2 — tool permissions + budgets."""

    web_search: int = 8
    fetch_url: int = 6
    max_retries_per_call: int = 2
    max_searches_per_subquestion: int = 3


class Finding(BaseModel):
    claim: str
    source_url: str
    evidence: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("source_url")
    @classmethod
    def must_look_like_url(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("source_url must be an http(s) URL that was fetched")
        return v


class SourceRecord(BaseModel):
    url: str
    title: str = ""
    fetched: bool = False
    snippet: str = ""


class ValidationChecklist(BaseModel):
    """LAYER 5 — eight yes/no items."""

    goal_addressed: bool = False
    summary_word_count_in_range: bool = False
    findings_count_exact: bool = False
    min_fetched_sources_met: bool = False
    every_finding_has_fetched_url: bool = False
    no_fabricated_urls: bool = False
    citations_from_fetch_set: bool = False
    prefers_partial_if_incomplete: bool = False

    def all_yes(self) -> bool:
        return all(
            [
                self.goal_addressed,
                self.summary_word_count_in_range,
                self.findings_count_exact,
                self.min_fetched_sources_met,
                self.every_finding_has_fetched_url,
                self.no_fabricated_urls,
                self.citations_from_fetch_set,
                self.prefers_partial_if_incomplete,
            ]
        )

    def as_yes_no(self) -> dict[str, str]:
        return {k: ("yes" if v else "no") for k, v in self.model_dump().items()}


class ResearchBrief(BaseModel):
    """Single-line JSON target for FINAL or PARTIAL emission."""

    status: Literal["FINAL", "PARTIAL"]
    goal: str
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    dead_ends: list[str] = Field(default_factory=list)
    sub_questions: list[str] = Field(default_factory=list)
    validation: ValidationChecklist = Field(default_factory=ValidationChecklist)
    budgets_remaining: dict[str, int] = Field(default_factory=dict)
    notes_path: str | None = None
    brief_path: str | None = None

    def to_compact_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


class ResearchSessionState(BaseModel):
    """LAYER 4 — memory surfaces."""

    session_id: str
    goal: GoalSpec
    budgets: ToolBudgets
    plan: list[str] = Field(default_factory=list)
    notes_facts: list[str] = Field(default_factory=list)
    notes_dead_ends: list[str] = Field(default_factory=list)
    notes_sources: list[SourceRecord] = Field(default_factory=list)
    recent_observations: list[str] = Field(default_factory=list)
    allowed_urls: set[str] = Field(default_factory=set)
    fetched_urls: set[str] = Field(default_factory=set)
    search_counts: dict[str, int] = Field(default_factory=dict)
    web_search_used: int = 0
    fetch_url_used: int = 0
    findings: list[Finding] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def push_observation(self, text: str) -> None:
        self.recent_observations.append(text)
        self.recent_observations = self.recent_observations[-3:]

    def memory_scan(self) -> str:
        lines = ["## MEMORY SCAN"]
        if self.plan:
            lines.append("PLAN: " + " | ".join(self.plan))
        if self.notes_facts:
            lines.append("FACTS:")
            lines.extend(f"- {f}" for f in self.notes_facts[-12:])
        if self.notes_dead_ends:
            lines.append("DEAD_ENDS:")
            lines.extend(f"- {d}" for d in self.notes_dead_ends[-8:])
        if self.notes_sources:
            lines.append("SOURCES:")
            for s in self.notes_sources[-10:]:
                flag = "fetched" if s.fetched else "discovered"
                lines.append(f"- [{flag}] {s.url} — {s.title[:80]}")
        if self.recent_observations:
            lines.append("RECENT OBS:")
            lines.extend(f"- {o}" for o in self.recent_observations)
        return "\n".join(lines)
