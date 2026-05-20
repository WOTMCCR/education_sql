from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from knowledge.analytics.meta_store import (
    find_join_path,
    get_catalog_overview,
    get_columns_by_full_names,
    get_dimensions_by_ids,
    get_metric_context,
    get_table_context,
    referenced_full_names,
)
from knowledge.analytics.search import search_columns, search_metrics, search_values
from knowledge.core import llm as core_llm
from knowledge.core.config import get_settings
from knowledge.core.structured_llm import StructuredLlmClient
from knowledge.models.chat import MetaCitation, MetaQaResponse
from knowledge.runtime import make_thread_id, run_graph


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "meta_qa_answer.md"
DATA_QUERY_WORDS = ("多少", "几个", "趋势", "排名", "最高", "最低", "明细", "本月", "最近", "同比", "环比")
CATALOG_OVERVIEW_WORDS = (
    "有哪些表",
    "有什么表",
    "哪些表",
    "有哪些数据",
    "有什么数据",
    "有哪些数据库",
    "有什么数据库",
    "有哪些指标",
    "有什么指标",
    "我能问什么",
    "我可以问什么",
    "能问哪些",
    "可以问哪些",
    "关注哪些指标",
    "应该关注哪些",
    "insight",
    "洞察",
)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def _requires_data_qa(question: str) -> bool:
    return any(word in question for word in DATA_QUERY_WORDS) and not any(
        word in question for word in ("怎么算", "口径", "定义", "字段", "哪些表", "支持哪些维度", "为什么")
    )


def _is_catalog_overview_question(question: str) -> bool:
    normalized = question.lower()
    return any(word in normalized for word in CATALOG_OVERVIEW_WORDS)


def _citation(kind: str, source: str, item: dict[str, Any]) -> dict[str, str]:
    if kind == "metric":
        entity_id = item.get("metric_id") or item.get("id")
        name = item.get("name") or str(entity_id)
    elif kind == "column":
        entity_id = item.get("full_name") or item.get("id")
        name = item.get("description") or str(entity_id)
    elif kind == "table":
        entity_id = item.get("table_name")
        name = item.get("business_name") or str(entity_id)
    elif kind == "dimension":
        entity_id = item.get("dimension_id") or item.get("id")
        name = item.get("name") or str(entity_id)
    elif kind == "join":
        entity_id = item.get("join_id") or item.get("id")
        name = item.get("description") or str(entity_id)
    else:
        entity_id = item.get("value_id") or item.get("value") or item.get("id")
        name = item.get("value") or str(entity_id)
    return {
        "kind": kind,
        "id": str(entity_id or ""),
        "name": str(name or ""),
        "source": source,
        "description": str(item.get("description") or ""),
    }


def _catalog_overview_response(question: str, *, started: float) -> dict[str, Any]:
    overview = get_catalog_overview()
    tables = overview["tables"]
    metrics = overview["metrics"]
    dimensions = overview["dimensions"]

    table_lines = [
        f"- `{item['table_name']}`：{item.get('business_name') or item['table_name']}，约 {item.get('row_count') or 0} 行"
        for item in tables[:10]
    ]
    metric_lines = [
        f"- `{item['metric_id']}`：{item.get('name') or item['metric_id']}，{item.get('description') or '已配置业务口径'}"
        for item in metrics[:10]
    ]
    dimension_names = "、".join([str(item.get("name") or item.get("dimension_id")) for item in dimensions[:8]])
    question_examples = [
        "本月报名人数是多少？",
        "最近30天收入如何？",
        "哪个校区报名人数最多？",
        "按课程系列统计本月收入",
        "最近三个月完课率变化情况",
    ]
    answer = "\n".join(
        [
            f"当前数据资产包含 {overview['table_count']} 张业务表、{overview['metric_count']} 个指标、{overview['dimension_count']} 个可用维度。",
            "",
            "核心表：",
            *table_lines,
            "",
            "核心指标：",
            *metric_lines,
            "",
            f"常用分析维度包括：{dimension_names}。",
            "",
            "建议优先关注报名、收入、退款、完课率、出勤率、转化率等指标，并结合时间、校区、课程系列、班次做趋势、排名和对比。",
            "",
            "可以直接这样问：",
            *[f"- {item}" for item in question_examples],
        ]
    )
    citations = [
        *[_citation("table", "meta_table_info", item) for item in tables[:3]],
        *[_citation("metric", "meta_metric_info", item) for item in metrics[:3]],
    ]
    stage = {
        "name": "meta_qa_catalog_overview",
        "status": "ok",
        "durationMs": round((time.perf_counter() - started) * 1000),
        "message": "Answered catalog overview with deterministic metadata summary.",
        "outputSummary": {
            "tableCount": overview["table_count"],
            "metricCount": overview["metric_count"],
            "dimensionCount": overview["dimension_count"],
        },
    }
    return {
        "ok": True,
        "result_type": "meta_answer",
        "mode": "meta_qa",
        "answer": answer,
        "citations": citations,
        "blocks": [{"type": "markdown", "content": answer}, {"type": "meta_citations", "data": citations}],
        "trace": {"stages": [stage], "durationMs": round((time.perf_counter() - started) * 1000)},
        "question": question,
    }


