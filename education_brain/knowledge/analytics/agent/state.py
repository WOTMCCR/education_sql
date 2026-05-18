from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def keep_first_error(
    current: dict[str, str] | None,
    new: dict[str, str] | None,
) -> dict[str, str] | None:
    return current or new


class DataAgentState(TypedDict, total=False):
    question: str
    session_id: str | None
    query_id: str

    keywords: list[str]
    expanded_keywords: list[str]
    retrieved_columns: list[dict[str, Any]]
    retrieved_metrics: list[dict[str, Any]]
    retrieved_values: list[dict[str, Any]]

    metric_infos: list[dict[str, Any]]
    candidate_metric_infos: list[dict[str, Any]]
    dimension_infos: list[dict[str, Any]]
    candidate_dimension_infos: list[dict[str, Any]]
    table_infos: list[dict[str, Any]]
    candidate_table_infos: list[dict[str, Any]]
    join_paths: list[dict[str, Any]]

    intent: dict[str, Any]
    structured_intent: dict[str, Any]
    llm_filter_decision: Annotated[dict[str, Any], operator.or_]
    sql_plan: dict[str, Any]
    candidate_context: dict[str, Any]
    llm_raw_outputs: Annotated[dict[str, str], operator.or_]
    llm_usage: Annotated[dict[str, dict[str, Any]], operator.or_]
    sql: str
    sql_valid: bool
    validation_error: dict[str, str] | None
    rows: list[dict[str, Any]]
    row_count: int

    visual: dict[str, Any]
    explain: dict[str, Any]
    answer: str
    error: Annotated[dict[str, str] | None, keep_first_error]
    warnings: Annotated[list[str], operator.add]
    trace_stages: Annotated[list[dict[str, Any]], operator.add]
    started_at: float
