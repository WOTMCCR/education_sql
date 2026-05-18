from types import SimpleNamespace

from knowledge.processor.query_pipeline import graph


def test_fan_out_router_skips_hyde_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="",
            effective_hyde_model="",
            enable_hyde=True,
        ),
    )

    routes = graph._fan_out_router({"original_query": "Python"})

    assert routes == ["vector_search"]


def test_fan_out_router_skips_hyde_when_disabled(monkeypatch):
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="dummy",
            effective_hyde_model="dummy-model",
            enable_hyde=False,
        ),
    )

    routes = graph._fan_out_router({"original_query": "Python"})

    assert routes == ["vector_search"]


def test_fan_out_router_uses_hyde_when_available(monkeypatch):
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="dummy",
            effective_hyde_model="dummy-model",
            enable_hyde=True,
        ),
    )

    routes = graph._fan_out_router({"original_query": "Python"})

    assert routes == ["vector_search", "hyde_search"]
