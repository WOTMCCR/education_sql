from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from knowledge.analytics.agent.llm_schema import parse_model
from knowledge.analytics.agent.llm_utils import summarize_for_trace
from knowledge.analytics.meta_store import (
    find_join_path,
    get_columns_by_full_names,
    get_dimensions_by_ids,
    get_metric_context,
    get_table_context,
    referenced_full_names,
)
from knowledge.analytics.search import search_columns, search_metrics, search_values
from knowledge.core import llm as core_llm
from knowledge.core.config import get_settings
from knowledge.models.chat import MetaCitation, MetaQaResponse


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "meta_qa_answer.md"
DATA_QUERY_WORDS = ("多少", "几个", "趋势", "排名", "最高", "最低", "明细", "本月", "最近", "同比", "环比")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def _requires_data_qa(question: str) -> bool:
    return any(word in question for word in DATA_QUERY_WORDS) and not any(
        word in question for word in ("怎么算", "口径", "定义", "字段", "哪些表", "支持哪些维度", "为什么")
    )


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


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


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


def _requires_data_qa_response(question: str, *, started: float) -> dict[str, Any]:
    answer = "这个问题需要查询真实统计值，请切换到“数据问数”模式。"
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
    settings = get_settings()
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    stage_started = time.perf_counter()

    if not settings.openai_api_key or not settings.llm_model:
        stage = {
            "name": "meta_qa_llm",
            "status": "error",
            "durationMs": round((time.perf_counter() - stage_started) * 1000),
            "llm_called": False,
            "promptName": PROMPT_PATH.name,
            "promptHash": _prompt_hash(prompt),
            "usage": {"usageUnavailable": True},
            "message": "Meta QA 需要配置 OPENAI_API_KEY 和 LLM_MODEL。",
        }
        return _error_response(
            question,
            code="META_QA_UNAVAILABLE",
            message="数据说明暂时不可用：LLM 未配置。",
            started=started,
            stage=stage,
        )

    user_payload = {
        "question": question,
        "context": context,
        "allowedCitationKeys": [{"kind": kind, "id": entity_id} for kind, entity_id in allowed],
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
    ]
    result = core_llm.chat_completion_text(
        model=settings.llm_model,
        messages=messages,
        purpose="analytics.meta_qa",
        temperature=0.0,
        max_tokens=1200,
        timeout=45.0,
        trigger_cooldown=False,
        response_format={"type": "json_object"},
        return_metadata=True,
    )
    if result is None:
        stage = {
            "name": "meta_qa_llm",
            "status": "error",
            "durationMs": round((time.perf_counter() - stage_started) * 1000),
            "llm_called": True,
            "promptName": PROMPT_PATH.name,
            "promptHash": _prompt_hash(prompt),
            "inputSummary": summarize_for_trace({k: len(v) if isinstance(v, list) else v for k, v in context.items()}),
            "usage": {"usageUnavailable": True},
            "message": "LLM 返回空内容或调用失败。",
        }
        return _error_response(
            question,
            code="META_QA_UNAVAILABLE",
            message="数据说明暂时不可用：LLM 调用失败。",
            started=started,
            stage=stage,
        )

    raw = result.text if isinstance(result, core_llm.ChatCompletionTextResult) else str(result)
    usage = result.usage if isinstance(result, core_llm.ChatCompletionTextResult) else {"usageUnavailable": True}
    try:
        parsed = parse_model(raw, MetaQaResponse)
    except ValueError as e:
        stage = {
            "name": "meta_qa_llm",
            "status": "error",
            "durationMs": round((time.perf_counter() - stage_started) * 1000),
            "llm_called": True,
            "promptName": PROMPT_PATH.name,
            "promptHash": _prompt_hash(prompt),
            "usage": usage or {"usageUnavailable": True},
            "message": str(e),
        }
        return _error_response(
            question,
            code="META_QA_OUTPUT_INVALID",
            message="数据说明暂时不可用：LLM 输出结构无效。",
            started=started,
            stage=stage,
        )

    assert isinstance(parsed, MetaQaResponse)
    citations: list[dict[str, str]] = []
    for citation in parsed.citations:
        key = (citation.kind, citation.id)
        if key in allowed:
            citations.append(allowed[key])
    if not citations and allowed and not parsed.unsupported_reason:
        citations = list(allowed.values())[:3]

    stage = {
        "name": "meta_qa_llm",
        "status": "ok",
        "durationMs": round((time.perf_counter() - stage_started) * 1000),
        "llm_called": True,
        "promptName": PROMPT_PATH.name,
        "promptHash": _prompt_hash(prompt),
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
        "usage": usage or {"usageUnavailable": True},
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


def run_meta_qa(question: str, session_id: str | None = None) -> dict[str, Any]:
    del session_id
    started = time.perf_counter()
    if _requires_data_qa(question):
        return _requires_data_qa_response(question, started=started)
    context, allowed = _build_context(question)
    return _call_meta_llm(question, context, allowed, started)
