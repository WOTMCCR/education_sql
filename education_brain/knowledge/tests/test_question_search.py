from knowledge.service.question_search import search_questions


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def skip(self, count):
        self._items = self._items[count:]
        return self

    def limit(self, count):
        self._items = self._items[:count]
        return self

    def __iter__(self):
        return iter(self._items)


def _matches(document, query):
    if not query:
        return True
    if "$and" in query:
        return all(_matches(document, clause) for clause in query["$and"])
    if "$or" in query:
        return any(_matches(document, clause) for clause in query["$or"])

    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict) and "$regex" in expected:
            if expected["$regex"].lower() not in str(value).lower():
                return False
        elif isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        else:
            if value != expected:
                return False
    return True


class _FakeCollection:
    def __init__(self, items):
        self.items = list(items)

    def count_documents(self, query):
        return sum(1 for item in self.items if _matches(item, query))

    def find(self, query, projection):
        del projection
        return _FakeCursor(
            [item.copy() for item in self.items if _matches(item, query)]
        )


def test_search_questions_supports_keyword_and_normalized_question_type(monkeypatch):
    db = {
        "question_item": _FakeCollection(
            [
                {
                    "question_code": "q1",
                    "bank_code": "python_bank",
                    "question_type": "单选题",
                    "stem": "关于数据类型，下面哪个说法正确？",
                },
                {
                    "question_code": "q2",
                    "bank_code": "python_bank",
                    "question_type": "判断题",
                    "stem": "数据类型可以自动推断。",
                },
            ]
        )
    }
    monkeypatch.setattr("knowledge.service.question_search.get_mongo_db", lambda: db)

    result = search_questions(
        keyword="数据类型",
        bank_code="python_bank",
        question_type="选择题",
        page=1,
        size=10,
    )

    assert result["total"] == 1
    assert result["items"] == [
        {
            "question_code": "q1",
            "bank_code": "python_bank",
            "question_type": "单选题",
            "stem": "关于数据类型，下面哪个说法正确？",
        }
    ]
