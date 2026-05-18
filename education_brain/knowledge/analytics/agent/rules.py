from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from knowledge.analytics.agent.sql import execute_select


def _month_range(today: date) -> tuple[str, str, str]:
    start = today.replace(day=1)
    end_exclusive = today + timedelta(days=1)
    return start.isoformat(), today.isoformat(), end_exclusive.isoformat()


def _week_ranges(today: date) -> dict[str, tuple[str, str]]:
    this_week_start = today - timedelta(days=today.weekday())
    this_week_end = today + timedelta(days=1)
    last_week_start = this_week_start - timedelta(days=7)
    return {
        "this_week": (this_week_start.isoformat(), this_week_end.isoformat()),
        "last_week": (last_week_start.isoformat(), this_week_start.isoformat()),
    }


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)


def _format_money(value: Any) -> str:
    return f"{_number(value):,.2f}"


def _format_percent(value: Any) -> str:
    return f"{_number(value) * 100:.2f}%"


def _contains_any(question: str, words: tuple[str, ...]) -> bool:
    return any(word in question for word in words)


def _base_result(
    *,
    question: str,
    started_at: float,
    answer: str,
    intent: dict[str, Any],
    visual: dict[str, Any],
    explain: dict[str, Any],
    row_count: int,
) -> dict[str, Any]:
    return {
        "queryId": f"dq_rule_{uuid.uuid4().hex[:12]}",
        "mode": "data_qa",
        "question": question,
        "answer": answer,
        "intent": intent,
        "visual": visual,
        "explain": explain,
        "trace": {
            "stages": [
                {
                    "name": "deterministic_rule",
                    "status": "ok",
                    "durationMs": round((time.perf_counter() - started_at) * 1000),
                    "message": "Matched a deterministic analytics rule for a core business question.",
                }
            ],
            "rowCount": row_count,
            "durationMs": round((time.perf_counter() - started_at) * 1000),
        },
        "warnings": [],
    }


def _error_result(question: str, started_at: float, error: Exception) -> dict[str, Any]:
    message = f"确定性问数规则执行失败：{error}"
    return {
        "queryId": f"dq_rule_{uuid.uuid4().hex[:12]}",
        "mode": "data_qa",
        "question": question,
        "answer": message,
        "intent": {"analysisType": "detail", "metrics": [], "dimensions": [], "filters": []},
        "visual": {"type": "table", "title": "问数失败", "columns": [], "rows": []},
        "explain": {"sql": "", "metrics": [], "tables": [], "columns": [], "joins": [], "assumptions": []},
        "trace": {
            "stages": [
                {
                    "name": "deterministic_rule",
                    "status": "error",
                    "durationMs": round((time.perf_counter() - started_at) * 1000),
                    "message": message,
                }
            ],
            "rowCount": 0,
            "durationMs": round((time.perf_counter() - started_at) * 1000),
        },
        "warnings": [],
        "error": {"stage": "deterministic_rule", "code": "DETERMINISTIC_RULE_FAILED", "message": message},
    }


def _course_series_revenue(question: str, started_at: float, today: date) -> dict[str, Any]:
    start, end, end_exclusive = _month_range(today)
    sql = f"""
SELECT
  series.series_name AS series,
  ROUND(SUM(order_item.payable_amount), 2) AS paid_revenue
FROM `order`
JOIN order_item ON `order`.id = order_item.order_id
JOIN series_cohort ON order_item.cohort_id = series_cohort.id
JOIN series ON series_cohort.series_id = series.id
WHERE `order`.order_status IN ('paid', 'completed')
  AND order_item.order_item_status IN ('paid', 'completed')
  AND `order`.paid_at >= '{start}'
  AND `order`.paid_at < '{end_exclusive}'
GROUP BY series.id, series.series_name
ORDER BY paid_revenue DESC
LIMIT 20
""".strip()
    rows = execute_select(sql)
    visual = {
        "type": "bar",
        "title": "本月课程系列收入",
        "x": "series",
        "y": ["paid_revenue"],
        "columns": [
            {"key": "series", "label": "课程系列", "type": "string"},
            {"key": "paid_revenue", "label": "收入金额", "type": "currency", "unit": "yuan", "precision": 2},
        ],
        "rows": rows,
    }
    return _base_result(
        question=question,
        started_at=started_at,
        answer=f"按课程系列统计的本月收入已返回，共 {len(rows)} 条结果。",
        intent={
            "analysisType": "ranking",
            "metrics": ["paid_revenue"],
            "dimensions": ["series"],
            "filters": [],
            "timeRange": {"start": start, "end": end, "endExclusive": end_exclusive, "grain": "day", "label": "本月"},
            "sort": [{"field": "paid_revenue", "direction": "desc"}],
            "limit": 20,
            "visualHint": "bar",
        },
        visual=visual,
        explain={
            "sql": sql,
            "metrics": [{"id": "paid_revenue", "name": "收入金额", "unit": "yuan"}],
            "tables": ["order", "order_item", "series_cohort", "series"],
            "columns": ["order.paid_at", "order.order_status", "order_item.payable_amount", "order_item.cohort_id", "series.series_name"],
            "joins": ["order_order_item", "order_item_cohort", "cohort_series"],
            "assumptions": ["课程系列收入按订单明细 payable_amount 归因到课程系列，避免订单级金额在多明细场景下重复累计。"],
        },
        row_count=len(rows),
    )


