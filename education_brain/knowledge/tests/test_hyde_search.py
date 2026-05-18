from types import SimpleNamespace

from knowledge.processor.query_pipeline.nodes import hyde_search


def test_hyde_search_skips_when_hypothesis_empty(monkeypatch):
    monkeypatch.setattr(
        hyde_search,
        "get_settings",
        lambda: SimpleNamespace(query_search_limit=5),
    )
    monkeypatch.setattr(
        hyde_search,
        "_generate_hypothesis",
        lambda query, s: "",
    )

    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("无 hypothesis 时不应编码检索")

    monkeypatch.setattr(hyde_search, "encode_bge_queries", fail_if_called)

    result = hyde_search.hyde_search(
        {"original_query": "Python", "rewritten_query": "Python"}
    )

    assert result == {"hyde_chunks": []}
    assert called["value"] is False


def test_generate_hypothesis_does_not_trigger_global_cooldown(monkeypatch):
    monkeypatch.setattr(
        hyde_search,
        "chat_completion_text",
        lambda **kwargs: kwargs,
    )

    settings = SimpleNamespace(
        openai_api_key="dummy",
        effective_hyde_model="hyde-model",
    )

    result = hyde_search._generate_hypothesis("排序算法", settings)

    assert result["trigger_cooldown"] is False
    assert result["model"] == "hyde-model"
