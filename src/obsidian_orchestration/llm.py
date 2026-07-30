"""Lightweight OpenAI-compatible LLM client for routing decisions."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

ROUTING_SYSTEM = """You are the routing brain of a multi-agent system.
Given a user objective, decide which specialist(s) to invoke.

Available agents:
- research-scout: vault/web retrieval, source finding, scouting
- prompt-architect: system prompt design, versioning, prompt improvements
- evaluation-critic: quality review, Accept/Revise/Reject, evidence critique

Also decide whether to fan-out multiple scout sub-queries in parallel.

Respond with ONLY valid JSON, no markdown:
{
  "route": "research-scout" | "prompt-architect" | "evaluation-critic" | "parallel-scout",
  "sub_queries": ["..."],   // only for parallel-scout; 2-5 focused sub-questions
  "confidence": 0.0-1.0,
  "rationale": "short reason"
}
"""


def _endpoint() -> tuple[str, str, str]:
    """Return (base_url, api_key, model)."""
    base = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    model = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    return base.rstrip("/"), key, model


def llm_available() -> bool:
    _, key, _ = _endpoint()
    # Ollama often needs no key
    base, _, _ = _endpoint()
    if "11434" in base or os.getenv("LLM_ALLOW_NO_KEY") == "1":
        return True
    return bool(key)


def chat_json(system: str, user: str, temperature: float = 0.1) -> dict[str, Any]:
    base, key, model = _endpoint()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # Prefer JSON mode when supported
    if "openai.com" in base or os.getenv("LLM_JSON_MODE") == "1":
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    content = data["choices"][0]["message"]["content"]
    # Strip optional markdown fences
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    return json.loads(content)


def route_objective(objective: str) -> dict[str, Any]:
    """LLM-powered routing. Falls back to heuristics if LLM unavailable."""
    if not llm_available():
        return _heuristic_route(objective)

    try:
        result = chat_json(ROUTING_SYSTEM, f"Objective: {objective}")
        route = result.get("route", "research-scout")
        if route not in {"research-scout", "prompt-architect", "evaluation-critic", "parallel-scout"}:
            route = "research-scout"
        sub_queries = result.get("sub_queries") or []
        if route == "parallel-scout" and len(sub_queries) < 2:
            sub_queries = _default_subqueries(objective)
        return {
            "route": route,
            "sub_queries": sub_queries,
            "confidence": float(result.get("confidence", 0.75)),
            "rationale": result.get("rationale") or "LLM routing",
        }
    except Exception as e:
        fallback = _heuristic_route(objective)
        fallback["rationale"] = f"LLM failed ({e}); used heuristic"
        return fallback


def _heuristic_route(objective: str) -> dict[str, Any]:
    o = objective.lower()
    if any(k in o for k in ("prompt", "system prompt", "version the", "architect")):
        return {"route": "prompt-architect", "sub_queries": [], "confidence": 0.7, "rationale": "keyword: prompt"}
    if any(k in o for k in ("critique", "review", "evaluate", "quality gate")):
        return {"route": "evaluation-critic", "sub_queries": [], "confidence": 0.7, "rationale": "keyword: critique"}
    if any(k in o for k in ("compare", "multiple", "several aspects", "survey", "landscape")):
        return {
            "route": "parallel-scout",
            "sub_queries": _default_subqueries(objective),
            "confidence": 0.65,
            "rationale": "keyword: multi-aspect → parallel scout",
        }
    return {"route": "research-scout", "sub_queries": [], "confidence": 0.6, "rationale": "default scout"}


def _default_subqueries(objective: str) -> list[str]:
    return [
        f"Primary sources and official specs related to: {objective}",
        f"Recent 2025-2026 developments and adoption of: {objective}",
        f"Criticisms, limitations, and alternatives regarding: {objective}",
    ]
