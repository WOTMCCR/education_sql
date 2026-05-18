# knowledge/core/clients.py
"""
所有外部客户端的统一入口

线程安全策略:

- 无状态 HTTP 客户端 (OpenAI, MinIO): @cache
  底层是 C 实现的 dict 查找，线程安全；最坏并发多创建一次，无副作用

- 有状态连接 (MongoDB): @cache
  pymongo.MongoClient 内部自带连接池，多创建一次浪费但不会出错，@cache 足够

- 重量级资源 (Milvus gRPC, BGE GPU 模型): Lock + 二次检查
  内部维护连接池或 GPU 显存，重复创建浪费资源，必须严格单例
"""

import logging
import os
import threading
from functools import cache
from urllib.parse import urlparse

import httpx
import pymysql
import torch
import urllib3
from elasticsearch import Elasticsearch
from minio import Minio
from openai import AsyncOpenAI, OpenAI
from pymilvus import MilvusClient
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


@cache
def get_minio() -> Minio:
    """MinIO 对象存储客户端"""
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


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


def ensure_minio_bucket() -> None:
    """确保 MinIO bucket 存在，导入流程启动时调用一次"""
    s = get_settings()
    client = get_minio()
    if not client.bucket_exists(s.minio_bucket):
        client.make_bucket(s.minio_bucket)


def _build_milvus_client(timeout: float | None = None) -> MilvusClient:
    s = get_settings()
    kwargs = {
        "uri": s.milvus_uri,
        "user": s.milvus_user,
        "password": s.milvus_password,
        "db_name": s.milvus_db_name,
        "token": s.effective_milvus_token,
        "timeout": timeout,
    }
    return MilvusClient(**kwargs)

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


def probe_milvus(timeout_seconds: float) -> None:
    client = _build_milvus_client(timeout=timeout_seconds)
    client.list_collections(timeout=timeout_seconds) # type: ignore


def probe_minio(timeout_seconds: float) -> None:
    s = get_settings()
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds),
        retries=urllib3.Retry(total=0, connect=0, read=0, redirect=0, status=0),
    )
    client = Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
        http_client=http_client,
    )
    client.bucket_exists(s.minio_bucket)


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 重量级资源 — Lock + 二次检查
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_milvus_lock = threading.Lock()
_milvus_client = None

def get_milvus():
    """Milvus 客户端 — 维护 gRPC channel，严格单例"""
    global _milvus_client
    if _milvus_client is not None:
        return _milvus_client

    with _milvus_lock:
        if _milvus_client is None:
            _milvus_client = _build_milvus_client()
    return _milvus_client


_bge_m3_lock = threading.Lock()
_bge_m3_client = None
_bge_m3_infer_lock = threading.Lock()


def _resolve_bge_runtime(*, device: str, use_fp16: bool) -> tuple[str, bool]:
    """统一解析 BGE 运行时设备。

    当前环境无 CUDA 时自动降级到 CPU，并关闭 fp16。
    """
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("BGE_DEVICE=cuda 但当前环境无可用 CUDA，自动回退到 CPU")
        return "cpu", False

    if device == "cpu":
        return "cpu", False

    return device, use_fp16

def get_bge_m3():
    """BGE-M3 嵌入模型 — 加载 ~2.2GB 到 GPU，严格单例"""
    global _bge_m3_client
    if _bge_m3_client is not None:
        return _bge_m3_client
    
    with _bge_m3_lock:
        if _bge_m3_client is None:
            from pymilvus.model.hybrid import BGEM3EmbeddingFunction
            s = get_settings()
            device, use_fp16 = _resolve_bge_runtime(
                device=s.bge_device,
                use_fp16=s.bge_fp16,
            )
            _bge_m3_client = BGEM3EmbeddingFunction(
                model_name=s.bge_m3_path,
                device=device,
                use_fp16=use_fp16,
            )
    return _bge_m3_client


def encode_bge_queries(texts: list[str]):
    """串行执行 BGE-M3 query 编码，避免并发访问同一模型实例。"""
    model = get_bge_m3()
    with _bge_m3_infer_lock:
        return model.encode_queries(texts)


def encode_bge_documents(texts: list[str]):
    """串行执行 BGE-M3 document 编码，避免并发访问同一模型实例。"""
    model = get_bge_m3()
    with _bge_m3_infer_lock:
        return model(texts)


_bge_reranker_lock = threading.Lock()
_bge_reranker_client = None


def get_bge_reranker():
    """BGE Reranker — 加载 ~2.2GB 到 GPU，严格单例"""
    global _bge_reranker_client
    if _bge_reranker_client is not None:
        return _bge_reranker_client

    with _bge_reranker_lock:
        if _bge_reranker_client is None:
            from pymilvus.model.reranker import BGERerankFunction
            s = get_settings()
            device, use_fp16 = _resolve_bge_runtime(
                device=s.bge_device,
                use_fp16=s.bge_fp16,
            )
            _bge_reranker_client = BGERerankFunction(
                model_name=s.bge_reranker_path,
                device=device,
                use_fp16=use_fp16,
            )
    return _bge_reranker_client
