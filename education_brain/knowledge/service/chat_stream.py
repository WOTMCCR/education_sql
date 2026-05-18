"""SSE 流式聊天运行时。

这个模块只负责流式入口相关逻辑：
- 任务提交
- 内存队列管理
- SSE 事件生成
- 后台执行管线
"""

import asyncio
import json
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi.responses import StreamingResponse

from knowledge.core.config import get_settings
from knowledge.models.chat import ChatMessage, StreamSubmitResponse
from knowledge.service.chat_history import get_recent_messages, save_message
from knowledge.service.chat_sync import handle_chat_intent
from knowledge.service.intent_classifier import classify_intent

logger = logging.getLogger(__name__)

_task_queues: dict[str, asyncio.Queue] = {}
_task_done_times: dict[str, float] = {}


def cleanup_expired_tasks() -> None:
    """清理超过 TTL 的已完成任务队列。"""
    settings = get_settings()
    now = time.monotonic()
    expired = [
        tid
        for tid, done_time in _task_done_times.items()
        if now - done_time > settings.stream_task_ttl_seconds
    ]
    for tid in expired:
        _task_queues.pop(tid, None)
        _task_done_times.pop(tid, None)
    if expired:
        logger.debug("清理了 %d 个过期流式任务", len(expired))


def has_stream_task(task_id: str) -> bool:
    return task_id in _task_queues


def build_streaming_response(task_id: str) -> StreamingResponse:
    return StreamingResponse(
        sse_event_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def submit_stream_query(query: str, session_id: str = "") -> StreamSubmitResponse:
    """统一流式提交入口。

    与旧版本不同：所有意图都可以提交，只有 `knowledge`
    会走 LLM token 流；搜索类意图快速处理后直接发 done。
    """
    intent_result = await asyncio.to_thread(classify_intent, query)

    task_id = uuid4().hex[:16]
    actual_session_id = session_id or uuid4().hex[:16]

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=actual_session_id,
            task_id=task_id,
            role="user",
            content=query,
            answer=query,
            intent=intent_result.intent,
        ),
    )

    cleanup_expired_tasks()
    queue: asyncio.Queue = asyncio.Queue()
    _task_queues[task_id] = queue

    asyncio.create_task(
        run_stream_pipeline(
            task_id=task_id,
            session_id=actual_session_id,
            query=query,
            intent_result=intent_result,
            queue=queue,
        )
    )

    return StreamSubmitResponse(
        task_id=task_id,
        intent=intent_result.intent,
        status="processing",
    )


async def sse_event_generator(task_id: str):
    """将内存队列中的事件序列化为 SSE 文本流。"""
    settings = get_settings()
    queue = _task_queues.get(task_id)
    if queue is None:
        return

    while True:
        try:
            event = await asyncio.wait_for(
                queue.get(),
                timeout=settings.stream_keepalive_seconds,
            )
        except asyncio.TimeoutError:
            yield ":keepalive\n\n"
            continue

        event_type = event.get("event", "message")
        event_data = json.dumps(event.get("data", {}), ensure_ascii=False)
        yield f"event: {event_type}\ndata: {event_data}\n\n"

        if event_type in ("done", "error"):
            break


async def run_stream_pipeline(
    *,
    task_id: str,
    session_id: str,
    query: str,
    intent_result,
    queue: asyncio.Queue,
) -> None:
    """后台任务：统一处理所有意图的流式结果。"""
    try:
        if intent_result.intent != "knowledge":
            await _run_non_qa_stream(
                task_id=task_id,
                session_id=session_id,
                query=query,
                intent_result=intent_result,
                queue=queue,
            )
            return

        await _run_knowledge_stream(
            task_id=task_id,
            session_id=session_id,
            query=query,
            queue=queue,
        )
    except Exception as exc:
        logger.error("流式管线异常: %s", exc, exc_info=True)
        await queue.put(
            {
                "event": "error",
                "data": {"message": f"答案生成失败: {exc}"},
            }
        )
    finally:
        _task_done_times[task_id] = time.monotonic()


async def _run_non_qa_stream(
    *,
    task_id: str,
    session_id: str,
    query: str,
    intent_result,
    queue: asyncio.Queue,
) -> None:
    """搜索类意图的统一流式处理：快速完成后直接 done。"""
    await queue.put(
        {
            "event": "status",
            "data": {"phase": "searching", "message": "正在检索结果..."},
        }
    )

    response = await asyncio.to_thread(
        handle_chat_intent,
        task_id=task_id,
        intent_result=intent_result,
        query=query,
        session_id=session_id,
    )

    await queue.put({"event": "done", "data": response.model_dump()})
    await _save_assistant_response(session_id=session_id, task_id=task_id, response=response)


async def _run_knowledge_stream(
    *,
    task_id: str,
    session_id: str,
    query: str,
    queue: asyncio.Queue,
) -> None:
    """知识类问题的流式处理。"""
    from knowledge.processor.query_pipeline.graph import build_retrieval_graph
    from knowledge.processor.query_pipeline.nodes.answer_generate import answer_generate_stream
    from knowledge.processor.query_pipeline.state import create_default_state

    full_answer_parts: list[str] = []
    citations: list[dict[str, Any]] = []

    await queue.put(
        {
            "event": "status",
            "data": {"phase": "rewriting", "message": "正在改写查询..."},
        }
    )

    history = await asyncio.to_thread(get_recent_messages, session_id, 6)
    state = create_default_state(
        session_id=session_id,
        original_query=query,
        history=history,
    )

    await queue.put(
        {
            "event": "status",
            "data": {"phase": "searching", "message": "正在检索相关文档..."},
        }
    )
    retrieval_graph = build_retrieval_graph()
    result_state = await asyncio.to_thread(retrieval_graph.invoke, state)

    await queue.put(
        {
            "event": "status",
            "data": {"phase": "generating", "message": "正在生成回答..."},
        }
    )

    async for event in answer_generate_stream(result_state):
        await queue.put(event)
        if event.get("event") == "token":
            full_answer_parts.append(event.get("data", {}).get("text", ""))
        elif event.get("event") == "citation":
            citations = event.get("data", {}).get("citations", [])

    full_answer = "".join(full_answer_parts)
    if not full_answer:
        full_answer = "抱歉，暂时无法生成回答。请稍后重试。"

    done_data = {
        "task_id": task_id,
        "intent": "knowledge",
        "result_type": "answer",
        "items": [],
        "summary": "",
        "answer": full_answer,
        "citations": citations,
    }
    await queue.put({"event": "done", "data": done_data})

    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id,
            task_id=task_id,
            role="assistant",
            content=full_answer,
            result_type="answer",
            answer=full_answer,
            citations=citations,
            intent="knowledge",
        ),
    )


async def _save_assistant_response(*, session_id: str, task_id: str, response) -> None:
    await asyncio.to_thread(
        save_message,
        ChatMessage(
            session_id=session_id,
            task_id=task_id,
            role="assistant",
            content=response.answer,
            result_type=response.result_type,
            items=response.items,
            summary=response.summary,
            answer=response.answer,
            citations=response.citations,
            intent=response.intent,
        ),
    )
