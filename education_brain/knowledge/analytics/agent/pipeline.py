from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from knowledge.analytics.agent.graph import build_data_qa_graph
from knowledge.analytics.agent.nodes.core import finalize_result
from knowledge.analytics.agent.rules import run_rule_based_data_qa


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


def run_data_qa(question: str, session_id: str | None = None) -> dict[str, Any]:
    started_at = time.perf_counter()
    rule_result = run_rule_based_data_qa(question, started_at=started_at)
    if rule_result is not None:
        return _jsonable(rule_result)

    graph = build_data_qa_graph()
    state = graph.invoke(
        {
            "question": question,
            "session_id": session_id,
            "warnings": [],
            "trace_stages": [],
            "started_at": started_at,
        }
    )
    state.update(finalize_result(state))
    trace_stages = state.get("trace_stages", [])
    result = {
        "queryId": state.get("query_id", ""),
        "mode": "data_qa",
        "question": question,
        "answer": state.get("answer", ""),
        "intent": state.get("intent", {"analysisType": "detail", "metrics": [], "dimensions": [], "filters": []}),
        "visual": state.get("visual", {"type": "table", "title": "问数结果", "columns": [], "rows": []}),
        "explain": state.get("explain", {"sql": "", "metrics": [], "tables": [], "columns": [], "joins": [], "assumptions": []}),
        "trace": {
            "stages": trace_stages,
            "rowCount": int(state.get("row_count") or 0),
            "durationMs": round((time.perf_counter() - started_at) * 1000),
        },
        "warnings": state.get("warnings", []),
    }
    if state.get("error"):
        result["error"] = state["error"]
    return _jsonable(result)
