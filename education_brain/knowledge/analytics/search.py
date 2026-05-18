from __future__ import annotations

from typing import Any

import httpx
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient

from knowledge.analytics.meta_store import embed_texts, mysql_like_search
from knowledge.core.config import get_settings


def _score(result: Any) -> float:
    value = getattr(result, "score", None)
    return float(value if value is not None else 0)


def _payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "payload", None)
    return dict(payload or {})


def search_qdrant(collection_name: str, query: str, limit: int) -> list[dict[str, Any]]:
    s = get_settings()
    vector = embed_texts([query])[0]
    client = QdrantClient(url=s.analytics_qdrant_url, timeout=s.analytics_qdrant_timeout_seconds, trust_env=False)
    response = client.query_points(
        collection_name=collection_name,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    points = getattr(response, "points", response)
    items: list[dict[str, Any]] = []
    for point in points:
        payload = _payload(point)
        payload["score"] = _score(point)
        items.append(payload)
    return items


def search_metrics(query: str, limit: int) -> list[dict[str, Any]]:
    s = get_settings()
    try:
        items = search_qdrant(s.analytics_qdrant_metric_collection, query, limit)
    except Exception:
        return mysql_like_search("metrics", query, limit)
    return [
        {
            "id": item.get("metric_id") or item.get("id"),
            "metric_id": item.get("metric_id") or item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "score": item.get("score", 0),
        }
        for item in items
    ]


def search_columns(query: str, limit: int) -> list[dict[str, Any]]:
    s = get_settings()
    try:
        items = search_qdrant(s.analytics_qdrant_column_collection, query, limit)
    except Exception:
        return mysql_like_search("columns", query, limit)
    return [
        {
            "id": item.get("full_name") or item.get("id"),
            "full_name": item.get("full_name") or item.get("id"),
            "table_name": item.get("table_name"),
            "column_name": item.get("column_name"),
            "description": item.get("description"),
            "score": item.get("score", 0),
        }
        for item in items
    ]


def search_values(query: str, limit: int) -> list[dict[str, Any]]:
    s = get_settings()
    client = Elasticsearch(s.analytics_es_url, request_timeout=s.analytics_es_timeout_seconds)
    try:
        response = client.search(
            index=s.analytics_es_dimension_values_index,
            size=limit,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["value^3", "code", "field"],
                }
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        return [
            {
                "field": hit.get("_source", {}).get("field"),
                "value": hit.get("_source", {}).get("value"),
                "score": hit.get("_score", 0),
                "dimension_id": hit.get("_source", {}).get("dimension_id"),
                "value_id": hit.get("_source", {}).get("value_id"),
                "code": hit.get("_source", {}).get("code"),
            }
            for hit in hits
        ]
    except Exception:
        return []
    finally:
        client.close()


def probe_embedding_query() -> None:
    s = get_settings()
    with httpx.Client(base_url=s.analytics_embedding_url, timeout=s.analytics_embedding_timeout_seconds, trust_env=False) as client:
        response = client.post("/embed", json={"inputs": ["收入"]})
        response.raise_for_status()
