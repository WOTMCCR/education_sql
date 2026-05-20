from __future__ import annotations

import time
import uuid
import re
from datetime import date, timedelta
from typing import Any, Callable

import jieba.analyse

from knowledge.analytics.meta_store import (
    find_join_path,
    get_columns_by_full_names,
    get_dimensions_by_ids,
    get_metric_context,
    get_table_context,
    referenced_full_names,
)
from knowledge.analytics.agent.llm_schema import (
    FilterDecision,
    KeywordExpansion,
    SqlCorrection,
    SqlPlan,
    StructuredIntent,
)
from knowledge.analytics.agent.llm_utils import call_structured_llm
from knowledge.analytics.search import search_columns, search_metrics, search_values
from knowledge.analytics.agent.sql import (
    execute_select,
    explain_sql,
    ensure_default_limit,
    is_safe_select_sql,
    question_contains_dangerous_sql,
    quote_table,
    render_join,
    sql_field,
)
from knowledge.analytics.agent.state import DataAgentState


ALLOW_POS = ("n", "nr", "ns", "nt", "nz", "v", "vn", "a", "an", "eng", "i", "l")
INCOME_WORDS = {"收入", "实收", "实付收入", "销售额", "交易额", "GMV", "付费金额", "金额"}


def _stage(name: str, fn: Callable[[DataAgentState], dict[str, Any]]) -> Callable[[DataAgentState], dict[str, Any]]:
    def wrapper(state: DataAgentState) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            update = fn(state)
            emitted_stages = list(update.pop("trace_stages", []))
            if emitted_stages and emitted_stages[-1].get("name") == name:
                return {**update, "trace_stages": emitted_stages}
            status = "error" if update.get("error") else "ok"
            message = None if status == "ok" else update.get("error", {}).get("message")
            return {
                **update,
                "trace_stages": emitted_stages
                + [
                    {
                        "name": name,
                        "status": status,
                        "durationMs": round((time.perf_counter() - start) * 1000),
                        **({"message": message} if message else {}),
                    }
                ],
            }
        except Exception as e:
            return {
                "error": {"stage": name, "code": "NODE_FAILED", "message": str(e)},
                "trace_stages": [
                    {
                        "name": name,
                        "status": "error",
                        "durationMs": round((time.perf_counter() - start) * 1000),
                        "message": str(e),
                    }
                ],
            }

    return wrapper


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys([item.strip() for item in items if item and item.strip()]))


def _with_income_aliases(question: str, keywords: list[str]) -> list[str]:
    if any(word in question for word in INCOME_WORDS):
        keywords.extend(["收入", "实收", "实付金额", "付费金额", "GMV", "paid_revenue"])
    if "报名" in question:
        keywords.extend(["报名", "报名次数", "enrollment_count"])
    if "校区" in question:
        keywords.extend(["校区", "校区名称", "campus"])
    if "趋势" in question or "最近30天" in question or "最近 30 天" in question:
        keywords.extend(["趋势", "日期", "支付日期", "paid_date"])
    return _unique(keywords)


def extract_keywords(state: DataAgentState) -> dict[str, Any]:
    question = state["question"]
    words = jieba.analyse.extract_tags(question, topK=8, allowPOS=ALLOW_POS)
    return {"keywords": _unique([question, *words])}


def _llm_trace_update(stage: str, result: Any) -> dict[str, Any]:
    llm = result.stage.get("llm", {})
    return {
        "trace_stages": [result.stage],
        "llm_usage": {stage: llm.get("usage") or {"usageUnavailable": True}},
    }


def expand_search_keywords(state: DataAgentState) -> dict[str, Any]:
    seed_keywords = _with_income_aliases(state["question"], list(state.get("keywords") or []))
    result = call_structured_llm(
        stage="expand_search_keywords",
        prompt_name="expand_keywords",
        response_model=KeywordExpansion,
        user_payload={
            "question": state["question"],
            "seedKeywords": seed_keywords,
        },
        max_tokens=700,
    )
    update = _llm_trace_update("expand_search_keywords", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, KeywordExpansion)
    expanded = _unique([*seed_keywords, *parsed.keywords])
    return {**update, "expanded_keywords": expanded, "keywords": expanded}


