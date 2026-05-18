"""统一问答接口。"""

import asyncio
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from knowledge.models.chat import ChatMessage, ChatResponse, StreamSubmitResponse
from knowledge.service.chat_history import get_recent_messages, save_message
from knowledge.service.chat_stream import (
    build_streaming_response,
    has_stream_task,
    submit_stream_query,
)
from knowledge.service.chat_sync import (
    handle_chat_intent,
    handle_course as _handle_course,
    handle_question as _handle_question,
)
from knowledge.service.intent_classifier import classify_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    session_id: str = ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /chat/query  （同步，完全不变）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.post("/query", response_model=ChatResponse)
async def chat_query(req: ChatRequest):
    """统一问答入口 — 内部做意图路由

    三种意图走不同路径：
    - course_intro / question_search → MongoDB 结构化查询
    - knowledge → LangGraph 查询管线（统一知识问答）
    """
    task_id = uuid4().hex[:16]
    session_id = req.session_id or uuid4().hex[:16]

    intent_result = await asyncio.to_thread(classify_intent, req.query)

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id,
            task_id=task_id,
            role="user",
            content=req.query,
            answer=req.query,
            intent=intent_result.intent,
        ),
    )

    response = await asyncio.to_thread(
        handle_chat_intent,
        task_id=task_id,
        intent_result=intent_result,
        query=req.query,
        session_id=session_id,
    )

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id, task_id=task_id,
            role="assistant", content=response.answer,
            result_type=response.result_type, items=response.items,
            summary=response.summary, answer=response.answer,
            citations=response.citations, intent=response.intent,
        ),
    )

    return response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /chat/query/stream  [Step 9 新增]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.post("/query/stream", response_model=StreamSubmitResponse)
async def chat_query_stream(req: ChatRequest):
    """统一流式提交入口。

    所有意图都可以提交；只有 `knowledge` 会走 token 流，
    搜索类意图会快速处理并通过 SSE `done` 返回完整结果。
    """
    return await submit_stream_query(req.query, req.session_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /chat/stream/{task_id}  [Step 9 新增]
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/stream/{task_id}")
async def chat_stream_sse(task_id: str):
    if not has_stream_task(task_id):
        raise HTTPException(status_code=404, detail="task_id 不存在或已过期")
    return build_streaming_response(task_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /chat/history（不变）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/history")
async def chat_history(
    session_id: str = Query(description="会话 ID"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """查询历史会话"""
    messages = await asyncio.to_thread(get_recent_messages, session_id, limit)
    return {"session_id": session_id, "messages": messages}
