"""聊天接口。"""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from knowledge.analytics.agent import run_data_qa
from knowledge.analytics.meta_qa import run_meta_qa
from knowledge.models.chat import ChatMessage, ChatRequest, ChatResponse
from knowledge.service.chat_history import get_recent_messages, save_message

router = APIRouter(prefix="/chat", tags=["chat"])


META_QA_ROUTE_TERMS = (
    "有哪些表",
    "有什么表",
    "哪些表",
    "有哪些数据",
    "有什么数据",
    "有哪些数据库",
    "有什么数据库",
    "数据资产",
    "业务主题",
    "可问范围",
    "我能问什么",
    "我可以问什么",
    "能问哪些",
    "可以问哪些",
    "有哪些指标",
    "有什么指标",
    "关注哪些指标",
    "应该关注哪些",
    "应该先关注",
    "insight",
    "洞察",
)


def _resolve_chat_mode(requested_mode: str, query: str) -> str:
    if requested_mode != "data_qa":
        return requested_mode
    normalized = query.lower()
    if any(term in normalized for term in META_QA_ROUTE_TERMS):
        return "meta_qa"
    return requested_mode


def _data_qa_blocks(result: dict) -> list[dict]:
    answer = result.get("answer") or ""
    return [
        {"type": "markdown", "content": answer},
        {"type": "data_qa_result", "data": result},
    ]


def _meta_qa_blocks(result: dict) -> list[dict]:
    blocks = result.get("blocks")
    if isinstance(blocks, list):
        return blocks
    return [
        {"type": "markdown", "content": result.get("answer") or ""},
        {"type": "meta_citations", "data": result.get("citations") or []},
    ]


@router.post("/query", response_model=ChatResponse)
async def chat_query(req: ChatRequest):
    """显式聊天入口。

    显式 mode 仍是主入口；数据资产探索类问题会从 `data_qa` 自动转到 `meta_qa`。
    """
    task_id = uuid4().hex[:16]
    session_id = req.session_id or uuid4().hex[:16]

    if req.mode not in {"data_qa", "meta_qa"}:
        raise HTTPException(status_code=400, detail=f"Unsupported chat mode: {req.mode}")
    mode = _resolve_chat_mode(req.mode, req.query)

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id,
            task_id=task_id,
            role="user",
            content=req.query,
            answer=req.query,
            intent=mode,
            mode=mode,
        ),
    )

    if mode == "data_qa":
        result = await asyncio.to_thread(run_data_qa, req.query, session_id)
        answer = result.get("answer") or ""
        blocks = _data_qa_blocks(result)
        result_type = "data_qa_result"
        citations: list[dict] = []
        trace = None
    else:
        result = await asyncio.to_thread(run_meta_qa, req.query, session_id)
        answer = result.get("answer") or ""
        blocks = _meta_qa_blocks(result)
        result_type = result.get("result_type") or "meta_answer"
        citations = result.get("citations") or []
        trace = result.get("trace")

    response = ChatResponse(
        task_id=task_id,
        intent=mode,
        result_type=result_type,
        mode=mode,
        items=[],
        summary=answer,
        answer=answer,
        citations=citations,
        blocks=blocks,
        trace=trace,
    )

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id, task_id=task_id,
            role="assistant", content=response.answer,
            result_type=response.result_type, items=response.items,
            summary=response.summary, answer=response.answer,
            citations=response.citations, intent=response.intent,
            mode=response.mode, blocks=response.blocks,
            trace=response.trace,
        ),
    )

    return response


@router.get("/history")
async def chat_history(
    session_id: str = Query(description="会话 ID"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """查询历史会话"""
    messages = await asyncio.to_thread(get_recent_messages, session_id, limit)
    return {"session_id": session_id, "messages": messages}
