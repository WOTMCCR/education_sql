from types import SimpleNamespace

import pytest
from knowledge.core import llm


def test_chat_completion_text_passes_per_call_timeout(monkeypatch):
    captured = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)

            class _Message:
                content = "ok"

            class _Choice:
                message = _Message()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    monkeypatch.setattr(llm, "get_openai", lambda: FakeClient())
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(openai_timeout_seconds=2.5),
    )

    result = llm.chat_completion_text(
        model="dummy-model",
        messages=[{"role": "user", "content": "hi"}],
        purpose="test",
    )

    assert result == "ok"
    assert captured["timeout"] == 2.5


def test_chat_completion_text_allows_overriding_timeout(monkeypatch):
    captured = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)

            class _Message:
                content = "ok"

            class _Choice:
                message = _Message()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    monkeypatch.setattr(llm, "get_openai", lambda: FakeClient())
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(openai_timeout_seconds=2.5),
    )

    result = llm.chat_completion_text(
        model="dummy-model",
        messages=[{"role": "user", "content": "hi"}],
        purpose="test",
        timeout=9.0,
    )

    assert result == "ok"
    assert captured["timeout"] == 9.0


def test_chat_completion_text_skips_during_failure_cooldown(monkeypatch):
    calls = {"count": 0}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            calls["count"] += 1
            raise RuntimeError("boom")

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    monkeypatch.setattr(llm, "get_openai", lambda: FakeClient())
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_timeout_seconds=2.5,
            llm_failure_cooldown_seconds=30.0,
        ),
    )

    llm._llm_unavailable_until = 0.0
    try:
        first = llm.chat_completion_text(
            model="dummy-model",
            messages=[{"role": "user", "content": "hi"}],
            purpose="test1",
        )
        second = llm.chat_completion_text(
            model="dummy-model",
            messages=[{"role": "user", "content": "hi again"}],
            purpose="test2",
        )
    finally:
        llm._llm_unavailable_until = 0.0

    assert first is None
    assert second is None
    assert calls["count"] == 1


def test_chat_completion_text_can_fail_without_triggering_cooldown(monkeypatch):
    calls = {"count": 0}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            calls["count"] += 1
            raise RuntimeError("boom")

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    monkeypatch.setattr(llm, "get_openai", lambda: FakeClient())
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_timeout_seconds=2.5,
            llm_failure_cooldown_seconds=30.0,
        ),
    )

    llm._llm_unavailable_until = 0.0
    try:
        first = llm.chat_completion_text(
            model="dummy-model",
            messages=[{"role": "user", "content": "hi"}],
            purpose="test1",
            trigger_cooldown=False,
        )
        second = llm.chat_completion_text(
            model="dummy-model",
            messages=[{"role": "user", "content": "hi again"}],
            purpose="test2",
            trigger_cooldown=False,
        )
    finally:
        llm._llm_unavailable_until = 0.0

    assert first is None
    assert second is None
    assert calls["count"] == 2


def test_chat_completion_text_falls_back_to_ollama_no_think_when_content_empty(monkeypatch):
    class _Message:
        content = ""
        reasoning = "Thinking..."

    class _Choice:
        message = _Message()

    class _Resp:
        choices = [_Choice()]

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return _Resp()

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    monkeypatch.setattr(llm, "get_openai", lambda: FakeClient())
    monkeypatch.setattr(
        llm,
        "_chat_via_ollama_api",
        lambda **kwargs: "final answer",
    )
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_timeout_seconds=2.5,
            openai_base_url="http://localhost:11434/v1",
            llm_failure_cooldown_seconds=30.0,
        ),
    )

    result = llm.chat_completion_text(
        model="qwen3.5:latest",
        messages=[{"role": "user", "content": "hi"}],
        purpose="test",
        max_tokens=128,
    )

    assert result == "final answer"


@pytest.mark.anyio
async def test_chat_completion_stream_falls_back_when_openai_stream_has_reasoning_only(monkeypatch):
    class FakeDelta:
        reasoning = "Thinking..."
        reasoning_content = None
        content = ""

    class FakeChunk:
        choices = [SimpleNamespace(delta=FakeDelta())]

    class FakeResponse:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_done", False):
                raise StopAsyncIteration
            self._done = True
            return FakeChunk()

    class FakeCompletions:
        @staticmethod
        async def create(**kwargs):
            return FakeResponse()

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    async def fake_stream_via_ollama_api(**kwargs):
        yield llm.StreamChunk(kind="content", text="final answer")

    monkeypatch.setattr("knowledge.core.clients.get_async_openai", lambda: FakeClient())
    monkeypatch.setattr(llm, "_stream_via_ollama_api", fake_stream_via_ollama_api)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            answer_timeout_seconds=30.0,
            openai_base_url="http://localhost:11434/v1",
        ),
    )

    chunks = [
        chunk
        async for chunk in llm.chat_completion_stream(
            model="qwen3.5:latest",
            messages=[{"role": "user", "content": "hi"}],
            purpose="test",
            max_tokens=128,
        )
    ]

    assert chunks == [
        llm.StreamChunk(kind="thinking", text="Thinking..."),
        llm.StreamChunk(kind="content", text="final answer"),
    ]


@pytest.mark.anyio
async def test_stream_via_ollama_api_disables_thinking_and_yields_content(monkeypatch):
    captured = {}

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield '{"message":{"role":"assistant","content":"答复片段"},"done":false}'
            yield '{"done":true}'

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url, json):
            captured["method"] = method
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(llm._httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(openai_base_url="http://localhost:11434/v1"),
    )

    chunks = [
        chunk
        async for chunk in llm._stream_via_ollama_api(
            model="qwen3.5:latest",
            messages=[{"role": "user", "content": "hi"}],
            timeout=30.0,
            max_tokens=128,
        )
    ]

    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"] == {"num_predict": 128}
    assert chunks == [llm.StreamChunk(kind="content", text="答复片段")]
