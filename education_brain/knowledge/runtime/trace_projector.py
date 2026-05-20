from __future__ import annotations

import time
from typing import Any


def project_trace(
    *,
    graph_name: str,
    thread_id: str,
    started_at: float,
    final_state: dict[str, Any],
    events: list[Any] | None = None,
) -> dict[str, Any]:
    stages = list(final_state.get("trace_stages") or [])
    if not stages and events:
        stages = _stages_from_events(events)
    if not stages:
        stages = [{"name": graph_name, "status": "ok", "durationMs": round((time.perf_counter() - started_at) * 1000)}]
    checkpoint_id = _checkpoint_id(final_state)
    return {
        "stages": stages,
        "rowCount": int(final_state.get("row_count") or 0),
        "durationMs": round((time.perf_counter() - started_at) * 1000),
        "graph": {
            "name": graph_name,
            "threadId": thread_id,
            **({"checkpointId": checkpoint_id} if checkpoint_id else {}),
        },
    }


def _stages_from_events(events: list[Any]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        mode, payload = event
        if mode != "updates" or not isinstance(payload, dict):
            continue
        for node_name in payload:
            stages.append({"name": str(node_name), "status": "ok", "durationMs": 0})
    return stages


def _checkpoint_id(final_state: dict[str, Any]) -> str:
    metadata = final_state.get("__metadata__") or {}
    return str(metadata.get("checkpoint_id") or metadata.get("checkpointId") or "")
