from __future__ import annotations

from knowledge.models.chat import ChatResponse


def data_qa_blocks(result: dict) -> list[dict]:
    answer = result.get("answer") or ""
    return [{"type": "markdown", "content": answer}, {"type": "data_qa_result", "data": result}]


def meta_qa_blocks(result: dict) -> list[dict]:
    blocks = result.get("blocks")
    if isinstance(blocks, list):
        return blocks
    return [{"type": "markdown", "content": result.get("answer") or ""}, {"type": "meta_citations", "data": result.get("citations") or []}]


def to_chat_response(
    *,
    task_id: str,
    mode: str,
    result: dict,
    trace: dict | None = None,
) -> ChatResponse:
    if mode == "data_qa":
        answer = result.get("answer") or ""
        return ChatResponse(
            task_id=task_id,
            intent="data_qa",
            result_type="data_qa_result",
            mode="data_qa",
            items=[],
            summary=answer,
            answer=answer,
            citations=[],
            blocks=data_qa_blocks(result),
            trace=trace,
        )
    answer = result.get("answer") or ""
    return ChatResponse(
        task_id=task_id,
        intent="meta_qa",
        result_type=result.get("result_type") or "meta_answer",
        mode="meta_qa",
        items=[],
        summary=answer,
        answer=answer,
        citations=result.get("citations") or [],
        blocks=meta_qa_blocks(result),
        trace=trace or result.get("trace"),
    )
