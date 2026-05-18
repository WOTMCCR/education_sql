import asyncio

import pytest

from knowledge.service import chat_stream


@pytest.mark.anyio
async def test_run_knowledge_stream_builds_done_answer_from_tokens_only(monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            return {"final_chunks": [{"chunk_text": "ctx"}]}

    async def fake_answer_generate_stream(state):
        yield {"event": "thinking", "data": {"text": "先分析问题"}}
        yield {"event": "token", "data": {"text": "最终"}}
        yield {"event": "thinking", "data": {"text": "再组织答案"}}
        yield {"event": "token", "data": {"text": "回答"}}
        yield {
            "event": "citation",
            "data": {"citations": [{"index": 1, "doc_title": "算法讲义"}]},
        }

    saved_messages = []

    monkeypatch.setattr(
        "knowledge.processor.query_pipeline.graph.build_retrieval_graph",
        lambda: FakeGraph(),
    )
    monkeypatch.setattr(
        "knowledge.processor.query_pipeline.nodes.answer_generate.answer_generate_stream",
        fake_answer_generate_stream,
    )
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
