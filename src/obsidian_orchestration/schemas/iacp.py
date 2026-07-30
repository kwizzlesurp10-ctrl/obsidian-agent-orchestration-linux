"""IACP — Inter-Agent Communication Protocol schemas (Pydantic)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Performative(str, Enum):
    REQUEST = "REQUEST"
    INFORM = "INFORM"
    QUERY = "QUERY"
    PROPOSE = "PROPOSE"
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class AgentName(str, Enum):
    PRIMARY = "primary"
    RESEARCH_SCOUT = "research-scout"
    PROMPT_ARCHITECT = "prompt-architect"
    EVALUATION_CRITIC = "evaluation-critic"


class TaskType(str, Enum):
    SCOUT = "scout"
    DESIGN_PROMPT = "design-prompt"
    CRITIQUE = "critique"
    SYNTHESIZE = "synthesize"
    OTHER = "other"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: _id("task"))
    type: TaskType
    objective: str
    constraints: list[str] = Field(default_factory=list)
    priority: Priority = Priority.NORMAL
    deadline: str | None = None
    context_refs: list[str] = Field(default_factory=list)


class IACPMessage(BaseModel):
    protocol: str = "IACP/1.0"
    message_id: str = Field(default_factory=lambda: _id("msg"))
    timestamp: str = Field(default_factory=_now)
    from_agent: AgentName
    to_agent: AgentName | str
    performative: Performative
    conversation_id: str = Field(default_factory=lambda: _id("conv"))
    in_reply_to: str | None = None
    task: TaskEnvelope
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    rationale: str = ""
    expected_output: str = ""

    def reply(
        self,
        *,
        from_agent: AgentName,
        performative: Performative,
        payload: dict[str, Any] | None = None,
        confidence: float = 0.8,
        rationale: str = "",
    ) -> "IACPMessage":
        return IACPMessage(
            from_agent=from_agent,
            to_agent=self.from_agent,
            performative=performative,
            conversation_id=self.conversation_id,
            in_reply_to=self.message_id,
            task=self.task,
            payload=payload or {},
            confidence=confidence,
            rationale=rationale,
            expected_output=self.expected_output,
        )
