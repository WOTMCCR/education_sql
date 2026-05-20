from __future__ import annotations

from typing import Any

from knowledge.analytics.agent.query_plan import ComparisonSpec, FilterRequest, QueryPlan, TimeWindow
from knowledge.analytics.agent.sql import quote_table, render_join, sql_field


def _from_with_joins(plan: QueryPlan) -> str:
    parts = [quote_table(plan.metric.base_table)]
    joined = {plan.metric.base_table}
    for edge in plan.join_plan.edges:
        rendered = render_join(edge, joined)
        if rendered:
            parts.append(rendered[0])
    return " ".join(parts)


def _escape(value: Any) -> str:
    return str(value).replace("'", "''")


def _filter_clause(filters: list[FilterRequest]) -> list[str]:
    clauses: list[str] = []
    for item in filters:
        field = sql_field(item.field)
        if item.op == "eq":
            clauses.append(f"{field} = '{_escape(item.value)}'")
        elif item.op == "in":
            values = item.value if isinstance(item.value, list) else [item.value]
            rendered = ", ".join([f"'{_escape(value)}'" for value in values])
            clauses.append(f"{field} IN ({rendered})")
    return clauses


def _where_clause(plan: QueryPlan, window: TimeWindow | None = None) -> str:
    filters = [*plan.metric.default_filters, *_filter_clause(plan.filters)]
    selected_window = window or plan.time_range
    if selected_window and plan.metric.time_column:
        field = sql_field(plan.metric.time_column)
        filters.append(f"{field} >= '{selected_window.start}'")
        filters.append(f"{field} < '{selected_window.endExclusive}'")
    return " AND ".join(filters) if filters else "1 = 1"


def _dimension_selects(plan: QueryPlan) -> list[str]:
    return [f"{sql_field(dimension.field)} AS {dimension.alias}" for dimension in plan.dimensions]


def _dimension_aliases(plan: QueryPlan) -> list[str]:
    return [dimension.alias for dimension in plan.dimensions]


def build_aggregate_sql(plan: QueryPlan) -> str:
    selects = [*_dimension_selects(plan), f"{plan.metric.expression} AS {plan.metric.value_alias}"]
    sql = [
        "SELECT",
        "  " + ",\n  ".join(selects),
        f"FROM {_from_with_joins(plan)}",
        f"WHERE {_where_clause(plan)}",
    ]
    if plan.dimensions:
        group_by = ", ".join([sql_field(dimension.field) for dimension in plan.dimensions])
        sql.append(f"GROUP BY {group_by}")
    sql.append(f"ORDER BY {plan.metric.value_alias} DESC")
    sql.append(f"LIMIT {plan.limit}")
    return "\n".join(sql)


def build_time_comparison_sql(plan: QueryPlan) -> str:
    comparison = plan.comparison
    if not comparison or comparison.kind != "time_period" or not comparison.current or not comparison.baseline:
        raise ValueError("time comparison requires current and baseline windows")
    return "\nUNION ALL\n".join(
        [
            _comparison_bucket_sql(plan, "current", comparison.current),
            _comparison_bucket_sql(plan, "baseline", comparison.baseline),
        ]
    )


def _comparison_bucket_sql(plan: QueryPlan, bucket: str, window: TimeWindow) -> str:
    dimension_selects = _dimension_selects(plan)
    selects = [f"'{bucket}' AS comparison_bucket", *dimension_selects, f"{plan.metric.expression} AS {plan.metric.value_alias}"]
    sql = [
        "SELECT",
        "  " + ",\n  ".join(selects),
        f"FROM {_from_with_joins(plan)}",
        f"WHERE {_where_clause(plan, window)}",
    ]
    if plan.dimensions:
        group_by = ", ".join([sql_field(dimension.field) for dimension in plan.dimensions])
        sql.append(f"GROUP BY {group_by}")
    return "\n".join(sql)


def visual_columns_for_plan(plan: QueryPlan, *, comparison: bool = False) -> list[dict[str, Any]]:
    columns = [{"key": dimension.alias, "label": dimension.name, "type": "string"} for dimension in plan.dimensions]
    if comparison:
        columns.extend(
            [
                {"key": "current_value", "label": "本期值", "type": _metric_column_type(plan), "unit": plan.metric.unit, "precision": 2},
                {"key": "baseline_value", "label": "基期值", "type": _metric_column_type(plan), "unit": plan.metric.unit, "precision": 2},
                {"key": "delta", "label": "差值", "type": _metric_column_type(plan), "unit": plan.metric.unit, "precision": 2},
                {"key": "delta_rate", "label": "变化率", "type": "number", "unit": "ratio", "precision": 4},
            ]
        )
    else:
        columns.append({"key": plan.metric.value_alias, "label": plan.metric.name, "type": _metric_column_type(plan), "unit": plan.metric.unit, "precision": 2})
    return columns


def _metric_column_type(plan: QueryPlan) -> str:
    return "currency" if plan.metric.unit == "yuan" else "number"


def comparison_metadata(comparison: ComparisonSpec | None) -> dict[str, Any] | None:
    if not comparison or comparison.kind == "none":
        return None
    return comparison.model_dump(exclude_none=True)
