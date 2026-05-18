import asyncio

from fastapi.testclient import TestClient

from knowledge.api.app import app
from knowledge.api.routes import chat as chat_route
from knowledge.api.routes.chat import ChatRequest, chat_history, chat_query, chat_query_stream
from knowledge.models.chat import ChatResponse
from knowledge.models.intent import IntentResult
from knowledge.service import chat_sync, chat_stream


async def _inline_to_thread(fn, *args, **kwargs):
    return fn(*args, **kwargs)


def test_chat_query_routes_search_intent_without_invoking_graph(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)

    monkeypatch.setattr(
        chat_route,
        "classify_intent",
        lambda query: IntentResult(
            intent="course_intro",
            slots={"keyword": "Python"},
            confidence="rule",
        ),
    )
    monkeypatch.setattr(
        chat_route,
        "save_message",
        lambda message: saved_messages.append(message),
    )
    monkeypatch.setattr(
        chat_route,
        "handle_chat_intent",
        lambda **kwargs: ChatResponse(
            task_id=kwargs["task_id"],
            intent="course_intro",
            result_type="search_result",
            items=[{"title": "Python 基础", "series_code": "python-101"}],
            summary="找到 1 门课程",
            answer="找到 1 门课程",
            citations=[],
        ),
    )

    payload = asyncio.run(chat_query(ChatRequest(query="有哪些 Python 相关课程"))).model_dump()
    assert payload["intent"] == "course_intro"
    assert payload["result_type"] == "search_result"
    assert payload["summary"] == "找到 1 门课程"
    assert payload["answer"] == "找到 1 门课程"
    assert payload["items"] == [{"title": "Python 基础", "series_code": "python-101"}]
    assert len(saved_messages) == 2
    assert saved_messages[1].result_type == "search_result"


def test_chat_query_routes_answer_intent_to_graph(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)

    monkeypatch.setattr(
        chat_route,
        "classify_intent",
        lambda query: IntentResult(intent="knowledge", slots={}, confidence="rule"),
    )
    monkeypatch.setattr(
        chat_route,
        "save_message",
        lambda message: saved_messages.append(message),
    )
    monkeypatch.setattr(
        chat_route,
        "handle_chat_intent",
        lambda **kwargs: ChatResponse(
            task_id=kwargs["task_id"],
            intent="knowledge",
            result_type="answer",
            answer="排序算法各有适用场景",
            citations=[{"index": 1, "doc_title": "算法讲义"}],
        ),
    )

    payload = asyncio.run(chat_query(ChatRequest(query="对比一下几种排序算法的优劣"))).model_dump()
    assert payload["intent"] == "knowledge"
    assert payload["result_type"] == "answer"
    assert payload["answer"] == "排序算法各有适用场景"
    assert payload["citations"] == [{"index": 1, "doc_title": "算法讲义"}]
    assert len(saved_messages) == 2
    assert saved_messages[1].answer == "排序算法各有适用场景"


def test_chat_query_routes_learning_path_question_uses_knowledge_intent(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)

    monkeypatch.setattr(
        chat_route,
        "classify_intent",
        lambda query: IntentResult(intent="knowledge", slots={}, confidence="rule"),
    )
    monkeypatch.setattr(
        chat_route,
        "save_message",
        lambda message: saved_messages.append(message),
    )
    monkeypatch.setattr(
        chat_route,
        "handle_chat_intent",
        lambda **kwargs: ChatResponse(
            task_id=kwargs["task_id"],
            intent="knowledge",
            result_type="answer",
            answer="可以先补数据结构，再进入后端框架实践。",
            citations=[],
        ),
    )

    payload = asyncio.run(chat_query(ChatRequest(query="学完 Python 基础后应该学什么"))).model_dump()
    assert payload["intent"] == "knowledge"
    assert payload["result_type"] == "answer"
    assert len(saved_messages) == 2
    assert saved_messages[0].intent == "knowledge"
    assert saved_messages[1].intent == "knowledge"


