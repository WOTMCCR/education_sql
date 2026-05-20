from __future__ import annotations

from knowledge.analytics.meta_qa.state import MetaQaState


def run_meta_qa_node(state: MetaQaState) -> dict:
    from knowledge.analytics.meta_qa.pipeline import _run_meta_qa_direct

    result = _run_meta_qa_direct(state["question"], state.get("session_id"))
    return {
        "result": result,
        "row_count": 0,
        "trace_stages": (result.get("trace") or {}).get("stages") or [],
    }