def _build_context(question: str) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, str]]]:
    metrics = search_metrics(question, 6)
    columns = search_columns(question, 8)
    values = search_values(question, 5)

    metric_ids = _unique([str(item.get("metric_id") or item.get("id") or "") for item in metrics])[:6]
    metric_context = get_metric_context(metric_ids)

    full_names = _unique(
        [
            str(item.get("full_name") or item.get("id") or "")
            for item in columns
        ]
        + [
            str(name)
            for metric in metric_context
            for name in (metric.get("relevant_columns") or [])
        ]
        + [
            str(name)
            for metric in metric_context
            for name in referenced_full_names(metric.get("formula"))
        ]
    )[:24]
    column_context = get_columns_by_full_names(full_names)

    dimension_ids = _unique(
        [
            str(dimension_id)
            for metric in metric_context
            for dimension_id in (metric.get("allowed_dimensions") or [])
        ]
        + [str(value.get("dimension_id") or "") for value in values]
    )[:16]
    dimensions = get_dimensions_by_ids(dimension_ids)

    table_names = _unique(
        [str(metric.get("base_table") or "") for metric in metric_context]
        + [str(column.get("table_name") or "") for column in column_context]
        + [str(dimension.get("table_name") or "") for dimension in dimensions if dimension.get("table_name") != "*"]
    )[:16]
    tables = get_table_context(table_names)

    joins: list[dict[str, Any]] = []
    for metric in metric_context[:3]:
        base_table = str(metric.get("base_table") or "")
        for table_name in table_names:
            if base_table and table_name and base_table != table_name:
                joins.extend(find_join_path(base_table, table_name))
    joins_by_id = {join.get("join_id"): join for join in joins if join.get("join_id")}
    joins = list(joins_by_id.values())[:12]

    context = {
        "question": question,
        "metrics": metric_context,
        "columns": column_context,
        "dimensions": dimensions,
        "tables": tables,
        "joins": joins,
        "values": values,
    }

    allowed: dict[tuple[str, str], dict[str, str]] = {}
    for item in metric_context:
        c = _citation("metric", "meta_metric_info", item)
        allowed[(c["kind"], c["id"])] = c
    for item in column_context:
        c = _citation("column", "meta_column_info", item)
        allowed[(c["kind"], c["id"])] = c
    for item in dimensions:
        c = _citation("dimension", "meta_dimension_info", item)
        allowed[(c["kind"], c["id"])] = c
    for item in tables:
        c = _citation("table", "meta_table_info", item)
        allowed[(c["kind"], c["id"])] = c
    for item in joins:
        c = _citation("join", "meta_join_info", item)
        allowed[(c["kind"], c["id"])] = c
    for item in values:
        c = _citation("value", "meta_dimension_info", item)
        allowed[(c["kind"], c["id"])] = c

    return context, allowed


def _error_response(question: str, *, code: str, message: str, started: float, stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "result_type": "meta_error",
        "mode": "meta_qa",
        "answer": message,
        "citations": [],
        "blocks": [{"type": "markdown", "content": message}],
        "trace": {
            "stages": [stage],
            "durationMs": round((time.perf_counter() - started) * 1000),
        },
        "error": {"stage": "meta_qa", "code": code, "message": message},
        "question": question,
    }


def _prompt_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _requires_data_qa_response(question: str, *, started: float) -> dict[str, Any]:
    answer = "这个问题需要查询真实统计值，请切换到“数据分析”模式。"
    return {
        "ok": True,
        "result_type": "meta_answer",
        "mode": "meta_qa",
        "answer": answer,
        "citations": [],
        "blocks": [{"type": "markdown", "content": answer}, {"type": "meta_citations", "data": []}],
        "trace": {
            "stages": [
                {
                    "name": "meta_qa_route",
                    "status": "skipped",
                    "durationMs": 0,
                    "message": "META_QUERY_REQUIRES_DATA_QA",
                    "suggestedMode": "data_qa",
                }
            ],
            "durationMs": round((time.perf_counter() - started) * 1000),
        },
        "error": {"stage": "meta_qa_route", "code": "META_QUERY_REQUIRES_DATA_QA", "message": answer},
        "question": question,
    }


