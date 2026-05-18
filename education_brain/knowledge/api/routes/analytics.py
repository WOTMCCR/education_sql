from __future__ import annotations

from fastapi import APIRouter, Query

from knowledge.analytics.meta_store import get_counts_safe
from knowledge.analytics.search import search_columns, search_metrics, search_values
from knowledge.core.clients import (
    probe_analytics_elasticsearch,
    probe_analytics_embedding,
    probe_analytics_mysql,
    probe_analytics_qdrant,
)
from knowledge.core.config import get_settings

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _component(check) -> dict[str, str]:
    try:
        check(get_settings().health_check_timeout_seconds)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/health")
def analytics_health():
    components = {
        "mysql_meta": _component(probe_analytics_mysql),
        "qdrant": _component(probe_analytics_qdrant),
        "elasticsearch": _component(probe_analytics_elasticsearch),
        "embedding": _component(probe_analytics_embedding),
    }
    try:
        counts = get_counts_safe()
    except Exception as e:
        counts = {"tables": 0, "columns": 0, "metrics": 0, "joins": 0, "dimensions": 0}
        components["mysql_meta"] = {"status": "error", "error": str(e)}
    all_ok = all(c.get("status") == "ok" for c in components.values())
    any_ok = any(c.get("status") == "ok" for c in components.values())
    status = "healthy" if all_ok else "degraded" if any_ok else "unhealthy"
    return {
        "status": status,
        **components,
        "counts": counts,
    }


@router.get("/meta/metrics")
def analytics_meta_metrics(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=50)):
    return {"items": search_metrics(q, limit)}


@router.get("/meta/columns")
def analytics_meta_columns(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=50)):
    return {"items": search_columns(q, limit)}


@router.get("/meta/values")
def analytics_meta_values(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=50)):
    return {"items": search_values(q, limit)}
