"""向量检索节点 — 对应 PLAN.md §7.5.2

复用 service/document_search.py 的 encode_query 和
processor/milvus_store.py 的 hybrid_search。
"""

import logging

from knowledge.processor.query_pipeline.state import QueryGraphState
from knowledge.service.document_search import encode_query
from knowledge.processor.milvus_store import hybrid_search

logger = logging.getLogger(__name__)


def vector_search(state: QueryGraphState) -> dict:
    """LangGraph 节点：稠密+稀疏混合向量检索"""
    query = state.get("rewritten_query") or state.get("original_query", "")
    if not query:
        return {"embedding_chunks": []}

    from knowledge.core.config import get_settings
    s = get_settings()

    dense, sparse = encode_query(query)

    hits = hybrid_search(
        dense, sparse,
        limit=s.query_search_limit,
    )

    logger.info("向量检索: %d 条命中", len(hits))
    return {"embedding_chunks": hits}