def _cohort_enrollment(question: str, started_at: float, today: date) -> dict[str, Any]:
    start, end, end_exclusive = _month_range(today)
    sql = f"""
SELECT
  series_cohort.cohort_name AS cohort,
  COUNT(DISTINCT student_cohort_rel.student_id) AS enrolled_student_count
FROM student_cohort_rel
JOIN series_cohort ON student_cohort_rel.cohort_id = series_cohort.id
WHERE student_cohort_rel.enroll_at >= '{start}'
  AND student_cohort_rel.enroll_at < '{end_exclusive}'
GROUP BY series_cohort.id, series_cohort.cohort_name
ORDER BY enrolled_student_count DESC
LIMIT 20
""".strip()
    rows = execute_select(sql)
    visual = {
        "type": "bar",
        "title": "本月班次报名学员数",
        "x": "cohort",
        "y": ["enrolled_student_count"],
        "columns": [
            {"key": "cohort", "label": "班次", "type": "string"},
            {"key": "enrolled_student_count", "label": "报名学员数", "type": "number", "unit": "people", "precision": 0},
        ],
        "rows": rows,
    }
    return _base_result(
        question=question,
        started_at=started_at,
        answer=f"按班次统计的本月报名学员数已返回，共 {len(rows)} 条结果。",
        intent={
            "analysisType": "ranking",
            "metrics": ["enrolled_student_count"],
            "dimensions": ["cohort"],
            "filters": [],
            "timeRange": {"start": start, "end": end, "endExclusive": end_exclusive, "grain": "day", "label": "本月"},
            "sort": [{"field": "enrolled_student_count", "direction": "desc"}],
            "limit": 20,
            "visualHint": "bar",
        },
        visual=visual,
        explain={
            "sql": sql,
            "metrics": [{"id": "enrolled_student_count", "name": "报名学员数", "unit": "people"}],
            "tables": ["student_cohort_rel", "series_cohort"],
            "columns": ["student_cohort_rel.student_id", "student_cohort_rel.enroll_at", "student_cohort_rel.cohort_id", "series_cohort.cohort_name"],
            "joins": ["student_cohort_cohort"],
            "assumptions": ["报名学员数按 student_id 去重统计。"],
        },
        row_count=len(rows),
    )


