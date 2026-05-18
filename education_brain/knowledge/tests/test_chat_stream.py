import asyncio

import pytest

from knowledge.core.llm import StreamChunk
from knowledge.service import chat_stream


@pytest.mark.anyio
async def test_run_knowledge_stream_builds_done_answer_from_tokens_only(monkeypatch):
    async def inline_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    class FakeGraph:
        def invoke(self, state):
            return {"final_chunks": [{"chunk_text": "ctx"}]}

    async def fake_chat_completion_stream(**kwargs):
        yield StreamChunk(kind="thinking", text="先分析问题")
        yield StreamChunk(kind="content", text="最终")
        yield StreamChunk(kind="thinking", text="再组织答案")
        yield StreamChunk(kind="content", text="回答")

    saved_messages = []

    monkeypatch.setattr(
        "knowledge.processor.query_pipeline.graph.build_retrieval_graph",
        lambda: FakeGraph(),
    )
    monkeypatch.setattr(
        "knowledge.processor.query_pipeline.nodes.answer_generate.chat_completion_stream",
        fake_chat_completion_stream,
    )
    monkeypatch.setattr(chat_stream.asyncio, "to_thread", inline_to_thread)
    monkeypatch.setattr(chat_stream, "get_recent_messages", lambda session_id, limit=6: [])
    monkeypatch.setattr(chat_stream, "save_message", lambda message: saved_messages.append(message))

    queue = asyncio.Queue()
    await chat_stream._run_knowledge_stream(
        task_id="task-1",
        session_id="session-1",
        query="什么是反向传播算法？",
        queue=queue,
    )

    events = []
    while not queue.empty():
        events.append(await queue.get())

    thinking_texts = [e["data"]["text"] for e in events if e["event"] == "thinking"]
    token_texts = [e["data"]["text"] for e in events if e["event"] == "token"]
    done_event = next(e for e in events if e["event"] == "done")

    assert thinking_texts == ["先分析问题", "再组织答案"]
    assert token_texts == ["最终", "回答"]
    assert done_event["data"]["answer"] == "最终回答"
    for thinking in thinking_texts:
        assert thinking not in done_event["data"]["answer"]

    assert saved_messages
    assert saved_messages[0].answer == "最终回答"
