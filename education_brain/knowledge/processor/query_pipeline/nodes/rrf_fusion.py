"""RRF 融合节点 — 对应 PLAN.md §7.5.4

Reciprocal Rank Fusion:
  RRF_score(doc) = Σ 1 / (k + rank_i(doc))

基于排名而非分数的融合算法。
两路检索的相似度分数尺度不同，不能直接相加。
RRF 只看排名，天然对不同度量尺度鲁棒。
"""

import logging

from knowledge.core.config import get_settings
from knowledge.processor.query_pipeline.state import QueryGraphState

logger = logging.getLogger(__name__)

def rrf_fusion(state: QueryGraphState) -> dict:
    """LangGraph 节点: RRF 融合向量检索 + HyDE 检索结果"""
    vector_chunks = state.get("embedding_chunks") or []
    hyde_chunks = state.get("hyde_chunks") or []

    if not vector_chunks and not hyde_chunks:
        logger.warning("两路检索均为空, RRF 跳过")
        return {"rrf_chunks": []}
    
    s = get_settings()

    sources = {
        "vector": (vector_chunks, 1.0),
        "hyde": (hyde_chunks, 1.0),
    }
    
    merged = _rrf_merge(sources, k=s.rrf_k, top_k=s.rrf_max_results)

    logger.info(
        "RRF 融合: vector=%d, hyde=%d → %d",
        len(vector_chunks), len(hyde_chunks), len(merged),
    )
    return {"rrf_chunks": merged}

def _rrf_merge(
    sources: dict[str, tuple[list[dict], float]],
    *,
    k: int = 60,
    top_k: int = 10,
) -> list[dict]:
    """执行 RRF 融合

    同一个 chunk_id 在多路检索中出现 → 分数叠加（共识奖励）。
    只出现在一路中的 chunk 也会被保留，但分数较低。
    """
    chunk_scores: dict[str, float] = {}
    chunk_data: dict[str, dict] = {}

    for source_name, (docs, weight) in sources.items():
        for rank, doc in enumerate(docs, start=1):
            chunk_id = doc.get("chunk_id")
            if not chunk_id:
                continue

            chunk_scores[chunk_id] = (
                chunk_scores.get(chunk_id, 0.0) + weight / (k + rank)
            )
            chunk_data.setdefault(chunk_id, doc)

    sorted_ids = sorted(chunk_scores, key=chunk_scores.get, reverse=True)
    return [chunk_data[cid] for cid in sorted_ids[:top_k]]