def _series_refund_rate(question: str, started_at: float, today: date) -> dict[str, Any]:
    time_filter_revenue = ""
    time_filter_refund = ""
    time_range: dict[str, Any] | None = None
    if "本月" in question:
        start, end, end_exclusive = _month_range(today)
        time_filter_revenue = f"AND `order`.paid_at >= '{start}' AND `order`.paid_at < '{end_exclusive}'"
        time_filter_refund = f"AND refund_request.refunded_at >= '{start}' AND refund_request.refunded_at < '{end_exclusive}'"
        time_range = {"start": start, "end": end, "endExclusive": end_exclusive, "grain": "day", "label": "本月"}

    sql = f"""
SELECT
  revenue.series,
  ROUND(COALESCE(refunds.refund_amount, 0), 2) AS refund_amount,
  ROUND(revenue.paid_revenue, 2) AS paid_revenue,
  ROUND(COALESCE(refunds.refund_amount, 0) / NULLIF(revenue.paid_revenue, 0), 4) AS refund_rate
FROM (
  SELECT
    series.id AS series_id,
    series.series_name AS series,
    SUM(order_item.payable_amount) AS paid_revenue
  FROM `order`
  JOIN order_item ON `order`.id = order_item.order_id
  JOIN series_cohort ON order_item.cohort_id = series_cohort.id
  JOIN series ON series_cohort.series_id = series.id
  WHERE `order`.order_status IN ('paid', 'completed', 'partial_refunded', 'refunded')
    AND order_item.order_item_status IN ('paid', 'completed', 'refunded')
    {time_filter_revenue}
  GROUP BY series.id, series.series_name
) revenue
LEFT JOIN (
  SELECT
    series.id AS series_id,
    SUM(refund_request.approved_amount) AS refund_amount
  FROM refund_request
  JOIN order_item ON refund_request.order_item_id = order_item.id
  JOIN series_cohort ON order_item.cohort_id = series_cohort.id
  JOIN series ON series_cohort.series_id = series.id
  WHERE refund_request.refund_status = 'refunded'
    AND refund_request.yn = 1
    {time_filter_refund}
  GROUP BY series.id
) refunds ON revenue.series_id = refunds.series_id
WHERE revenue.paid_revenue > 0
ORDER BY refund_rate DESC, refund_amount DESC
LIMIT 10
""".strip()
    rows = execute_select(sql)
    top = rows[0] if rows else {}
    answer = "课程系列退款率排名已返回。"
    if top:
        answer = f"课程系列退款率排名已返回，共 {len(rows)} 条结果；最高为 {top.get('series')}（{_format_percent(top.get('refund_rate'))}）。"
    return _base_result(
        question=question,
        started_at=started_at,
        answer=answer,
        intent={
            "analysisType": "ranking",
            "metrics": ["refund_rate"],
            "dimensions": ["series"],
            "filters": [],
            **({"timeRange": time_range} if time_range else {}),
            "sort": [{"field": "refund_rate", "direction": "desc"}],
            "limit": 10,
            "visualHint": "bar",
        },
        visual={
            "type": "bar",
            "title": "课程系列退款率",
            "x": "series",
            "y": ["refund_rate"],
            "columns": [
                {"key": "series", "label": "课程系列", "type": "string"},
                {"key": "refund_rate", "label": "退款率", "type": "number", "unit": "ratio", "precision": 4},
                {"key": "refund_amount", "label": "退款金额", "type": "currency", "unit": "yuan", "precision": 2},
                {"key": "paid_revenue", "label": "收入金额", "type": "currency", "unit": "yuan", "precision": 2},
            ],
            "rows": rows,
        },
        explain={
            "sql": sql,
            "metrics": [{"id": "refund_rate", "name": "退款率", "unit": "ratio"}],
            "tables": ["refund_request", "order", "order_item", "series_cohort", "series"],
            "columns": ["refund_request.approved_amount", "refund_request.refunded_at", "order_item.payable_amount", "series.series_name"],
            "joins": ["refund_order_item", "order_order_item", "order_item_cohort", "cohort_series"],
            "assumptions": ["课程系列退款率使用已退款金额除以课程系列已成交或已退款订单明细应付金额，避免订单级金额跨多个课程系列重复累计。"],
        },
        row_count=len(rows),
    )


