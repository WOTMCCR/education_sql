import json
from typing import Any

from knowledge.analytics.agent.pipeline import run_data_qa
from knowledge.analytics.agent.sql import ensure_default_limit, is_safe_select_sql, quote_table
from knowledge.analytics import meta_store
from knowledge.tests.data_qa_test_fixtures import install_data_qa_meta_fixtures


RANKING_SQL = (
    "SELECT org_campus.campus_name AS campus, SUM(`order`.paid_amount) AS paid_revenue "
    "FROM `order` "
    "JOIN order_item ON `order`.id = order_item.order_id "
    "JOIN series_cohort ON order_item.cohort_id = series_cohort.id "
    "JOIN org_campus ON series_cohort.campus_id = org_campus.id "
    "WHERE `order`.order_status IN ('paid', 'completed') "
    "GROUP BY org_campus.campus_name ORDER BY paid_revenue DESC LIMIT 10"
)


def _install_llm_ranking_path(monkeypatch, joins: list[str] | None = None):
    from knowledge.analytics.agent.graph import build_data_qa_graph
    from knowledge.core import llm

    install_data_qa_meta_fixtures(monkeypatch)
    intent = {
        "analysisType": "ranking",
        "metrics": ["paid_revenue"],
        "dimensions": ["campus"],
        "filters": [],
        "sort": [{"field": "paid_revenue", "direction": "desc"}],
        "limit": 10,
        "visualHint": "bar",
    }

    def fake_chat_completion_text(**kwargs: Any) -> str:
        purpose = str(kwargs.get("purpose") or "")
        if purpose.endswith("expand_search_keywords"):
            return json.dumps({"keywords": ["收入", "paid_revenue", "校区", "campus", "排名"]}, ensure_ascii=False)
        if purpose.endswith("structure_intent"):
            return json.dumps(intent, ensure_ascii=False)
        if purpose.endswith("filter_metric"):
            return json.dumps({"selectedIds": ["paid_revenue"], "rejectedIds": [], "reason": "收入排名"}, ensure_ascii=False)
        if purpose.endswith("filter_table"):
            return json.dumps(
                {"selectedIds": ["order", "order_item", "series_cohort", "org_campus"], "rejectedIds": [], "reason": "校区收入需要 join"},
                ensure_ascii=False,
            )
        if purpose.endswith("generate_sql"):
            return json.dumps(
                {
                    "sql": RANKING_SQL,
                    "visual": {"type": "bar", "x": "campus", "y": ["paid_revenue"]},
                    "usedTables": ["order", "order_item", "series_cohort", "org_campus"],
                    "usedColumns": [
                        "order.paid_amount",
                        "order.order_status",
                        "order.id",
                        "order_item.order_id",
                        "order_item.cohort_id",
                        "series_cohort.id",
                        "series_cohort.campus_id",
                        "org_campus.id",
                        "org_campus.campus_name",
                    ],
                    "usedMetrics": ["paid_revenue"],
                    "joins": joins or ["order_order_item", "order_item_cohort", "cohort_campus"],
                    "assumptions": [],
                },
                ensure_ascii=False,
            )
        if purpose.endswith("correct_sql"):
            return json.dumps(
                {
                    "sql": RANKING_SQL,
                    "changed": False,
                    "reason": "SQL already valid",
                    "usedTables": ["order", "order_item", "series_cohort", "org_campus"],
                    "usedColumns": ["order.paid_amount", "org_campus.campus_name"],
                    "joins": ["order_order_item", "order_item_cohort", "cohort_campus"],
                },
                ensure_ascii=False,
            )
        return json.dumps({}, ensure_ascii=False)

    monkeypatch.setattr(llm, "chat_completion_text", fake_chat_completion_text)
    build_data_qa_graph.cache_clear()


def test_find_join_path_order_to_campus_uses_explicit_meta_edges(monkeypatch):
    install_data_qa_meta_fixtures(monkeypatch)

    path = meta_store.find_join_path("order", "org_campus")

    assert [edge["join_id"] for edge in path] == [
        "order_order_item",
        "order_item_cohort",
        "cohort_campus",
    ]


def test_data_qa_pipeline_returns_ranking_with_join_explain(monkeypatch):
    _install_llm_ranking_path(monkeypatch)

    result = run_data_qa("哪个校区收入最高？", session_id="pytest")

    assert result["mode"] == "data_qa"
    assert result["intent"]["analysisType"] == "ranking"
    assert result["intent"]["metrics"] == ["paid_revenue"]
    assert result["intent"]["dimensions"] == ["campus"]
    assert result["visual"]["type"] == "bar"
    assert result["visual"]["rows"]
    assert result["explain"]["joins"] == [
        "order_order_item",
        "order_item_cohort",
        "cohort_campus",
    ]


def test_data_qa_pipeline_accepts_llm_join_expressions_when_in_context(monkeypatch):
    _install_llm_ranking_path(
        monkeypatch,
        joins=[
            "`order`.id = order_item.order_id",
            "order_item.cohort_id = series_cohort.id",
            "series_cohort.campus_id = org_campus.id",
        ],
    )

    result = run_data_qa("哪个校区收入最高？", session_id="pytest-join-expr")

    assert not result.get("error")
    assert result["visual"]["type"] == "bar"
    assert result["explain"]["joins"] == [
        "order_order_item",
        "order_item_cohort",
        "cohort_campus",
    ]


def test_correct_sql_skips_llm_when_sql_already_valid(monkeypatch):
    from knowledge.analytics.agent.nodes.core import correct_sql
    from knowledge.core import llm

    def fail_if_called(**_: Any) -> str:
        raise AssertionError("correct_sql must not call LLM when sql_valid is already true")

    monkeypatch.setattr(llm, "chat_completion_text", fail_if_called)

    update = correct_sql(
        {
            "question": "哪个校区收入最高？",
            "sql": RANKING_SQL,
            "sql_valid": True,
            "candidate_context": {"sqlContext": {}},
        }
    )

    assert update["trace_stages"][0]["name"] == "correct_sql"
    assert update["trace_stages"][0]["status"] == "skipped"


def test_data_qa_pipeline_rejects_multistatement_input(monkeypatch):
    _install_llm_ranking_path(monkeypatch)

    result = run_data_qa("本月总收入是多少？; DROP TABLE `order`;", session_id="pytest")

    assert result["error"]["code"] == "SQL_UNSAFE"
    assert result["trace"]["rowCount"] == 0
    assert any(
        stage["name"] == "execute_sql" and stage["status"] == "skipped"
        for stage in result["trace"]["stages"]
    )
    assert not any(
        stage["name"] == "execute_sql" and stage["status"] == "ok"
        for stage in result["trace"]["stages"]
    )


def test_sql_helpers_quote_reserved_order_table():
    assert quote_table("order") == "`order`"
    assert is_safe_select_sql("SELECT SUM(`order`.paid_amount) FROM `order`")
    assert not is_safe_select_sql("SELECT 1; DROP TABLE `order`;")
    assert not is_safe_select_sql("SELECT 1 /* hidden */")
    assert not is_safe_select_sql("SELECT 1 INTO OUTFILE '/tmp/x'")
    assert not is_safe_select_sql("SELECT GET_LOCK('x', 1)")
    assert ensure_default_limit("SELECT id FROM student") == "SELECT id FROM student LIMIT 1000"
    assert ensure_default_limit("SELECT SUM(`order`.paid_amount) FROM `order`") == "SELECT SUM(`order`.paid_amount) FROM `order`"
