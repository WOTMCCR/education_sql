from __future__ import annotations

from typing import Any


JOIN_PATH = [
    {
        "join_id": "order_order_item",
        "left_table": "order",
        "left_column": "id",
        "right_table": "order_item",
        "right_column": "order_id",
    },
    {
        "join_id": "order_item_cohort",
        "left_table": "order_item",
        "left_column": "cohort_id",
        "right_table": "series_cohort",
        "right_column": "id",
    },
    {
        "join_id": "cohort_campus",
        "left_table": "series_cohort",
        "left_column": "campus_id",
        "right_table": "org_campus",
        "right_column": "id",
    },
]


METRIC = {
    "metric_id": "paid_revenue",
    "name": "实付收入",
    "description": "已支付订单的实付金额合计。",
    "formula": "SUM(`order`.paid_amount)",
    "base_table": "order",
    "time_column": "order.paid_at",
    "unit": "yuan",
    "default_filters": ["`order`.order_status IN ('paid', 'completed')"],
    "allowed_dimensions": ["campus", "paid_date"],
    "relevant_columns": ["order.paid_amount", "order.order_status", "order.paid_at"],
    "aliases": ["收入", "实付收入"],
}


DIMENSIONS = [
    {
        "dimension_id": "campus",
        "name": "校区",
        "table_name": "org_campus",
        "column_name": "campus_name",
        "aliases": ["校区"],
    },
    {
        "dimension_id": "paid_date",
        "name": "支付日期",
        "table_name": "*",
        "column_name": "paid_at",
        "time_grain": "day",
        "aliases": ["日期"],
    },
]


COLUMNS = [
    "order.id",
    "order.paid_amount",
    "order.order_status",
    "order.paid_at",
    "order_item.order_id",
    "order_item.cohort_id",
    "series_cohort.id",
    "series_cohort.campus_id",
    "org_campus.id",
    "org_campus.name",
    "org_campus.campus_name",
]


def install_data_qa_meta_fixtures(monkeypatch: Any) -> None:
    from knowledge.analytics import meta_store
    from knowledge.analytics.agent.nodes import core as core_nodes

    def fake_find_join_path(left: str, right: str) -> list[dict[str, str]]:
        if left == "order" and right == "org_campus":
            return list(JOIN_PATH)
        return []

    monkeypatch.setattr(meta_store, "get_join_edges", lambda: list(JOIN_PATH))
    monkeypatch.setattr(core_nodes, "find_join_path", fake_find_join_path)
    monkeypatch.setattr(core_nodes, "search_metrics", lambda keyword, limit=8: [{"metric_id": "paid_revenue", "score": 1.0}])
    monkeypatch.setattr(core_nodes, "search_columns", lambda keyword, limit=10: [{"full_name": name, "score": 1.0} for name in COLUMNS])
    monkeypatch.setattr(
        core_nodes,
        "search_values",
        lambda keyword, limit=5: [
            {
                "value_id": "campus_chaoyang",
                "dimension_id": "campus",
                "field": "org_campus.campus_name",
                "value": "朝阳校区",
                "score": 1.0,
            }
        ],
    )
    monkeypatch.setattr(core_nodes, "get_metric_context", lambda metric_ids: [METRIC] if "paid_revenue" in metric_ids else [])
    monkeypatch.setattr(
        core_nodes,
        "get_dimensions_by_ids",
        lambda dimension_ids: [dimension for dimension in DIMENSIONS if dimension["dimension_id"] in set(dimension_ids)],
    )
    monkeypatch.setattr(core_nodes, "get_table_context", lambda table_names: [{"table_name": name, "business_name": name, "description": name} for name in table_names])
    monkeypatch.setattr(core_nodes, "get_columns_by_full_names", lambda names: [{"full_name": name, "table_name": name.split(".", 1)[0], "column_name": name.split(".", 1)[1]} for name in names])
    monkeypatch.setattr(core_nodes, "explain_sql", lambda sql: None)
    monkeypatch.setattr(
        core_nodes,
        "execute_select",
        lambda sql: [
            {"campus": "朝阳校区", "paid_revenue": 56300.0},
            {"campus": "徐汇校区", "paid_revenue": 42100.0},
        ],
    )