def _renewal_week_comparison(question: str, started_at: float, today: date) -> dict[str, Any]:
    ranges = _week_ranges(today)
    this_start, this_end = ranges["this_week"]
    last_start, last_end = ranges["last_week"]
    sql = f"""
SELECT
  '本周' AS period,
  COALESCE(ROUND(SUM(`order`.paid_amount), 2), 0) AS renewal_revenue,
  COUNT(DISTINCT `order`.student_id) AS renewal_students
FROM `order`
WHERE `order`.order_status IN ('paid', 'completed')
  AND `order`.paid_at >= '{this_start}'
  AND `order`.paid_at < '{this_end}'
  AND EXISTS (
    SELECT 1 FROM `order` previous_order
    WHERE previous_order.student_id = `order`.student_id
      AND previous_order.order_status IN ('paid', 'completed')
      AND previous_order.paid_at < '{this_start}'
  )
UNION ALL
SELECT
  '上周' AS period,
  COALESCE(ROUND(SUM(`order`.paid_amount), 2), 0) AS renewal_revenue,
  COUNT(DISTINCT `order`.student_id) AS renewal_students
FROM `order`
WHERE `order`.order_status IN ('paid', 'completed')
  AND `order`.paid_at >= '{last_start}'
  AND `order`.paid_at < '{last_end}'
  AND EXISTS (
    SELECT 1 FROM `order` previous_order
    WHERE previous_order.student_id = `order`.student_id
      AND previous_order.order_status IN ('paid', 'completed')
      AND previous_order.paid_at < '{last_start}'
  )
""".strip()
    rows = execute_select(sql)
    by_period = {row["period"]: row for row in rows}
    this_value = _number(by_period.get("本周", {}).get("renewal_revenue"))
    last_value = _number(by_period.get("上周", {}).get("renewal_revenue"))
    delta = this_value - last_value
    change_rate = None if last_value == 0 else delta / last_value
    for row in rows:
        if row.get("period") == "本周":
            row["delta_vs_last_week"] = round(delta, 2)
            row["change_rate"] = round(change_rate, 4) if change_rate is not None else None
        else:
            row["delta_vs_last_week"] = None
            row["change_rate"] = None
    change_text = "上周为 0，无法计算变化率" if change_rate is None else f"变化率 {_format_percent(change_rate)}"
    return _base_result(
        question=question,
        started_at=started_at,
        answer=f"续费金额对比已返回：本周 {_format_money(this_value)} 元，上周 {_format_money(last_value)} 元，差额 {_format_money(delta)} 元，{change_text}。",
        intent={
            "analysisType": "comparison",
            "metrics": ["renewal_revenue"],
            "dimensions": ["paid_date"],
            "filters": [],
            "timeRange": {"start": last_start, "end": today.isoformat(), "endExclusive": this_end, "grain": "week", "label": "本周对比上周"},
            "sort": [],
            "limit": 2,
            "visualHint": "bar",
        },
        visual={
            "type": "bar",
            "title": "本周与上周续费金额对比",
            "x": "period",
            "y": ["renewal_revenue"],
            "columns": [
                {"key": "period", "label": "周期", "type": "string"},
                {"key": "renewal_revenue", "label": "续费金额", "type": "currency", "unit": "yuan", "precision": 2},
                {"key": "renewal_students", "label": "续费学员数", "type": "number", "unit": "people", "precision": 0},
                {"key": "delta_vs_last_week", "label": "较上周差额", "type": "currency", "unit": "yuan", "precision": 2},
                {"key": "change_rate", "label": "变化率", "type": "number", "unit": "ratio", "precision": 4},
            ],
            "rows": rows,
        },
        explain={
            "sql": sql,
            "metrics": [{"id": "renewal_revenue", "name": "续费金额", "unit": "yuan"}],
            "tables": ["order"],
            "columns": ["order.student_id", "order.paid_amount", "order.order_status", "order.paid_at"],
            "joins": [],
            "assumptions": ["续费定义为本期发生支付，且同一学员在本期开始前存在已支付或已完成订单。"],
        },
        row_count=len(rows),
    )


def run_rule_based_data_qa(question: str, *, started_at: float, today: date | None = None) -> dict[str, Any] | None:
    today = today or date.today()
    normalized = question.replace(" ", "")
    try:
        if "续费" in normalized and "本周" in normalized and "上周" in normalized and _contains_any(normalized, ("对比", "比较", "差异")):
            return _renewal_week_comparison(question, started_at, today)
        if "退款率" in normalized and _contains_any(normalized, ("课程系列", "课程")) and _contains_any(normalized, ("最高", "排名", "最多")):
            return _series_refund_rate(question, started_at, today)
        if normalized.startswith("按") and _contains_any(normalized, ("课程系列", "课程")) and "收入" in normalized:
            return _course_series_revenue(question, started_at, today)
        if normalized.startswith("按") and "班次" in normalized and "报名" in normalized:
            return _cohort_enrollment(question, started_at, today)
    except Exception as e:
        return _error_result(question, started_at, e)
    return None
