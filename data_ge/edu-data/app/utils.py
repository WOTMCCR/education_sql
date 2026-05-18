"""Utility helpers for API handlers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def offset_limit(page_no: int, page_size: int) -> tuple[int, int]:
    normalized_page_no = max(page_no, 1)
    normalized_page_size = max(min(page_size, 100), 1)
    return (normalized_page_no - 1) * normalized_page_size, normalized_page_size


def format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None


def format_date(value: date | None) -> str | None:
    return value.strftime("%Y-%m-%d") if value is not None else None


def format_time(value: time | timedelta | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return value.strftime("%H:%M:%S")


def money(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(Decimal(str(value)))


def parse_datetime(value: str, field_name: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"{field_name} 格式必须为 YYYY-MM-DD HH:mm:ss")


def make_no(prefix: str) -> str:
    return f"{prefix}{local_now().strftime('%Y%m%d%H%M%S%f')}"


def json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        if not value:
            return []
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return list(value)


def count_total(sql: str, params: Any | None = None) -> int:
    from .database import fetch_one

    row = fetch_one(sql, params)
    if row is None or row["total"] is None:
        return 0
    return int(row["total"])
