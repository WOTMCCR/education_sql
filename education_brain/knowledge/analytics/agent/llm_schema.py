from __future__ import annotations

import json
import re
from typing import Any, Literal, TypeVar
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


AnalysisType = Literal["single_metric", "trend", "ranking", "comparison", "detail"]
VisualType = Literal["stat", "line", "bar", "table"]


class KeywordExpansion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list)
    reason: str = ""

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_keys(cls, value: Any) -> Any:
        if isinstance(value, dict) and "keywords" not in value:
            items = value.get("expanded_keywords") or []
            search_keywords = value.get("search_keywords") or {}
            if isinstance(search_keywords, dict):
                for group in search_keywords.values():
                    if isinstance(group, list):
                        items.extend(group)
            return {"keywords": items, "reason": value.get("reason") or ""}
        return value

    @field_validator("keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys([item.strip() for item in value if item and item.strip()]))[:24]


class IntentFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"] = "eq"
    value: Any
    label: str | None = None


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    endExclusive: str
    grain: Literal["day", "week", "month", "quarter", "year"] | None = None
    label: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_half_open_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "start" not in normalized and "startInclusive" in normalized:
            normalized["start"] = normalized["startInclusive"]
        if "end" not in normalized and "endExclusive" in normalized:
            try:
                normalized["end"] = (date.fromisoformat(str(normalized["endExclusive"])) - timedelta(days=1)).isoformat()
            except ValueError:
                normalized["end"] = normalized["endExclusive"]
        return {key: normalized[key] for key in ["start", "end", "endExclusive", "grain", "label"] if key in normalized}


class SortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    direction: Literal["asc", "desc"] = "desc"


class StructuredIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysisType: AnalysisType
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[IntentFilter] = Field(default_factory=list)
    timeRange: TimeRange | None = None
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=1000)
    visualHint: VisualType | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_nullable_lists(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in ["metrics", "dimensions", "filters", "sort"]:
            if normalized.get(key) is None:
                normalized[key] = []
        return normalized


class FilterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectedIds: list[str] = Field(default_factory=list)
    rejectedIds: list[str] = Field(default_factory=list)
    reason: str = ""

    @field_validator("selectedIds", "rejectedIds")
    @classmethod
    def _clean_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys([item.strip() for item in value if item and item.strip()]))


class SqlVisualPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: VisualType
    x: str | None = None
    y: list[str] = Field(default_factory=list)


class SqlPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str
    visual: SqlVisualPlan
    usedTables: list[str] = Field(default_factory=list)
    usedColumns: list[str] = Field(default_factory=list)
    usedMetrics: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "sql" not in normalized and "select_sql" in normalized:
            normalized["sql"] = normalized["select_sql"]
        if "usedTables" not in normalized and "used_tables" in normalized:
            normalized["usedTables"] = normalized["used_tables"]
        if "usedColumns" not in normalized and "used_columns" in normalized:
            normalized["usedColumns"] = normalized["used_columns"]
        if "usedMetrics" not in normalized and "used_metrics" in normalized:
            normalized["usedMetrics"] = normalized["used_metrics"]
        if "visual" not in normalized:
            normalized["visual"] = {"type": "table", "y": []}
        return {
            key: normalized[key]
            for key in ["sql", "visual", "usedTables", "usedColumns", "usedMetrics", "joins", "assumptions"]
            if key in normalized
        }


class SqlCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str
    changed: bool = False
    reason: str = ""
    usedTables: list[str] = Field(default_factory=list)
    usedColumns: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)


T = TypeVar("T", bound=BaseModel)


def extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    elif not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    return parsed


def parse_model(raw: str, model: type[T]) -> T:
    try:
        return model.model_validate(extract_json_object(raw))
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        raise ValueError(str(e)) from e
