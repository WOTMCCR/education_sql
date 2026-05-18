from knowledge.service.course_search import search_courses


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def skip(self, count):
        self._items = self._items[count:]
        return self

    def limit(self, count):
        self._items = self._items[:count]
        return self

    def sort(self, key, direction):
        reverse = direction == -1
        self._items.sort(key=lambda item: item.get(key, 0), reverse=reverse)
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

    def distinct(self, key, query):
        return list(
            {
                item[key]
                for item in self.items
                if _matches(item, query)
            }
        )

    def count_documents(self, query):
        return sum(1 for item in self.items if _matches(item, query))

    def find(self, query, projection):
        del projection
        return _FakeCursor(
            [item.copy() for item in self.items if _matches(item, query)]
        )


def test_search_courses_filters_by_keyword_and_related_modules(monkeypatch):
    db = {
        "course_series": _FakeCollection(
            [
                {
                    "series_code": "python-101",
                    "title": "Python 基础",
                    "description": "从零开始学 Python",
                    "category_path": "编程/Python",
                    "audience": "在校生",
                    "goal_tags": "就业",
                },
                {
                    "series_code": "java-101",
                    "title": "Java 基础",
                    "description": "从零开始学 Java",
                    "category_path": "编程/Java",
                    "audience": "在校生",
                    "goal_tags": "就业",
                },
            ]
        ),
        "course_module": _FakeCollection(
            [
                {
                    "series_code": "python-101",
                    "module_title": "Python 数据类型",
                    "module_desc": "掌握 list 与 dict",
                    "sort_order": 2,
                },
                {
                    "series_code": "python-101",
                    "module_title": "Python 入门",
                    "module_desc": "语法基础",
                    "sort_order": 1,
                },
            ]
        ),
        "source_mapping": _FakeCollection(
            [
                {
                    "series_code": "python-101",
                    "source_file": "python.md",
                    "doc_id": "doc-1",
                    "mapping_type": "course_doc",
                }
            ]
        ),
    }
    monkeypatch.setattr("knowledge.service.course_search.get_mongo_db", lambda: db)

    result = search_courses(keyword="Python", audience="在校生", page=1, size=10)

    assert result["total"] == 1
    assert [item["series_code"] for item in result["items"]] == ["python-101"]
    assert [module["module_title"] for module in result["items"][0]["modules"]] == [
        "Python 入门",
        "Python 数据类型",
    ]
    assert result["items"][0]["related_documents"] == [
        {
            "series_code": "python-101",
            "source_file": "python.md",
            "doc_id": "doc-1",
            "mapping_type": "course_doc",
        }
    ]


def test_search_courses_marks_match_level_and_demotes_module_only_hits(monkeypatch):
    db = {
        "course_series": _FakeCollection(
            [
                {
                    "series_code": "python-101",
                    "title": "Python 基础",
                    "description": "从零开始学 Python",
                    "category_path": "编程/Python",
                },
                {
                    "series_code": "data-101",
                    "title": "数据分析求职班",
                    "description": "数据分析课程",
                    "category_path": "数据分析",
                },
            ]
        ),
        "course_module": _FakeCollection(
            [
                {
                    "series_code": "data-101",
                    "module_title": "SQL/Python数据处理基础",
                    "module_desc": "包含 Python 数据处理",
                    "sort_order": 1,
                }
            ]
        ),
        "source_mapping": _FakeCollection([]),
    }
    monkeypatch.setattr("knowledge.service.course_search.get_mongo_db", lambda: db)

    result = search_courses(keyword="Python", page=1, size=10)

    assert [item["series_code"] for item in result["items"]] == ["python-101", "data-101"]
    assert result["items"][0]["match_level"] == "title"
    assert result["items"][1]["match_level"] == "module"
    assert result["items"][1]["matched_modules"] == ["SQL/Python数据处理基础"]
