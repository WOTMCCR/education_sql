"""聊天接口。"""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from knowledge.analytics.agent import run_data_qa
from knowledge.models.chat import ChatMessage, ChatRequest, ChatResponse
from knowledge.service.chat_history import get_recent_messages, save_message

router = APIRouter(prefix="/chat", tags=["chat"])


def _data_qa_blocks(result: dict) -> list[dict]:
    answer = result.get("answer") or ""
    return [
        {"type": "markdown", "content": answer},
        {"type": "data_qa_result", "data": result},
    ]


@router.post("/query", response_model=ChatResponse)
async def chat_query(req: ChatRequest):
    """显式聊天入口。

    Iteration 04 只实现 `mode=data_qa`，不再保留旧意图分类和文档 RAG。
    """
    task_id = uuid4().hex[:16]
    session_id = req.session_id or uuid4().hex[:16]

    if req.mode != "data_qa":
        raise HTTPException(status_code=400, detail=f"Unsupported chat mode: {req.mode}")

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id,
            task_id=task_id,
            role="user",
            content=req.query,
            answer=req.query,
            intent=req.mode,
            mode=req.mode,
        ),
    )

    result = await asyncio.to_thread(run_data_qa, req.query, session_id)
    answer = result.get("answer") or ""
    blocks = _data_qa_blocks(result)
    response = ChatResponse(
        task_id=task_id,
        intent="data_qa",
        result_type="data_qa_result",
        mode="data_qa",
        items=[],
        summary=answer,
        answer=answer,
        citations=[],
        blocks=blocks,
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
