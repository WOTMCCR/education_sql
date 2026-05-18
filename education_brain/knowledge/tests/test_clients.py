from types import SimpleNamespace

from knowledge.core import clients


def test_get_openai_uses_timeout_for_local_base_url(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(clients, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        clients,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="dummy",
            openai_base_url="http://localhost:11434/v1",
            openai_timeout_seconds=3.0,
        ),
    )

    clients.get_openai.cache_clear()
    try:
        clients.get_openai()
    finally:
        clients.get_openai.cache_clear()

    http_client = captured["http_client"]
    assert captured["max_retries"] == 0
    assert http_client.timeout.connect == 3.0
    assert http_client.timeout.read == 3.0
