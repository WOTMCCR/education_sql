from datetime import datetime, timezone

from knowledge.models.chat import ChatMessage
from knowledge.service import chat_history


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def sort(self, key, direction):
        reverse = direction == -1
        self._items.sort(key=lambda item: item[key], reverse=reverse)
        return self

    def limit(self, limit):
        self._items = self._items[:limit]
        return self

    def __iter__(self):
        return iter(self._items)


class _FakeCollection:
    def __init__(self):
        self.items = []

    def insert_one(self, item):
        self.items.append(item)

    def find(self, query, projection):
        del projection
        items = [
            item
            for item in self.items
            if item.get("session_id") == query.get("session_id")
        ]
        return _FakeCursor(items)


def test_chat_history_saves_and_reads_complete_message(monkeypatch):
    collection = _FakeCollection()
    db = {"chat_history": collection}
    monkeypatch.setattr(chat_history, "get_mongo_db", lambda: db)

    created_at = datetime(2026, 4, 18, tzinfo=timezone.utc)
    message = ChatMessage(
        session_id="s1",
        task_id="task-1",
        role="assistant",
        content="找到 1 门课程",
        intent="data_qa",
        mode="data_qa",
        result_type="data_qa_result",
        items=[],
        summary="本月总收入为 123.00 元。",
        answer="本月总收入为 123.00 元。",
        citations=[],
        blocks=[
            {"type": "markdown", "content": "本月总收入为 123.00 元。"},
            {
                "type": "data_qa_result",
                "data": {
                    "queryId": "q-1",
                    "mode": "data_qa",
                    "visual": {"type": "stat", "columns": [], "rows": []},
                    "explain": {"sql": "SELECT 123"},
                    "trace": {"stages": []},
                },
            },
        ],
        created_at=created_at,
    )

    chat_history.save_message(message)
    result = chat_history.get_recent_messages("s1", limit=10)

    assert result == [
        {
            "session_id": "s1",
            "task_id": "task-1",
            "role": "assistant",
            "content": "找到 1 门课程",
            "mode": "data_qa",
            "intent": "data_qa",
            "result_type": "data_qa_result",
            "items": [],
            "summary": "本月总收入为 123.00 元。",
            "answer": "本月总收入为 123.00 元。",
            "citations": [],
            "blocks": [
                {"type": "markdown", "content": "本月总收入为 123.00 元。"},
                {
                    "type": "data_qa_result",
                    "data": {
                        "queryId": "q-1",
                        "mode": "data_qa",
                        "visual": {"type": "stat", "columns": [], "rows": []},
                        "explain": {"sql": "SELECT 123"},
                        "trace": {"stages": []},
                    },
                },
            ],
            "created_at": created_at,
        }
    ]