def _search_many(
    keywords: list[str],
    search_fn: Callable[[str, int], list[dict[str, Any]]],
    id_key: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for keyword in keywords:
        for item in search_fn(keyword, limit):
            entity_id = str(item.get(id_key) or item.get("id") or item.get("full_name") or item.get("value_id"))
            if not entity_id:
                continue
            previous = found.get(entity_id)
            item = {**item, "hitKeyword": keyword}
            if previous is None or float(item.get("score") or 0) > float(previous.get("score") or 0):
                found[entity_id] = item
    return sorted(found.values(), key=lambda item: float(item.get("score") or 0), reverse=True)


def recall_metric(state: DataAgentState) -> dict[str, Any]:
    return {"retrieved_metrics": _search_many(state["keywords"], search_metrics, "metric_id")}


def recall_column(state: DataAgentState) -> dict[str, Any]:
    return {"retrieved_columns": _search_many(state["keywords"], search_columns, "full_name", limit=10)}


def recall_value(state: DataAgentState) -> dict[str, Any]:
    keywords = [kw for kw in state["keywords"] if kw not in {"校区", "课程", "趋势", "日期", "收入"}]
    values = _search_many(keywords[:8], search_values, "value_id", limit=5)
    return {"retrieved_values": values}


def _analysis_type(question: str) -> str:
    if "趋势" in question or "最近30天" in question or "最近 30 天" in question:
        return "trend"
    if "最高" in question or "排名" in question or question.startswith("哪个"):
        return "ranking"
    return "single_metric"


def _dimension_ids(question: str, analysis_type: str) -> list[str]:
    if analysis_type == "trend":
        return ["paid_date"]
    if "校区" in question:
        return ["campus"]
    return []


def _dimension_ids_from_values(
    question: str,
    values: list[dict[str, Any]],
    allowed_dimensions: set[str],
) -> list[str]:
    result: list[str] = []
    for value in values:
        dimension_id = value.get("dimension_id")
        raw_value = str(value.get("value") or "")
        if dimension_id in allowed_dimensions and raw_value and raw_value in question:
            result.append(str(dimension_id))
    return _unique(result)


def _filters_from_values(
    question: str,
    values: list[dict[str, Any]],
    allowed_dimensions: set[str],
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for value in values:
        dimension_id = value.get("dimension_id")
        raw_value = str(value.get("value") or "")
        field = value.get("field")
        if not dimension_id or dimension_id not in allowed_dimensions or not raw_value or not field:
            continue
        if raw_value not in question:
            continue
        filters.append({"field": field, "op": "eq", "value": raw_value, "label": raw_value})
    return filters[:3]


def _metric_for_prompt(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": metric.get("metric_id"),
        "name": metric.get("name"),
        "description": metric.get("description"),
        "formula": metric.get("formula"),
        "baseTable": metric.get("base_table"),
        "timeColumn": metric.get("time_column"),
        "unit": metric.get("unit"),
        "defaultFilters": metric.get("default_filters") or [],
        "allowedDimensions": metric.get("allowed_dimensions") or [],
        "relevantColumns": metric.get("relevant_columns") or [],
        "aliases": metric.get("aliases") or [],
    }


def _dimension_for_prompt(dimension: dict[str, Any]) -> dict[str, Any]:
    table_name = dimension.get("table_name")
    column_name = dimension.get("column_name")
    field = f"{table_name}.{column_name}" if table_name and table_name != "*" and column_name else column_name
    return {
        "id": dimension.get("dimension_id"),
        "name": dimension.get("name"),
        "field": field,
        "tableName": table_name,
        "columnName": column_name,
        "timeGrain": dimension.get("time_grain"),
        "aliases": dimension.get("aliases") or [],
    }


def merge_retrieved_info(state: DataAgentState) -> dict[str, Any]:
    metric_ids = [item.get("metric_id") or item.get("id") for item in state.get("retrieved_metrics", [])]
    metric_ids = _unique([str(metric_id) for metric_id in metric_ids if metric_id])[:3]
    if not metric_ids:
        return {"error": {"stage": "merge_retrieved_info", "code": "RECALL_EMPTY", "message": "没有召回到可用指标。"}}

    metric_infos = get_metric_context(metric_ids[:8])
    if not metric_infos:
        return {"error": {"stage": "merge_retrieved_info", "code": "RECALL_EMPTY", "message": "召回指标缺少 meta 口径。"}}

    allowed_dimension_ids: list[str] = []
    for metric in metric_infos:
        allowed_dimension_ids.extend(metric.get("allowed_dimensions") or [])
    allowed_dimensions = set(allowed_dimension_ids)
    value_dimensions = [
        str(value.get("dimension_id"))
        for value in state.get("retrieved_values", [])
        if value.get("dimension_id") in allowed_dimensions
    ]
    dimension_ids = _unique([*allowed_dimension_ids, *value_dimensions])
    dimension_infos = get_dimensions_by_ids(dimension_ids)

    table_names = _unique(
        [
            *[metric["base_table"] for metric in metric_infos],
            *[
                str(dimension["table_name"])
                for dimension in dimension_infos
                if dimension.get("table_name") and dimension.get("table_name") != "*"
            ],
            *[
                str(column.get("table_name"))
                for column in state.get("retrieved_columns", [])[:8]
                if column.get("table_name")
            ],
        ]
    )
    return {
        "candidate_metric_infos": metric_infos,
        "metric_infos": metric_infos,
        "candidate_dimension_infos": dimension_infos,
        "dimension_infos": dimension_infos,
        "candidate_table_infos": get_table_context(table_names),
        "table_infos": get_table_context(table_names),
        "candidate_context": {
            "metrics": [_metric_for_prompt(metric) for metric in metric_infos],
            "dimensions": [_dimension_for_prompt(dimension) for dimension in dimension_infos],
            "values": state.get("retrieved_values", [])[:12],
            "columns": state.get("retrieved_columns", [])[:16],
        },
    }


def filter_table(state: DataAgentState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    candidates = state.get("candidate_table_infos") or state.get("table_infos", [])
    result = call_structured_llm(
        stage="filter_table",
        prompt_name="filter_candidates",
        response_model=FilterDecision,
        user_payload={
            "kind": "table",
            "question": state["question"],
            "intent": state.get("intent") or {},
            "candidates": [
                {
                    "id": table.get("table_name"),
                    "businessName": table.get("business_name"),
                    "description": table.get("description"),
                    "aliases": table.get("aliases") or [],
                }
                for table in candidates
            ],
        },
        max_tokens=700,
    )
    update = _llm_trace_update("filter_table", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, FilterDecision)
    selected = set(parsed.selectedIds)
    filtered = [table for table in candidates if table.get("table_name") in selected]
    return {
        **update,
        "table_infos": filtered or candidates[:8],
        "llm_filter_decision": {"filter_table": parsed.model_dump()},
    }


def filter_metric(state: DataAgentState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    candidates = state.get("candidate_metric_infos") or state.get("metric_infos", [])
    result = call_structured_llm(
        stage="filter_metric",
        prompt_name="filter_candidates",
        response_model=FilterDecision,
        user_payload={
            "kind": "metric",
            "question": state["question"],
            "intent": state.get("intent") or {},
            "candidates": [_metric_for_prompt(metric) for metric in candidates],
        },
        max_tokens=700,
    )
    update = _llm_trace_update("filter_metric", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, FilterDecision)
    selected = set(parsed.selectedIds or (state.get("intent") or {}).get("metrics") or [])
    filtered = [metric for metric in candidates if metric.get("metric_id") in selected]
    if not filtered:
        return {
            **update,
            "error": {
                "stage": "filter_metric",
                "code": "METRIC_NOT_DEFINED",
                "message": "候选指标无法覆盖当前问题所需业务口径。",
            },
        }
    return {
        **update,
        "metric_infos": filtered,
        "llm_filter_decision": {"filter_metric": parsed.model_dump()},
    }


def _time_range(question: str) -> dict[str, Any]:
    today = date.today()
    end_exclusive = today + timedelta(days=1)
    if "最近30天" in question or "最近 30 天" in question:
        start = today - timedelta(days=29)
        return {
            "start": start.isoformat(),
            "end": today.isoformat(),
            "endExclusive": end_exclusive.isoformat(),
            "grain": "day",
            "label": "最近30天",
        }
    start = today.replace(day=1)
    return {
        "start": start.isoformat(),
        "end": today.isoformat(),
        "endExclusive": end_exclusive.isoformat(),
        "grain": "day",
        "label": "本月",
    }


def structure_intent(state: DataAgentState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    result = call_structured_llm(
        stage="structure_intent",
        prompt_name="structure_intent",
        response_model=StructuredIntent,
        user_payload={
            "question": state["question"],
            "currentDate": date.today().isoformat(),
            "keywords": state.get("expanded_keywords") or state.get("keywords") or [],
            "candidateContext": state.get("candidate_context") or {},
        },
        max_tokens=1400,
    )
    update = _llm_trace_update("structure_intent", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, StructuredIntent)
    intent = parsed.model_dump(exclude_none=True)
    candidate_metrics = {metric.get("metric_id") for metric in state.get("candidate_metric_infos", [])}
    invalid_metrics = [metric for metric in intent.get("metrics", []) if metric not in candidate_metrics]
    if invalid_metrics:
        return {
            **update,
            "error": {
                "stage": "structure_intent",
                "code": "LLM_OUTPUT_INVALID",
                "message": f"LLM 选择了候选 context 之外的指标: {invalid_metrics}",
            },
        }
    if not intent.get("metrics"):
        return {
            **update,
            "intent": intent,
            "structured_intent": intent,
            "error": {
                "stage": "structure_intent",
                "code": "METRIC_NOT_DEFINED",
                "message": "当前 meta 未定义该问题需要的业务指标口径。",
            },
        }
    return {**update, "intent": intent, "structured_intent": intent}


def _dimension_field(dimension: dict[str, Any], metric: dict[str, Any]) -> str:
    table_name = dimension.get("table_name")
    column_name = dimension.get("column_name")
    if table_name == "*":
        return f"{metric['base_table']}.{column_name}"
    return f"{table_name}.{column_name}"


def _field_table(full_name: str) -> str:
    return full_name.split(".", 1)[0].strip("`")


def _normalize_table_name(table_name: str) -> str:
    return table_name.strip().strip("`")


def _normalize_full_name(full_name: str) -> str:
    parts = full_name.strip().split(".", 1)
    if len(parts) != 2:
        return full_name.strip().strip("`")
    return f"{parts[0].strip('`')}.{parts[1].strip('`')}"


def _metric_columns(metric: dict[str, Any]) -> list[str]:
    columns = [
        *(metric.get("relevant_columns") or []),
        *(referenced_full_names(metric.get("formula"))),
        *(name for expr in metric.get("default_filters") or [] for name in referenced_full_names(expr)),
    ]
    if metric.get("time_column"):
        columns.append(metric["time_column"])
    return _unique(columns)


def _selected_dimensions(state: DataAgentState, metric: dict[str, Any]) -> list[dict[str, Any]]:
    intent = state.get("intent") or {}
    requested = set(intent.get("dimensions") or [])
    filter_fields = {str(item.get("field") or "") for item in intent.get("filters") or []}
    selected: list[dict[str, Any]] = []
    for dimension in state.get("candidate_dimension_infos") or state.get("dimension_infos", []):
        field = _dimension_field(dimension, metric)
        if dimension.get("dimension_id") in requested or field in filter_fields:
            selected.append(dimension)
    return selected


def _build_join_paths(metric: dict[str, Any], dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    join_paths: list[dict[str, Any]] = []
    seen: set[str] = set()
    for dimension in dimensions:
        target_table = dimension["table_name"]
        if target_table in {"*", metric["base_table"]}:
            continue
        path = find_join_path(metric["base_table"], target_table)
        if not path:
            raise ValueError(f"无法从 {metric['base_table']} 关联到 {target_table}")
        for edge in path:
            if edge["join_id"] not in seen:
                join_paths.append(edge)
                seen.add(edge["join_id"])
    return join_paths


def _build_sql_context(state: DataAgentState) -> dict[str, Any]:
    metric = (state.get("metric_infos") or [])[0]
    dimensions = _selected_dimensions(state, metric)
    allowed = set(metric.get("allowed_dimensions") or [])
    blocked = [dimension["dimension_id"] for dimension in dimensions if dimension.get("dimension_id") not in allowed]
    if blocked:
        raise PermissionError(f"指标 {metric['metric_id']} 不支持维度: {blocked}")
    join_paths = _build_join_paths(metric, dimensions)
    dimension_columns = [_dimension_field(dimension, metric) for dimension in dimensions]
    join_columns = [
        f"{edge['left_table']}.{edge['left_column']}"
        for edge in join_paths
    ] + [
        f"{edge['right_table']}.{edge['right_column']}"
        for edge in join_paths
    ]
    filter_columns = [
        str(item.get("field"))
        for item in (state.get("intent") or {}).get("filters") or []
        if item.get("field")
    ]
    column_names = _unique([*_metric_columns(metric), *dimension_columns, *join_columns, *filter_columns])
    table_names = _unique([
        metric["base_table"],
        *[_field_table(column) for column in column_names],
        *[edge["left_table"] for edge in join_paths],
        *[edge["right_table"] for edge in join_paths],
    ])
    columns = get_columns_by_full_names(column_names)
    tables = get_table_context(table_names)
    return {
        "dialect": "MySQL 8.0",
        "safety": ["SELECT only", "single statement", "no comments", "no DDL or DML", "read-only execution"],
        "metric": _metric_for_prompt(metric),
        "dimensions": [_dimension_for_prompt(dimension) for dimension in dimensions],
        "filters": (state.get("intent") or {}).get("filters") or [],
        "timeRange": (state.get("intent") or {}).get("timeRange"),
        "sort": (state.get("intent") or {}).get("sort") or [],
        "limit": (state.get("intent") or {}).get("limit"),
        "tables": tables,
        "columns": columns,
        "joinPaths": join_paths,
    }


def add_extra_context(state: DataAgentState) -> dict[str, Any]:
    if state.get("error"):
        return {"query_id": state.get("query_id") or f"dq_{uuid.uuid4().hex[:12]}"}
    if not state.get("metric_infos"):
        return {
            "query_id": state.get("query_id") or f"dq_{uuid.uuid4().hex[:12]}",
            "error": {
                "stage": "add_extra_context",
                "code": "METRIC_NOT_DEFINED",
                "message": "没有可用于 SQL 生成的指标。",
            },
        }
    try:
        sql_context = _build_sql_context(state)
    except PermissionError as e:
        return {
            "query_id": state.get("query_id") or f"dq_{uuid.uuid4().hex[:12]}",
            "error": {"stage": "add_extra_context", "code": "DIMENSION_NOT_ALLOWED", "message": str(e)},
        }
    except ValueError as e:
        return {
            "query_id": state.get("query_id") or f"dq_{uuid.uuid4().hex[:12]}",
            "error": {"stage": "add_extra_context", "code": "JOIN_PATH_NOT_FOUND", "message": str(e)},
        }
    return {
        "query_id": state.get("query_id") or f"dq_{uuid.uuid4().hex[:12]}",
        "candidate_context": {**(state.get("candidate_context") or {}), "sqlContext": sql_context},
        "dimension_infos": _selected_dimensions(state, state["metric_infos"][0]),
        "join_paths": sql_context["joinPaths"],
        "table_infos": sql_context["tables"],
    }


def _where_clause(metric: dict[str, Any], time_range: dict[str, Any] | None) -> str:
    filters = list(metric.get("default_filters") or [])
    if time_range and metric.get("time_column"):
        time_field = sql_field(metric["time_column"])
        filters.append(f"{time_field} >= '{time_range['start']}'")
        filters.append(f"{time_field} < '{time_range['endExclusive']}'")
    return " AND ".join(filters) if filters else "1 = 1"


def _value_filter_clause(filters: list[dict[str, Any]]) -> str:
    clauses: list[str] = []
    for item in filters:
        if item.get("op") != "eq" or not item.get("field"):
            continue
        escaped = str(item.get("value", "")).replace("'", "''")
        clauses.append(f"{sql_field(item['field'])} = '{escaped}'")
    return " AND ".join(clauses)


def _from_with_joins(base_table: str, join_paths: list[dict[str, Any]]) -> str:
    parts = [quote_table(base_table)]
    joined = {base_table}
    for edge in join_paths:
        rendered = render_join(edge, joined)
        if rendered:
            parts.append(rendered[0])
    return " ".join(parts)


def _context_allowed_sets(sql_context: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str]]:
    tables = {table.get("table_name") for table in sql_context.get("tables") or [] if table.get("table_name")}
    columns = {column.get("full_name") for column in sql_context.get("columns") or [] if column.get("full_name")}
    metric = sql_context.get("metric") or {}
    metrics = {metric.get("id")} if metric.get("id") else set()
    joins = {edge.get("join_id") for edge in sql_context.get("joinPaths") or [] if edge.get("join_id")}
    return set(tables), set(columns), set(metrics), set(joins)


def _normalize_join_expression(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("`", "")).lower()


def _join_reference_map(sql_context: dict[str, Any]) -> dict[str, str]:
    references: dict[str, str] = {}
    for edge in sql_context.get("joinPaths") or []:
        join_id = edge.get("join_id")
        if not join_id:
            continue
        left = f"{edge.get('left_table')}.{edge.get('left_column')}"
        right = f"{edge.get('right_table')}.{edge.get('right_column')}"
        references[str(join_id)] = str(join_id)
        references[_normalize_join_expression(f"{left}={right}")] = str(join_id)
        references[_normalize_join_expression(f"{right}={left}")] = str(join_id)
    return references


def _normalize_join_references(joins: list[str], sql_context: dict[str, Any]) -> set[str]:
    reference_map = _join_reference_map(sql_context)
    normalized: set[str] = set()
    for join in joins:
        normalized.add(reference_map.get(join, reference_map.get(_normalize_join_expression(join), join)))
    return normalized


def _validate_sql_plan_context(plan: SqlPlan, sql_context: dict[str, Any]) -> str | None:
    allowed_tables, allowed_columns, allowed_metrics, allowed_joins = _context_allowed_sets(sql_context)
    used_tables = {_normalize_table_name(table) for table in plan.usedTables}
    used_columns = {_normalize_full_name(column) for column in plan.usedColumns}
    used_metrics = set(plan.usedMetrics)
    used_joins = _normalize_join_references(plan.joins, sql_context)
    sql_columns = referenced_full_names(plan.sql)
    sql_tables = {_field_table(column) for column in sql_columns}
    problems: list[str] = []
    if used_tables - allowed_tables:
        problems.append(f"tables={sorted(used_tables - allowed_tables)}")
    if used_columns - allowed_columns:
        problems.append(f"columns={sorted(used_columns - allowed_columns)}")
    if used_metrics - allowed_metrics:
        problems.append(f"metrics={sorted(used_metrics - allowed_metrics)}")
    if used_joins - allowed_joins:
        problems.append(f"joins={sorted(used_joins - allowed_joins)}")
    if sql_tables - allowed_tables:
        problems.append(f"sqlTables={sorted(sql_tables - allowed_tables)}")
    if sql_columns - allowed_columns:
        problems.append(f"sqlColumns={sorted(sql_columns - allowed_columns)}")
    return "; ".join(problems) if problems else None


def _normalize_llm_select_sql(sql: str) -> str:
    stripped = sql.strip()
    if stripped.endswith(";") and ";" not in stripped[:-1]:
        return stripped[:-1].rstrip()
    return stripped


def generate_sql(state: DataAgentState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    sql_context = (state.get("candidate_context") or {}).get("sqlContext") or {}
    result = call_structured_llm(
        stage="generate_sql",
        prompt_name="generate_sql",
        response_model=SqlPlan,
        user_payload={
            "question": state["question"],
            "currentDate": date.today().isoformat(),
            "intent": state.get("intent") or {},
            "sqlContext": sql_context,
        },
        max_tokens=1800,
        timeout=60.0,
    )
    update = _llm_trace_update("generate_sql", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, SqlPlan)
    parsed.sql = _normalize_llm_select_sql(parsed.sql)
    plan_error = _validate_sql_plan_context(parsed, sql_context)
    if plan_error:
        return {
            **update,
            "error": {
                "stage": "generate_sql",
                "code": "LLM_OUTPUT_INVALID",
                "message": f"LLM 生成 SQL 引用了候选 context 之外的对象: {plan_error}",
            },
        }
    if question_contains_dangerous_sql(state["question"]):
        return {
            **update,
            "sql": "",
            "sql_plan": parsed.model_dump(),
            "error": {
                "stage": "generate_sql",
                "code": "SQL_UNSAFE",
                "message": "问题中包含多语句或危险 SQL 关键词，已拒绝执行。",
            },
        }
    return {**update, "sql": ensure_default_limit(parsed.sql), "sql_plan": parsed.model_dump()}


def validate_sql(state: DataAgentState) -> dict[str, Any]:
    sql = state.get("sql") or ""
    if state.get("error"):
        return {
            "sql_valid": False,
            "trace_stages": [
                {
                    "name": "validate_sql",
                    "status": "skipped",
                    "durationMs": 0,
                    "message": "Skipped because an upstream stage already returned a structured error.",
                }
            ],
        }
    if not is_safe_select_sql(sql):
        return {
            "sql_valid": False,
            "error": {
                "stage": "validate_sql",
                "code": "SQL_UNSAFE",
                "message": "生成 SQL 不满足 SELECT-only 安全边界。",
            },
        }
    try:
        explain_sql(sql)
    except Exception as e:
        return {
            "sql_valid": False,
            "validation_error": {"stage": "validate_sql", "code": "SQL_VALIDATE_FAILED", "message": str(e)},
        }
    return {"sql_valid": True}


def correct_sql(state: DataAgentState) -> dict[str, Any]:
    if state.get("error") or not state.get("sql"):
        return {}
    if state.get("sql_valid") is True:
        return {
            "trace_stages": [
                {
                    "name": "correct_sql",
                    "status": "skipped",
                    "durationMs": 0,
                    "message": "Skipped because SQL already passed deterministic validation.",
                }
            ]
        }
    if not state.get("validation_error"):
        return {
            "trace_stages": [
                {
                    "name": "correct_sql",
                    "status": "skipped",
                    "durationMs": 0,
                    "message": "Skipped because no SQL validation error was available for correction.",
                }
            ]
        }
    sql_context = (state.get("candidate_context") or {}).get("sqlContext") or {}
    result = call_structured_llm(
        stage="correct_sql",
        prompt_name="correct_sql",
        response_model=SqlCorrection,
        user_payload={
            "question": state["question"],
            "intent": state.get("intent") or {},
            "sql": state.get("sql") or "",
            "sqlAlreadyValid": bool(state.get("sql_valid")),
            "validationError": state.get("validation_error"),
            "sqlContext": sql_context,
        },
        max_tokens=1500,
        timeout=60.0,
    )
    update = _llm_trace_update("correct_sql", result)
    if result.error:
        return {**update, "error": result.error}
    parsed = result.parsed
    assert isinstance(parsed, SqlCorrection)
    parsed.sql = _normalize_llm_select_sql(parsed.sql)
    allowed_tables, allowed_columns, _, allowed_joins = _context_allowed_sets(sql_context)
    sql_columns = referenced_full_names(parsed.sql)
    sql_tables = {_field_table(column) for column in sql_columns}
    problems: list[str] = []
    used_tables = {_normalize_table_name(table) for table in parsed.usedTables}
    used_columns = {_normalize_full_name(column) for column in parsed.usedColumns}
    used_joins = _normalize_join_references(parsed.joins, sql_context)
    if used_tables - allowed_tables:
        problems.append(f"tables={sorted(used_tables - allowed_tables)}")
    if used_columns - allowed_columns:
        problems.append(f"columns={sorted(used_columns - allowed_columns)}")
    if used_joins - allowed_joins:
        problems.append(f"joins={sorted(used_joins - allowed_joins)}")
    if sql_tables - allowed_tables:
        problems.append(f"sqlTables={sorted(sql_tables - allowed_tables)}")
    if sql_columns - allowed_columns:
        problems.append(f"sqlColumns={sorted(sql_columns - allowed_columns)}")
    if problems:
        return {
            **update,
            "error": {
                "stage": "correct_sql",
                "code": "LLM_OUTPUT_INVALID",
                "message": f"LLM 纠错 SQL 引用了候选 context 之外的对象: {'; '.join(problems)}",
            },
        }
    if is_safe_select_sql(parsed.sql):
        try:
            explain_sql(parsed.sql)
            return {**update, "sql": ensure_default_limit(parsed.sql), "sql_valid": True, "validation_error": None}
        except Exception as e:
            return {
                **update,
                "error": {
                    "stage": "correct_sql",
                    "code": "SQL_VALIDATE_FAILED",
                    "message": str(e),
                },
            }
    return {
        **update,
        "error": {
            "stage": "correct_sql",
            "code": "SQL_VALIDATE_FAILED",
            "message": state.get("validation_error", {}).get("message", "SQL 校验失败，自动纠错未成功。"),
        }
    }


def execute_sql(state: DataAgentState) -> dict[str, Any]:
    if state.get("error") or not state.get("sql_valid"):
        reason = (
            state.get("error", {}).get("message")
            if state.get("error")
            else "Skipped because SQL did not pass validation."
        )
        return {
            "rows": [],
            "row_count": 0,
            "trace_stages": [
                {
                    "name": "execute_sql",
                    "status": "skipped",
                    "durationMs": 0,
                    "message": reason,
                }
            ],
        }
    try:
        rows = execute_select(state["sql"])
    except Exception as e:
        return {
            "rows": [],
            "row_count": 0,
            "error": {"stage": "execute_sql", "code": "SQL_EXECUTE_FAILED", "message": str(e)},
        }
    return {"rows": rows, "row_count": len(rows)}


def _metric_explain(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": metric["metric_id"],
        "name": metric["name"],
        "formula": metric["formula"],
        "description": metric.get("description") or "",
        "unit": metric.get("unit"),
    }


def _build_visual(state: DataAgentState) -> dict[str, Any]:
    rows = state.get("rows") or []
    intent = state.get("intent") or {}
    metric = (state.get("metric_infos") or [{}])[0]
    plan_visual = ((state.get("sql_plan") or {}).get("visual") or {})
    visual_type = plan_visual.get("type") or intent.get("visualHint") or "table"
    first_row = rows[0] if rows else {}
    keys = list(first_row.keys())
    y_keys = plan_visual.get("y") or [
        key for key, value in first_row.items() if isinstance(value, (int, float))
    ]
    x_key = plan_visual.get("x") or next((key for key in keys if key not in y_keys), None)

    def column_for(key: str) -> dict[str, Any]:
        if key in y_keys or key in {metric.get("metric_id"), "value"}:
            col_type = "currency" if metric.get("unit") == "yuan" else "number"
            return {"key": key, "label": metric.get("name") or key, "type": col_type, "unit": metric.get("unit"), "precision": 2}
        if "date" in key or key.endswith("_at") or key in {"day", "month"}:
            return {"key": key, "label": key, "type": "date"}
        return {"key": key, "label": key, "type": "string"}

    if visual_type == "stat":
        value_key = y_keys[0] if y_keys else next(iter(first_row.keys()), "value")
        value = first_row.get(value_key) if first_row else None
        return {
            "type": "stat",
            "title": metric.get("name") or "问数指标",
            "columns": [
                {"key": "metric", "label": "指标", "type": "string"},
                column_for("value"),
            ],
            "rows": [{"metric": metric.get("name") or value_key, "value": value}],
        }
    columns = [column_for(key) for key in keys]
    visual = {
        "type": visual_type,
        "title": metric.get("name") or "问数结果",
        "columns": columns,
        "rows": rows,
    }
    if x_key:
        visual["x"] = x_key
    if y_keys:
        visual["y"] = y_keys
    return visual


def finalize_result(state: DataAgentState) -> dict[str, Any]:
    metric = (state.get("metric_infos") or [{}])[0]
    tables = [table.get("table_name") for table in state.get("table_infos", []) if table.get("table_name")]
    sql_context = (state.get("candidate_context") or {}).get("sqlContext") or {}
    context_columns = [column.get("full_name") for column in sql_context.get("columns", []) if column.get("full_name")]
    columns = _unique([*(metric.get("relevant_columns") or []), *context_columns])
    joins = [edge["join_id"] for edge in state.get("join_paths", [])]
    error = state.get("error")
    intent = state.get("intent") or {"analysisType": "detail", "metrics": [], "dimensions": [], "filters": []}
    if error:
        visual = {"type": "table", "title": "问数失败", "columns": [], "rows": []}
        answer = error["message"]
    else:
        visual = _build_visual(state)
        answer = _answer_text(state, visual)
    explain = {
        "sql": state.get("sql") or "",
        "metrics": [_metric_explain(metric)] if metric else [],
        "tables": tables,
        "columns": columns,
        "joins": joins,
        "assumptions": (state.get("sql_plan") or {}).get("assumptions")
        or (["未指定校区或课程时统计全部数据。"] if intent["analysisType"] != "ranking" else []),
    }
    return {"visual": visual, "answer": answer, "explain": explain, "intent": intent}


def _answer_text(state: DataAgentState, visual: dict[str, Any]) -> str:
    analysis_type = state["intent"]["analysisType"]
    metric_name = ((state.get("metric_infos") or [{}])[0]).get("name") or "指标"
    if analysis_type == "trend":
        return f"{metric_name}趋势已返回，共 {len(visual.get('rows') or [])} 个数据点。"
    if analysis_type == "ranking":
        return f"{metric_name}排名已返回，共 {len(visual.get('rows') or [])} 条结果。"
    if analysis_type == "detail":
        return f"明细结果已返回，共 {len(visual.get('rows') or [])} 行。"
    value = (visual.get("rows") or [{}])[0].get("value")
    return f"{metric_name}为 {value}。"


extract_keywords_node = _stage("extract_keywords", extract_keywords)
expand_search_keywords_node = _stage("expand_search_keywords", expand_search_keywords)
recall_metric_node = _stage("recall_metric", recall_metric)
recall_column_node = _stage("recall_column", recall_column)
recall_value_node = _stage("recall_value", recall_value)
merge_retrieved_info_node = _stage("merge_retrieved_info", merge_retrieved_info)
structure_intent_node = _stage("structure_intent", structure_intent)
filter_table_node = _stage("filter_table", filter_table)
filter_metric_node = _stage("filter_metric", filter_metric)
add_extra_context_node = _stage("add_extra_context", add_extra_context)
generate_sql_node = _stage("generate_sql", generate_sql)
validate_sql_node = _stage("validate_sql", validate_sql)
correct_sql_node = _stage("correct_sql", correct_sql)
execute_sql_node = _stage("execute_sql", execute_sql)
finalize_result_node = _stage("finalize_result", finalize_result)
