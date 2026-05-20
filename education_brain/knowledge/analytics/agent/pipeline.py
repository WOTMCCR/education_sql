from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Any

from knowledge.analytics.agent.graph import build_data_qa_graph
from knowledge.analytics.agent.nodes.core import finalize_result
from knowledge.analytics.agent.rules import run_rule_based_data_qa
from knowledge.runtime import make_thread_id, run_graph


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def run_data_qa(question: str, session_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    started_at = time.perf_counter()
    task_id = task_id or f"run_{uuid.uuid4().hex[:12]}"
    rule_result = run_rule_based_data_qa(question, started_at=started_at)
    if rule_result is not None:
        rule_result.setdefault("trace", {}).setdefault("graph", {"name": "data_qa", "threadId": make_thread_id(graph_name="data_qa", session_id=session_id, task_id=task_id)})
        return _jsonable(rule_result)

    graph = build_data_qa_graph()
    graph_run = run_graph(
        graph,
        graph_name="data_qa",
        thread_id=make_thread_id(graph_name="data_qa", session_id=session_id, task_id=task_id),
        input_state={
            "question": question,
            "session_id": session_id,
            "warnings": [],
            "trace_stages": [],
            "started_at": started_at,
        },
    )
    state = graph_run.state
    state.update(finalize_result(state))
    trace = {**graph_run.trace, "rowCount": int(state.get("row_count") or 0)}
    result = {
        "queryId": state.get("query_id", ""),
        "mode": "data_qa",
        "question": question,
        "answer": state.get("answer", ""),
        "intent": state.get("intent", {"analysisType": "detail", "metrics": [], "dimensions": [], "filters": []}),
        "visual": state.get("visual", {"type": "table", "title": "问数结果", "columns": [], "rows": []}),
        "explain": state.get("explain", {"sql": "", "metrics": [], "tables": [], "columns": [], "joins": [], "assumptions": []}),
        "trace": trace,
        "warnings": state.get("warnings", []),
    }
    if state.get("error"):
        result["error"] = state["error"]
    return _jsonable(result)