def test_chat_history_returns_full_message_fields(monkeypatch):
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(
        chat_route,
        "get_recent_messages",
        lambda session_id, limit=10: [
            {
                "role": "assistant",
                "content": "找到 1 门课程",
                "intent": "course_intro",
                "result_type": "search_result",
                "items": [{"title": "Python 基础"}],
                "summary": "找到 1 门课程",
                "answer": "找到 1 门课程",
                "citations": [],
                "created_at": "2026-04-18T12:00:00Z",
            }
        ],
    )

    payload = asyncio.run(chat_history(session_id="s1", limit=10))
    assert payload["messages"][0]["result_type"] == "search_result"
    assert payload["messages"][0]["items"] == [{"title": "Python 基础"}]
    assert payload["messages"][0]["created_at"] == "2026-04-18T12:00:00Z"


def test_handle_course_uses_module_only_copy_when_no_direct_match(monkeypatch):
    monkeypatch.setattr(
        chat_sync,
        "search_courses",
        lambda **kwargs: {
            "total": 1,
            "page": 1,
            "size": 10,
            "items": [
                {
                    "series_code": "data-101",
                    "title": "数据分析求职班",
                    "description": "数据分析课程",
                    "match_level": "module",
                    "matched_modules": ["SQL/Python数据处理基础"],
                    "modules": [],
                    "related_documents": [],
                }
            ],
        },
    )

    summary, items, citations = chat_route._handle_course({"keyword": "Python"})

    assert summary.startswith("没找到完全同名的 Python 课程")
    assert items[0]["match_level"] == "module"
    assert citations == []


def test_handle_question_uses_assistant_style_summary(monkeypatch):
    monkeypatch.setattr(
        chat_sync,
        "search_questions",
        lambda **kwargs: {
            "total": 1,
            "page": 1,
            "size": 5,
            "items": [
                {
                    "question_type": "多选题",
                    "stem": "关于递归，哪些说法是正确的？",
                }
            ],
        },
    )

    summary, items, citations = chat_route._handle_question(
        {"keyword": "Python", "question_type": "多选题"}
    )

    assert summary.startswith("先给你 1 道和 Python 相关的多选题")
    assert "关于递归，哪些说法是正确的？" in summary
    assert items[0]["question_type"] == "多选题"
    assert citations == []


def test_chat_query_stream_accepts_search_intent_and_returns_processing(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_stream.asyncio, "to_thread", _inline_to_thread)

    async def fake_run_stream_pipeline(**kwargs):
        return None

    monkeypatch.setattr(
        chat_stream,
        "classify_intent",
        lambda query: IntentResult(
            intent="course_intro",
            slots={"keyword": "Python"},
            confidence="rule",
        ),
    )
    monkeypatch.setattr(
        chat_stream,
        "save_message",
        lambda message: saved_messages.append(message),
    )
    monkeypatch.setattr(chat_stream, "run_stream_pipeline", fake_run_stream_pipeline)

    payload = asyncio.run(chat_query_stream(ChatRequest(query="有哪些 Python 课程？"))).model_dump()
    assert payload["intent"] == "course_intro"
    assert payload["status"] == "processing"
    assert payload["task_id"]
    assert len(saved_messages) == 1
    assert saved_messages[0].intent == "course_intro"


def test_chat_query_stream_can_complete_search_intent_via_sse(monkeypatch):
    monkeypatch.setattr(chat_stream.asyncio, "to_thread", _inline_to_thread)

    async def fake_run_stream_pipeline(**kwargs):
        queue = kwargs["queue"]
        await queue.put(
            {
                "event": "done",
                "data": {
                    "task_id": kwargs["task_id"],
                    "intent": "course_intro",
                    "result_type": "search_result",
                    "items": [{"title": "Python 基础", "series_code": "python-101"}],
                    "summary": "找到 1 门课程",
                    "answer": "找到 1 门课程",
                    "citations": [],
                },
            }
        )

    monkeypatch.setattr(
        chat_stream,
        "classify_intent",
        lambda query: IntentResult(
            intent="course_intro",
            slots={"keyword": "Python"},
            confidence="rule",
        ),
    )
    monkeypatch.setattr(chat_stream, "save_message", lambda message: None)
    monkeypatch.setattr(chat_stream, "run_stream_pipeline", fake_run_stream_pipeline)

    submit = asyncio.run(chat_query_stream(ChatRequest(query="有哪些 Python 课程？")))
    task_id = submit.task_id

    async def collect_stream():
        chunks = []
        async for chunk in chat_stream.sse_event_generator(task_id):
            chunks.append(chunk)
        return "".join(chunks)

    text = asyncio.run(collect_stream())
    assert "event: done" in text
    assert '"intent": "course_intro"' in text
    assert '"result_type": "search_result"' in text
