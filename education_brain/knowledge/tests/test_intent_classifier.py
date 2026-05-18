from types import SimpleNamespace

import logging
from knowledge.service import intent_classifier


def test_classify_intent_extracts_course_keyword_from_rule(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("有哪些 Python 相关课程")

    assert result.intent == "course_intro"
    assert result.slots == {"keyword": "Python"}
    assert result.confidence == "rule"


def test_parse_normalized_query_result_reads_json_and_hints():
    parsed = intent_classifier._parse_normalized_query_result(
        '{"normalized_query":"课程介绍","hints":{"intent":"course_intro","question_type":""}}'
    )

    assert parsed == {
        "normalized_query": "课程介绍",
        "hints": {"intent": "course_intro"},
    }


def test_classify_intent_uses_normalized_query_before_rule_matching(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "normalize_query_for_intent",
        lambda query: {
            "normalized_query": "课程介绍",
            "hints": {},
        },
    )

    result = intent_classifier.classify_intent("给我介绍介绍 有什么课程")

    assert result.intent == "course_intro"
    assert result.slots == {}
    assert result.confidence == "rule"


def test_normalize_query_for_intent_logs_original_and_normalized_query(monkeypatch, caplog):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="dummy", llm_model="dummy-model"),
    )
    monkeypatch.setattr(
        intent_classifier,
        "chat_completion_text",
        lambda **kwargs: '{"normalized_query":"课程介绍","hints":{"intent":"course_intro"}}',
    )

    with caplog.at_level(logging.INFO, logger="knowledge.service.intent_classifier"):
        result = intent_classifier.normalize_query_for_intent("给我介绍介绍 有什么课程")

    assert result["normalized_query"] == "课程介绍"
    assert any("意图前置规范化完成" in message for message in caplog.messages)
    assert any("课程介绍" in message for message in caplog.messages)


def test_classify_intent_logs_final_decision(monkeypatch, caplog):
    monkeypatch.setattr(
        intent_classifier,
        "normalize_query_for_intent",
        lambda query: {
            "normalized_query": "课程介绍",
            "hints": {},
        },
    )

    with caplog.at_level(logging.INFO, logger="knowledge.service.intent_classifier"):
        result = intent_classifier.classify_intent("给我介绍介绍 有什么课程")

    assert result.intent == "course_intro"
    assert any("意图分类完成" in message for message in caplog.messages)
    assert any("course_intro" in message for message in caplog.messages)


def test_classify_intent_extracts_question_type_and_keyword(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("有没有数据类型的选择题")

    assert result.intent == "question_search"
    assert result.slots == {
        "keyword": "数据类型",
        "question_type": "选择题",
    }
    assert result.confidence == "rule"


def test_classify_intent_does_not_extract_quantity_words_as_question_keyword(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("给我几道多选题")

    assert result.intent == "question_search"
    assert result.slots == {"question_type": "多选题"}
    assert result.confidence == "rule"


def test_classify_intent_handles_basic_english_course_query(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("Python courses")

    assert result.intent == "course_intro"
    assert result.slots == {"keyword": "Python"}
    assert result.confidence == "rule"


def test_classify_intent_treats_explicit_course_phrase_as_course_intro(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("大模型开发课程")

    assert result.intent == "course_intro"
    assert result.slots == {"keyword": "大模型开发"}
    assert result.confidence == "rule"


def test_classify_intent_knowledge_rule_does_not_call_llm(monkeypatch):
    called = {"value": False}

    monkeypatch.setattr(
        intent_classifier,
        "normalize_query_for_intent",
        lambda query: {
            "normalized_query": query,
            "hints": {},
        },
    )

    def fake_chat_completion_text(**kwargs):
        called["value"] = True
        return '{"intent":"knowledge","slots":{}}'

    monkeypatch.setattr(
        intent_classifier,
        "chat_completion_text",
        fake_chat_completion_text,
    )
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="dummy",
            llm_model="dummy-model",
        ),
    )

    result = intent_classifier.classify_intent("对比一下几种排序算法的优劣")

    assert result.intent == "knowledge"
    assert result.slots == {}
    assert called["value"] is False


def test_classify_intent_parses_llm_json_response(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "chat_completion_text",
        lambda **kwargs: '{"intent":"knowledge","slots":{"keyword":"PyTorch"}}',
    )
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="dummy",
            llm_model="dummy-model",
        ),
    )

    result = intent_classifier.classify_intent("PyTorch 资料整理")

    assert result.intent == "knowledge"
    assert result.slots == {"keyword": "PyTorch"}
    assert result.confidence == "llm"


def test_classify_intent_treats_learning_path_question_as_knowledge(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("学完 Python 基础后应该学什么")

    assert result.intent == "knowledge"
    assert result.slots == {}
    assert result.confidence in {"rule", "default"}


def test_classify_intent_treats_how_to_question_as_knowledge_without_llm(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = intent_classifier.classify_intent("Python 怎么连接 MySQL")

    assert result.intent == "knowledge"
    assert result.slots == {}
    assert result.confidence in {"rule", "default"}
