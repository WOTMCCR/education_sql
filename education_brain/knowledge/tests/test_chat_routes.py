import asyncio

from fastapi.testclient import TestClient

from knowledge.api.app import app
from knowledge.api.routes import chat as chat_route
from knowledge.api.routes.chat import ChatRequest, chat_history, chat_query


async def _inline_to_thread(fn, *args, **kwargs):
    return fn(*args, **kwargs)


def _data_qa_result() -> dict:
    return {
        "queryId": "q-1",
        "mode": "data_qa",
        "question": "本月总收入是多少？",
        "answer": "本月总收入为 123.00 元。",
        "intent": {
            "analysisType": "single_metric",
            "metrics": ["paid_revenue"],
            "dimensions": [],
            "filters": [],
        },
        "visual": {
            "type": "stat",
            "title": "本月总收入",
            "columns": [{"key": "paid_revenue", "label": "实付收入", "type": "currency"}],
            "rows": [{"paid_revenue": 123}],
        },
        "explain": {
            "sql": "SELECT 123 AS paid_revenue",
            "metrics": [{"id": "paid_revenue", "name": "实付收入", "formula": "sum(x)", "description": ""}],
            "tables": ["orders"],
            "columns": ["paid_amount"],
            "joins": [],
            "assumptions": [],
        },
        "trace": {"stages": [{"name": "execute_sql", "status": "ok"}], "rowCount": 1, "durationMs": 10},
        "warnings": [],
    }


def test_chat_query_data_qa_wraps_result_and_saves_blocks(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(chat_route, "save_message", lambda message: saved_messages.append(message))
    monkeypatch.setattr(chat_route, "run_data_qa", lambda query, session_id=None: _data_qa_result())

    payload = asyncio.run(
        chat_query(ChatRequest(query="本月总收入是多少？", mode="data_qa", session_id="s1"))
    ).model_dump()

    assert payload["mode"] == "data_qa"
    assert payload["intent"] == "data_qa"
    assert payload["result_type"] == "data_qa_result"
    assert payload["answer"] == "本月总收入为 123.00 元。"
    assert payload["blocks"][0] == {"type": "markdown", "content": "本月总收入为 123.00 元。"}
    assert payload["blocks"][1]["type"] == "data_qa_result"
    assert payload["blocks"][1]["data"]["visual"]["type"] == "stat"
    assert len(saved_messages) == 2
    assert saved_messages[0].role == "user"
    assert saved_messages[0].mode == "data_qa"
    assert saved_messages[1].role == "assistant"
    assert saved_messages[1].mode == "data_qa"
    assert saved_messages[1].blocks[1]["data"]["explain"]["sql"]


def test_chat_query_meta_qa_wraps_markdown_citations_and_trace(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(chat_route, "save_message", lambda message: saved_messages.append(message))
    monkeypatch.setattr(
        chat_route,
        "run_meta_qa",
        lambda query, session_id=None: {
            "result_type": "meta_answer",
            "mode": "meta_qa",
            "answer": "实付收入按已支付订单实付金额汇总。",
            "citations": [
                {
                    "kind": "metric",
                    "id": "paid_revenue",
                    "name": "实付收入",
                    "source": "meta_metric_info",
                    "description": "已支付订单的实付金额",
                }
            ],
            "blocks": [
                {"type": "markdown", "content": "实付收入按已支付订单实付金额汇总。"},
                {
                    "type": "meta_citations",
                    "data": [
                        {
                            "kind": "metric",
                            "id": "paid_revenue",
                            "name": "实付收入",
                            "source": "meta_metric_info",
                            "description": "已支付订单的实付金额",
                        }
                    ],
                },
            ],
            "trace": {"stages": [{"name": "meta_qa_llm", "status": "ok"}]},
        },
    )

    payload = asyncio.run(
        chat_query(ChatRequest(query="实付收入怎么算？", mode="meta_qa", session_id="s1"))
    ).model_dump()

    assert payload["mode"] == "meta_qa"
    assert payload["intent"] == "meta_qa"
    assert payload["result_type"] == "meta_answer"
    assert payload["blocks"][1]["type"] == "meta_citations"
    assert payload["trace"]["stages"][0]["name"] == "meta_qa_llm"
    assert saved_messages[1].mode == "meta_qa"
    assert saved_messages[1].blocks[1]["type"] == "meta_citations"
    assert saved_messages[1].trace["stages"][0]["name"] == "meta_qa_llm"


def test_chat_query_auto_routes_data_discovery_to_meta_qa(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(chat_route, "save_message", lambda message: saved_messages.append(message))
    monkeypatch.setattr(chat_route, "run_data_qa", lambda query, session_id=None: (_ for _ in ()).throw(AssertionError("should not run data qa")))
    monkeypatch.setattr(
        chat_route,
        "run_meta_qa",
        lambda query, session_id=None: {
            "result_type": "meta_answer",
            "mode": "meta_qa",
            "answer": "当前可用的表包括订单主表和校区表。",
            "citations": [],
            "blocks": [{"type": "markdown", "content": "当前可用的表包括订单主表和校区表。"}],
            "trace": {"stages": [{"name": "meta_qa_llm", "status": "ok"}]},
        },
    )

    payload = asyncio.run(
        chat_query(ChatRequest(query="现在有哪些表？", mode="data_qa", session_id="s1"))
    ).model_dump()

    assert payload["mode"] == "meta_qa"
    assert payload["intent"] == "meta_qa"
    assert payload["result_type"] == "meta_answer"
    assert payload["blocks"][0]["type"] == "markdown"
    assert saved_messages[0].role == "user"
    assert saved_messages[0].mode == "meta_qa"
    assert saved_messages[1].mode == "meta_qa"


def test_chat_query_requires_explicit_mode():
    client = TestClient(app)

    response = client.post("/chat/query", json={"query": "本月总收入是多少？", "session_id": "s1"})

    assert response.status_code == 400


def test_chat_query_rejects_unknown_mode():
    client = TestClient(app)

    response = client.post(
        "/chat/query",
        json={"query": "讲讲课程", "mode": "knowledge", "session_id": "s1"},
    )

    assert response.status_code == 400


def test_legacy_stream_routes_are_not_registered():
    paths = {route.path for route in app.routes}

    assert "/chat/query/stream" not in paths
    assert "/chat/stream/{task_id}" not in paths


def test_chat_history_returns_mode_and_blocks(monkeypatch):
    monkeypatch.setattr(chat_route.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(
        chat_route,
        "get_recent_messages",
        lambda session_id, limit=10: [
            {
                "role": "assistant",
                "content": "本月总收入为 123.00 元。",
                "mode": "data_qa",
                "intent": "data_qa",
                "result_type": "data_qa_result",
                "blocks": [{"type": "data_qa_result", "data": _data_qa_result()}],
                "answer": "本月总收入为 123.00 元。",
                "created_at": "2026-05-18T12:00:00Z",
            }
        ],
    )

    payload = asyncio.run(chat_history(session_id="s1", limit=10))

    assert payload["messages"][0]["mode"] == "data_qa"
    assert payload["messages"][0]["blocks"][0]["type"] == "data_qa_result"
