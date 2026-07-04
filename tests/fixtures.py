"""tests/fixtures.py — Common Query / Solution / Artifact test doubles."""

from __future__ import annotations

from typing import Any

from ooagent.core.protocols import Artifact, Query, Solution


def make_query(overrides: dict[str, Any] | None = None) -> Query:
    defaults: dict[str, Any] = {
        "text": "test query",
        "format": "text",
        "metadata": {},
    }
    return Query(**{**defaults, **(overrides or {})})


def make_solution(overrides: dict[str, Any] | None = None) -> Solution:
    defaults: dict[str, Any] = {
        "content": "test solution content",
        "format": "text",
        "sources": [],
    }
    return Solution(**{**defaults, **(overrides or {})})


def make_artifact(overrides: dict[str, Any] | None = None) -> Artifact:
    defaults: dict[str, Any] = {
        "content": "test artifact content",
        "format": "text",
        "provenance": [],
    }
    return Artifact(**{**defaults, **(overrides or {})})
