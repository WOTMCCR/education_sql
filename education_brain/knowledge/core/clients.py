# knowledge/core/clients.py
"""
所有外部客户端的统一入口

线程安全策略:

- 无状态 HTTP 客户端 (OpenAI): @cache
  底层是 C 实现的 dict 查找，线程安全；最坏并发多创建一次，无副作用

- 有状态连接 (MongoDB): @cache
  pymongo.MongoClient 内部自带连接池，多创建一次浪费但不会出错，@cache 足够
"""

import logging
import os
from functools import cache
from urllib.parse import urlparse

import httpx
import pymysql
from elasticsearch import Elasticsearch
from openai import AsyncOpenAI, OpenAI
from pymongo import MongoClient
from pymongo.database import Database
from qdrant_client import QdrantClient

from knowledge.core.config import get_settings

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 无状态 / 自带连接池的客户端 — @cache 即可
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@cache
def get_openai() -> OpenAI:
    """OpenAI 兼容客户端（官方 API / Ollama / vLLM / 其他）"""
    s = get_settings()
    hostname = (urlparse(s.openai_base_url).hostname or "").lower() if s.openai_base_url else ""
    is_local = hostname in {"localhost", "127.0.0.1", "0.0.0.0"}
    timeout = httpx.Timeout(s.openai_timeout_seconds)

    kwargs: dict = {
        "api_key": s.openai_api_key,
        "max_retries": 0,
    }
    if s.openai_base_url:
        kwargs["base_url"] = s.openai_base_url

    if is_local:
        kwargs["http_client"] = httpx.Client(
            trust_env=False,
            timeout=timeout,
        )
    else:
        proxy_url = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
        proxy_kw = {"proxy": proxy_url} if proxy_url else {}
        kwargs["http_client"] = httpx.Client(
            trust_env=False, timeout=timeout, **proxy_kw,
        )

    return OpenAI(**kwargs)

@cache
def get_async_openai()->AsyncOpenAI:
    """异步 OpenAI 兼容客户端 - 用于流式输出场景

    与 get_openai() 使用相同的配置，但返回 AsyncOpenAI 实例。
    AsyncOpenAI 内部使用 httpx.AsyncClient,
    可以在 async for 中逐 chunk 消费 SSE 流而不阻塞事件循环.
    """
    s = get_settings()
    hostname = (urlparse(s.openai_base_url).hostname or "").lower() if s.openai_base_url else ""
    is_local = hostname in {"localhost", "127.0.0.1", "0.0.0.0"}
    timeout = httpx.Timeout(s.answer_timeout_seconds)  # 流式场景用更长超时

    kwargs : dict = {
        "api_key": s.openai_api_key,
        "max_retries": 0,
    }
    if s.openai_base_url:
        kwargs["base_url"] = s.openai_base_url

    if is_local:
        import httpx as _httpx
        kwargs["http_client"] = _httpx.AsyncClient(
            trust_env=False,
            timeout=timeout,
        )
    else:
        import httpx as _httpx
        proxy_url = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
        proxy_kw = {"proxy": proxy_url} if proxy_url else {}
        kwargs["http_client"] = _httpx.AsyncClient(
            trust_env=False, timeout=timeout, **proxy_kw,
        )

    return AsyncOpenAI(**kwargs)


@cache
def get_mongo_client() -> MongoClient:
    """MongoDB 客户端（内部自带连接池）"""
    return MongoClient(get_settings().mongo_uri)


@cache
def get_mongo_db() -> Database:
    """MongoDB 数据库实例 — 大多数调用方需要的是 db 而非 client"""
    s = get_settings()
    return get_mongo_client()[s.mongo_db]


def get_analytics_mysql_connection():
    """教育问数 MySQL 连接。

    PyMySQL connection 是有状态对象，不在这里做全局缓存；调用方负责 close。
    """
    s = get_settings()
    return pymysql.connect(
        **s.analytics_mysql_connect_kwargs,
        connect_timeout=s.analytics_mysql_timeout_seconds,
        read_timeout=s.analytics_mysql_timeout_seconds,
        write_timeout=s.analytics_mysql_timeout_seconds,
    )


