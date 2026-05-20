from __future__ import annotations

from decimal import Decimal
from typing import Any


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)


def reshape_time_comparison(
    rows: list[dict[str, Any]],
    *,
    dimension_aliases: list[str],
    metric_alias: str,
    current_label: str,
    baseline_label: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(alias) for alias in dimension_aliases)
        target = grouped.setdefault(key, {alias: row.get(alias) for alias in dimension_aliases})
        bucket = row.get("comparison_bucket")
        if bucket == "current":
            target["current_value"] = _number(row.get(metric_alias))
            target["current_label"] = current_label
        elif bucket == "baseline":
            target["baseline_value"] = _number(row.get(metric_alias))
            target["baseline_label"] = baseline_label

    result: list[dict[str, Any]] = []
    for item in grouped.values():
        current_value = _number(item.get("current_value"))
        baseline_value = _number(item.get("baseline_value"))
        delta = current_value - baseline_value
        item["current_value"] = current_value
        item["baseline_value"] = baseline_value
        item["delta"] = delta
        item["delta_rate"] = None if baseline_value == 0 else delta / baseline_value
        item.setdefault("current_label", current_label)
        item.setdefault("baseline_label", baseline_label)
        result.append(item)
    return result
