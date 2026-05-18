from types import SimpleNamespace

from knowledge.analytics.meta_qa import pipeline
from knowledge.core import llm as core_llm


def test_run_meta_qa_calls_llm_and_filters_citations(monkeypatch):
    monkeypatch.setattr(pipeline, "search_metrics", lambda query, limit: [{"metric_id": "paid_revenue", "id": "paid_revenue"}])
    monkeypatch.setattr(pipeline, "search_columns", lambda query, limit: [])
    monkeypatch.setattr(pipeline, "search_values", lambda query, limit: [])
    monkeypatch.setattr(
        pipeline,
        "get_metric_context",
        lambda metric_ids: [
            {
                "metric_id": "paid_revenue",
                "name": "实付收入",
                "description": "已支付订单的实付金额",
                "formula": "SUM(`order`.paid_amount)",
                "base_table": "order",
                "allowed_dimensions": [],
                "relevant_columns": ["order.paid_amount"],
            }
        ],
    )
    monkeypatch.setattr(pipeline, "get_columns_by_full_names", lambda names: [])
    monkeypatch.setattr(pipeline, "get_dimensions_by_ids", lambda ids: [])
    monkeypatch.setattr(pipeline, "get_table_context", lambda names: [])
    monkeypatch.setattr(pipeline, "find_join_path", lambda source, target: [])
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="key", llm_model="model"),
    )

    def fake_llm(**kwargs):
        assert kwargs["purpose"] == "analytics.meta_qa"
        return core_llm.ChatCompletionTextResult(
            text='{"answer_markdown":"实付收入按已支付订单实付金额汇总。","citations":[{"kind":"metric","id":"paid_revenue","name":"实付收入","source":"meta_metric_info","description":"指标"}],"unsupported_reason":"","suggested_mode":"meta_qa","trace_summary":{}}',
            usage={"total_tokens": 12},
            model="model",
        )

    monkeypatch.setattr(pipeline.core_llm, "chat_completion_text", fake_llm)

    result = pipeline.run_meta_qa("实付收入怎么算？", session_id="s1")

    assert result["result_type"] == "meta_answer"
    assert result["blocks"][0]["type"] == "markdown"
    assert result["blocks"][1]["type"] == "meta_citations"
    assert result["citations"] == [
        {
            "kind": "metric",
            "id": "paid_revenue",
            "name": "实付收入",
            "source": "meta_metric_info",
            "description": "已支付订单的实付金额",
        }
    ]
    stage = result["trace"]["stages"][0]
    assert stage["name"] == "meta_qa_llm"
    assert stage["status"] == "ok"
    assert "promptHash" in stage
    assert "rawResponse" not in stage
    assert "prompt" not in stage


def test_run_meta_qa_without_llm_does_not_return_meta_answer(monkeypatch):
    monkeypatch.setattr(pipeline, "_build_context", lambda question: ({}, {}))
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", llm_model=""),
    )

    result = pipeline.run_meta_qa("实付收入怎么算？")

    assert result["result_type"] == "meta_error"
    assert result["error"]["code"] == "META_QA_UNAVAILABLE"
    assert result["trace"]["stages"][0]["name"] == "meta_qa_llm"


def test_run_meta_qa_routes_statistical_question_to_data_qa():
    result = pipeline.run_meta_qa("本月收入是多少？")

    assert result["result_type"] == "meta_answer"
    assert result["error"]["code"] == "META_QUERY_REQUIRES_DATA_QA"
    assert result["trace"]["stages"][0]["status"] == "skipped"
