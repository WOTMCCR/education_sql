from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    start: str
    endExclusive: str
    label: str


class ComparisonSpec(BaseModel):
    kind: Literal["none", "time_period", "entity"] = "none"
    mode: str = ""
    current: TimeWindow | None = None
    baseline: TimeWindow | None = None
    dimension: str = ""
    field: str = ""
    values: list[str] = Field(default_factory=list)
    label: str = ""


class MetricRequest(BaseModel):
    id: str
    name: str
    expression: str
    base_table: str
    value_alias: str
    time_column: str | None = None
    unit: str | None = None
    default_filters: list[str] = Field(default_factory=list)


class DimensionRequest(BaseModel):
    id: str
    name: str
    field: str
    table_name: str
    column_name: str
    alias: str


class FilterRequest(BaseModel):
    field: str
    op: Literal["eq", "in"] = "eq"
    value: Any
    label: str = ""


class JoinPlan(BaseModel):
    base_table: str
    target_tables: list[str] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    metric: MetricRequest
    dimensions: list[DimensionRequest] = Field(default_factory=list)
    filters: list[FilterRequest] = Field(default_factory=list)
    comparison: ComparisonSpec | None = None
    join_plan: JoinPlan
    time_range: TimeWindow | None = None
    output_shape: Literal["stat", "table", "bar", "line", "comparison"] = "table"
    limit: int = Field(default=50, ge=1, le=1000)
