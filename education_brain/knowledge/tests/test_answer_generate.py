from types import SimpleNamespace

from knowledge.processor.query_pipeline.nodes import answer_generate
from knowledge.prompt.query_prompt import ANSWER_SYSTEM_PROMPT


def test_generate_answer_uses_answer_timeout_without_global_cooldown(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        answer_generate,
        "chat_completion_text",
        lambda **kwargs: captured.update(kwargs) or "ok",
    )

    settings = SimpleNamespace(
        openai_api_key="dummy",
        effective_answer_model="answer-model",
        answer_timeout_seconds=120.0,
        answer_max_tokens=512,
    )

    result = answer_generate._generate_answer("排序算法", "上下文", settings)

    assert result == "ok"
    assert captured["timeout"] == 120.0
    assert captured["max_tokens"] == 512
    assert captured["trigger_cooldown"] is False


def test_answer_generate_uses_answer_specific_context_budget(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        answer_generate,
        "_build_context",
        lambda chunks, max_chars: (captured.__setitem__("max_chars", max_chars), ("ctx", []))[1],
    )
    monkeypatch.setattr(
        answer_generate,
        "_generate_answer",
        lambda query, context, settings: "ok",
    )

    monkeypatch.setattr(
        answer_generate,
        "get_settings",
        lambda: SimpleNamespace(
            max_context_chars=12000,
            answer_max_context_chars=4000,
        ),
    )

    result = answer_generate.answer_generate(
        {
            "original_query": "排序算法",
            "final_chunks": [{"chunk_text": "chunk"}],
        }
    )

    assert result["answer"] == "ok"
    assert captured["max_chars"] == 4000


def test_answer_prompt_uses_three_part_contract_for_knowledge_answers():
    assert "直接回答" in ANSWER_SYSTEM_PROMPT
    assert "资料依据" in ANSWER_SYSTEM_PROMPT
    assert "模型补充" in ANSWER_SYSTEM_PROMPT
    assert "不要以“基于提供的参考资料”开头" in ANSWER_SYSTEM_PROMPT
