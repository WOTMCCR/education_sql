from __future__ import annotations

import importlib
import json
from typing import Any

import pytest

from knowledge.analytics.agent.pipeline import run_data_qa
from knowledge.tests.data_qa_test_fixtures import install_data_qa_meta_fixtures


def _load_llm_contract() -> tuple[Any, type[Any]]:
    try:
        llm_utils = importlib.import_module("knowledge.analytics.agent.llm_utils")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Missing Iteration 03 LLM parser module: {exc}")

    schema_module_names = [
        "knowledge.analytics.agent.llm_schemas",
        "knowledge.analytics.agent.schemas",
        "knowledge.analytics.agent.llm_utils",
    ]
    schema_module = None
    for module_name in schema_module_names:
        try:
            schema_module = importlib.import_module(module_name)
            if hasattr(schema_module, "StructuredIntent"):
                break
        except ModuleNotFoundError:
            continue
    if schema_module is None or not hasattr(schema_module, "StructuredIntent"):
        pytest.fail("Missing Pydantic schema: StructuredIntent")

    parser = None
    for name in ("parse_llm_json", "parse_llm_schema", "parse_structured_output", "parse_pydantic_json"):
        candidate = getattr(llm_utils, name, None)
        if callable(candidate):
            parser = candidate
            break
    if parser is None:
        pytest.fail("Missing LLM JSON parser function in knowledge.analytics.agent.llm_utils")

    return parser, getattr(schema_module, "StructuredIntent")


def _parse_with_contract(parser: Any, model_cls: type[Any], text: str) -> Any:
    try:
        return parser(text, model_cls)
    except TypeError:
        return parser(model_cls, text)


def _intent_payload() -> dict[str, Any]:
    return {
        "analysisType": "single_metric",
        "metrics": ["paid_revenue"],
        "dimensions": ["campus"],
        "filters": [{"field": "org_campus.name", "op": "eq", "value": "朝阳校区", "label": "朝阳校区"}],
        "timeRange": {
            "start": "2026-05-01",
            "end": "2026-05-18",
            "endExclusive": "2026-05-19",
            "grain": "day",
            "label": "本月",
        },
        "sort": [],
        "limit": None,
        "visualHint": "stat",
    }


@pytest.mark.parametrize(
    "raw_text",
    [
        json.dumps(_intent_payload(), ensure_ascii=False),
        "```json\n" + json.dumps(_intent_payload(), ensure_ascii=False) + "\n```",
        "模型解释前缀\n" + json.dumps(_intent_payload(), ensure_ascii=False) + "\n模型解释后缀",
    ],
)
def test_llm_schema_parser_accepts_json_variants(raw_text: str):
    parser, StructuredIntent = _load_llm_contract()

    parsed = _parse_with_contract(parser, StructuredIntent, raw_text)

    dumped = parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)
    assert dumped["analysisType"] == "single_metric"
    assert dumped["metrics"] == ["paid_revenue"]
    assert dumped["filters"][0]["value"] == "朝阳校区"


def test_llm_schema_parser_rejects_missing_required_fields():
    parser, StructuredIntent = _load_llm_contract()
    incomplete = {"metrics": ["paid_revenue"], "dimensions": []}

    with pytest.raises(Exception):
        _parse_with_contract(parser, StructuredIntent, json.dumps(incomplete, ensure_ascii=False))


def test_llm_unavailable_returns_structured_error_without_rule_fallback(monkeypatch):
    from knowledge.analytics.agent.graph import build_data_qa_graph
    from knowledge.core import llm

    install_data_qa_meta_fixtures(monkeypatch)
    calls: list[dict[str, Any]] = []

    def unavailable_chat_completion_text(**kwargs: Any) -> None:
        calls.append(kwargs)
        return None

    monkeypatch.setattr(llm, "chat_completion_text", unavailable_chat_completion_text)
    build_data_qa_graph.cache_clear()

    result = run_data_qa("朝阳校区本月收入是多少？", session_id="pytest-llm-unavailable")

    assert calls, "LLM NL2SQL must call knowledge.core.llm.chat_completion_text"
    assert result.get("error", {}).get("code") == "LLM_UNAVAILABLE"
    assert not result["explain"]["sql"]
    assert any(stage["name"] == "execute_sql" and stage["status"] == "skipped" for stage in result["trace"]["stages"])


def test_llm_generated_dangerous_sql_is_skipped(monkeypatch):
    from knowledge.analytics.agent.graph import build_data_qa_graph
    from knowledge.core import llm

    install_data_qa_meta_fixtures(monkeypatch)
    calls: list[str] = []

    def fake_chat_completion_text(**kwargs: Any) -> str:
        purpose = str(kwargs.get("purpose", ""))
        messages = kwargs.get("messages") or []
        prompt_text = "\n".join(str(message.get("content", "")) for message in messages)
        marker = f"{purpose}\n{prompt_text}".lower()
        calls.append(marker)
        if purpose.endswith("expand_search_keywords"):
            return json.dumps(
                {
                    "expanded_keywords": ["朝阳校区", "本月", "收入", "实付金额", "paid_revenue", "campus"],
                    "search_keywords": {
                        "metrics": ["收入", "paid_revenue"],
                        "dimensions": ["校区", "campus"],
                        "values": ["朝阳校区"],
                    },
                },
                ensure_ascii=False,
            )
        if purpose.endswith("structure_intent"):
            return json.dumps(_intent_payload(), ensure_ascii=False)
        if purpose.endswith("filter_table") or purpose.endswith("filter_metric"):
            return json.dumps(
                {
                    "selectedIds": ["paid_revenue", "order", "org_campus"],
                    "rejectedIds": [],
                    "reason": "select candidates for malicious SQL safety test",
                },
                ensure_ascii=False,
            )
        if purpose.endswith("generate_sql"):
            return json.dumps(
                {
                    "sql": "DROP TABLE `order`",
                    "visual": {"type": "table", "y": []},
                    "usedTables": ["order"],
                    "usedColumns": ["order.paid_amount"],
                    "usedMetrics": ["paid_revenue"],
                    "joins": [],
                    "assumptions": ["malicious model output for safety regression coverage"],
                },
                ensure_ascii=False,
            )
        return json.dumps({}, ensure_ascii=False)

    monkeypatch.setattr(llm, "chat_completion_text", fake_chat_completion_text)
    build_data_qa_graph.cache_clear()

    result = run_data_qa("朝阳校区本月收入是多少？", session_id="pytest-dangerous-llm-sql")

    assert calls, "LLM NL2SQL must call knowledge.core.llm.chat_completion_text"
    assert result.get("error", {}).get("code") == "SQL_UNSAFE"
    assert any(stage["name"] == "execute_sql" and stage["status"] == "skipped" for stage in result["trace"]["stages"])
    assert not any(stage["name"] == "execute_sql" and stage["status"] == "ok" for stage in result["trace"]["stages"])