@cache
def get_analytics_qdrant_client() -> QdrantClient:
    """教育问数 Qdrant 客户端。"""
    s = get_settings()
    return QdrantClient(
        url=s.analytics_qdrant_url,
        timeout=s.analytics_qdrant_timeout_seconds,
        trust_env=False,
    )


@cache
def get_analytics_elasticsearch_client() -> Elasticsearch:
    """教育问数 Elasticsearch 客户端。"""
    s = get_settings()
    return Elasticsearch(
        s.analytics_es_url,
        request_timeout=s.analytics_es_timeout_seconds,
    )


def get_analytics_qdrant() -> QdrantClient:
    """兼容现有 get_* 简写命名的 Qdrant 客户端入口。"""
    return get_analytics_qdrant_client()


def get_analytics_elasticsearch() -> Elasticsearch:
    """兼容现有 get_* 简写命名的 Elasticsearch 客户端入口。"""
    return get_analytics_elasticsearch_client()


@cache
def get_analytics_embedding_client() -> httpx.Client:
    """教育问数 Embedding HTTP 客户端。"""
    s = get_settings()
    return httpx.Client(
        base_url=s.analytics_embedding_url,
        timeout=httpx.Timeout(s.analytics_embedding_timeout_seconds),
        trust_env=False,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 健康探针
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def probe_mongodb(timeout_seconds: float) -> None:
    s = get_settings()
    timeout_ms = max(1, int(timeout_seconds * 1000))
    client = MongoClient(
        s.mongo_uri,
        serverSelectionTimeoutMS=timeout_ms,
        connectTimeoutMS=timeout_ms,
        socketTimeoutMS=timeout_ms,
    )
    client.admin.command("ping")


def probe_analytics_mysql(timeout_seconds: float | None = None) -> None:
    s = get_settings()
    timeout = timeout_seconds or s.analytics_mysql_timeout_seconds
    connection = pymysql.connect(
        **s.analytics_mysql_connect_kwargs,
        connect_timeout=timeout,
        read_timeout=timeout,
        write_timeout=timeout,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    finally:
        connection.close()


def probe_analytics_qdrant(timeout_seconds: float | None = None) -> None:
    s = get_settings()
    client = QdrantClient(
        url=s.analytics_qdrant_url,
        timeout=timeout_seconds or s.analytics_qdrant_timeout_seconds,
        trust_env=False,
    )
    try:
        client.get_collections()
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def probe_analytics_elasticsearch(timeout_seconds: float | None = None) -> None:
    s = get_settings()
    client = Elasticsearch(
        s.analytics_es_url,
        request_timeout=timeout_seconds or s.analytics_es_timeout_seconds,
    )
    try:
        client.info()
    finally:
        client.close()


def probe_analytics_embedding(timeout_seconds: float | None = None) -> None:
    s = get_settings()
    timeout = httpx.Timeout(timeout_seconds or s.analytics_embedding_timeout_seconds)
    with httpx.Client(
        base_url=s.analytics_embedding_url,
        timeout=timeout,
        trust_env=False,
    ) as client:
        response = client.get("/health")
        if response.status_code in {404, 405}:
            response = client.post("/embed", json={"inputs": ["ping"]})
        response.raise_for_status()


def probe_analytics_dependencies(timeout_seconds: float | None = None) -> dict[str, str]:
    """运行教育问数四类依赖探针，供后续 analytics health route 复用。"""
    probes = {
        "mysql": probe_analytics_mysql,
        "qdrant": probe_analytics_qdrant,
        "elasticsearch": probe_analytics_elasticsearch,
        "embedding": probe_analytics_embedding,
    }
    results: dict[str, str] = {}
    for name, probe in probes.items():
        try:
            probe(timeout_seconds)
            results[name] = "ok"
        except Exception as e:
            results[name] = f"error: {e}"
    return results
