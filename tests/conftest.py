"""Test defaults: keep unit tests offline unless explicitly testing research agent."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _default_offline_research_agent(monkeypatch):
    # Layered web agent is opt-in during the suite; research tests re-enable as needed.
    monkeypatch.setenv("RESEARCH_AGENT", "0")
    monkeypatch.setenv("RESEARCH_AGENT_PARALLEL", "0")