def _call_meta_llm(question: str, context: dict[str, Any], allowed: dict[tuple[str, str], dict[str, str]], started: float) -> dict[str, Any]:
    user_payload = {
        "question": question,
        "context": context,
        "allowedCitationKeys": [{"kind": kind, "id": entity_id} for kind, entity_id in allowed],
    }
    llm_result = StructuredLlmClient(prompt_dir=PROMPT_PATH.parent, settings=get_settings()).invoke_schema(
        stage="meta_qa_llm",
        prompt_name=PROMPT_PATH.stem,
        response_model=MetaQaResponse,
        payload=user_payload,
        max_tokens=1200,
        timeout=45.0,
        purpose="analytics.meta_qa",
    )
    if llm_result.error:
        stage = {**llm_result.trace.as_stage(), "promptHash": _prompt_hash(PROMPT_PATH), "message": llm_result.error["message"]}
        unavailable = llm_result.error["code"] == "LLM_UNAVAILABLE"
        return _error_response(
            question,
            code="META_QA_UNAVAILABLE" if unavailable else "META_QA_OUTPUT_INVALID",
            message="数据说明暂时不可用：LLM 调用失败。" if unavailable else "数据说明暂时不可用：LLM 输出结构无效。",
            started=started,
            stage=stage,
        )

    parsed = llm_result.parsed
    assert isinstance(parsed, MetaQaResponse)
    citations: list[dict[str, str]] = []
    for citation in parsed.citations:
        key = (citation.kind, citation.id)
        if key in allowed:
            citations.append(allowed[key])
    if not citations and allowed and not parsed.unsupported_reason:
        citations = list(allowed.values())[:3]

    stage = {
        **llm_result.trace.as_stage(),
        "promptHash": _prompt_hash(PROMPT_PATH),
        "inputSummary": {
            "metrics": len(context.get("metrics") or []),
            "columns": len(context.get("columns") or []),
            "dimensions": len(context.get("dimensions") or []),
            "tables": len(context.get("tables") or []),
            "joins": len(context.get("joins") or []),
            "values": len(context.get("values") or []),
        },
        "outputSummary": {
            "answerPreview": parsed.answer_markdown[:240],
            "citationCount": len(citations),
            "unsupportedReason": parsed.unsupported_reason,
            "suggestedMode": parsed.suggested_mode,
        },
    }
    answer = parsed.answer_markdown
    return {
        "ok": True,
        "result_type": "meta_answer",
        "mode": "meta_qa",
        "answer": answer,
        "citations": citations,
        "blocks": [
            {"type": "markdown", "content": answer},
            {"type": "meta_citations", "data": citations},
        ],
        "trace": {
            "stages": [stage],
            "durationMs": round((time.perf_counter() - started) * 1000),
        },
        "question": question,
        **({"error": {"stage": "meta_qa_llm", "code": parsed.unsupported_reason, "message": answer}} if parsed.unsupported_reason else {}),
    }


def _run_meta_qa_direct(question: str, session_id: str | None = None) -> dict[str, Any]:
    del session_id
    started = time.perf_counter()
    if _is_catalog_overview_question(question):
        return _catalog_overview_response(question, started=started)
    if _requires_data_qa(question):
        return _requires_data_qa_response(question, started=started)
    context, allowed = _build_context(question)
    return _call_meta_llm(question, context, allowed, started)


def run_meta_qa(question: str, session_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    from knowledge.analytics.meta_qa.graph import build_meta_qa_graph

    started = time.perf_counter()
    task_id = task_id or f"run_{uuid.uuid4().hex[:12]}"
    graph_run = run_graph(
        build_meta_qa_graph(),
        graph_name="meta_qa",
        thread_id=make_thread_id(graph_name="meta_qa", session_id=session_id, task_id=task_id),
        input_state={
            "question": question,
            "session_id": session_id,
            "trace_stages": [],
            "started_at": started,
        },
    )
    result = graph_run.state.get("result") or _error_response(
        question,
        code="META_QA_GRAPH_EMPTY",
        message="数据说明暂时不可用：graph 未返回结果。",
        started=started,
        stage={"name": "meta_qa_graph", "status": "error", "durationMs": 0},
    )
    result["trace"] = {**(result.get("trace") or {}), **graph_run.trace}
    return result
