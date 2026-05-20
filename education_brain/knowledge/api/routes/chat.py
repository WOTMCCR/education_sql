"""聊天接口。"""

import asyncio
import inspect
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from knowledge.analytics.agent import run_data_qa
from knowledge.analytics.meta_qa import run_meta_qa
from knowledge.models.chat import ChatMessage, ChatRequest, ChatResponse
from knowledge.runtime import make_thread_id
from knowledge.runtime.result_projector import to_chat_response
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


def _graph_metadata(trace: dict | None, *, mode: str, session_id: str, task_id: str) -> dict[str, str]:
    graph = (trace or {}).get("graph") or {}
    thread_id = graph.get("threadId") or make_thread_id(graph_name=mode, session_id=session_id, task_id=task_id)
    return {
        "thread_id": thread_id,
        "checkpoint_id": graph.get("checkpointId") or "",
        "graph_name": graph.get("name") or mode,
        "graph_run_id": task_id,
    }


def _run_pipeline(fn, query: str, session_id: str, task_id: str):
    signature = inspect.signature(fn)
    if "task_id" in signature.parameters:
        return fn(query, session_id, task_id)
    return fn(query, session_id)


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
            **_graph_metadata(None, mode=mode, session_id=session_id, task_id=task_id),
        ),
    )

    if mode == "data_qa":
        result = await asyncio.to_thread(_run_pipeline, run_data_qa, req.query, session_id, task_id)
    else:
        result = await asyncio.to_thread(_run_pipeline, run_meta_qa, req.query, session_id, task_id)

    trace = result.get("trace")
    response = to_chat_response(task_id=task_id, mode=mode, result=result, trace=trace)
    graph_meta = _graph_metadata(response.trace, mode=mode, session_id=session_id, task_id=task_id)
    response.thread_id = graph_meta["thread_id"]
    response.checkpoint_id = graph_meta["checkpoint_id"]
    response.graph_name = graph_meta["graph_name"]


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
            **graph_meta,
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
