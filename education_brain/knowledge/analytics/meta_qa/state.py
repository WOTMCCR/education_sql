from __future__ import annotations

from typing import Any, TypedDict


class MetaQaState(TypedDict, total=False):
    question: str
    session_id: str | None
    result: dict[str, Any]
    trace_stages: list[dict[str, Any]]
    row_count: int
    started_at: float
