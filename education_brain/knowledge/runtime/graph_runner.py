from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from knowledge.runtime.trace_projector import project_trace


@dataclass(frozen=True)
class GraphRunResult:
    state: dict[str, Any]
    trace: dict[str, Any]
    thread_id: str
    checkpoint_id: str = ""


def make_thread_id(*, graph_name: str, session_id: str | None, task_id: str | None = None) -> str:
    session = _safe_key(session_id or "anonymous")
    task = _safe_key(task_id or "run")
    graph = _safe_key(graph_name)
    return f"chat:{session}:{graph}:{task}"


def run_graph(
    graph: Any,
    *,
    graph_name: str,
    input_state: dict[str, Any],
    thread_id: str,
    stream: bool = False,
) -> GraphRunResult:
    started_at = float(input_state.get("started_at") or time.perf_counter())
    config = {"configurable": {"thread_id": thread_id}}
    events: list[Any] = []
    if stream:
        final_state: dict[str, Any] = {}
        for event in graph.stream(input_state, config=config, stream_mode=["updates"]):
            events.append(event)
            if isinstance(event, tuple) and len(event) == 2 and isinstance(event[1], dict):
                for update in event[1].values():
                    if isinstance(update, dict):
                        final_state.update(update)
        if not final_state:
            final_state = graph.invoke(input_state, config=config)
    else:
        final_state = graph.invoke(input_state, config=config)
    checkpoint_id = _latest_checkpoint_id(graph, config)
    metadata = {"graph_name": graph_name, "thread_id": thread_id, "checkpoint_id": checkpoint_id}
    final_state = {**final_state, "__metadata__": metadata}
    trace = project_trace(graph_name=graph_name, thread_id=thread_id, started_at=started_at, final_state=final_state, events=events)
    return GraphRunResult(state=final_state, trace=trace, thread_id=thread_id, checkpoint_id=checkpoint_id)


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", value)[:96]


def _latest_checkpoint_id(graph: Any, config: dict[str, Any]) -> str:
    try:
        snapshot = graph.get_state(config)
    except Exception:
        return ""
    snapshot_config = getattr(snapshot, "config", {}) or {}
    configurable = snapshot_config.get("configurable") or {}
    return str(configurable.get("checkpoint_id") or "")
