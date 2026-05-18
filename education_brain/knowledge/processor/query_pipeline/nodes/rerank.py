"""Rerank 精排节点 — 对应 PLAN.md §7.5.5

两步操作：
1. MongoDB 回表取 chunk 全文(Milvus 只存向量，不存文本)
2. 交叉编码器逐对打分 + 悬崖截断

悬崖截断：不用固定 TopK , 而是检测分数断崖 , 动态保留。
"""

import logging

from knowledge.core.clients import get_bge_reranker
from knowledge.core.config import get_settings
from knowledge.processor.query_pipeline.state import QueryGraphState
from knowledge.service.document_search import lookback_and_assemble

logger = logging.getLogger(__name__)

def rerank(state: QueryGraphState) -> dict:
    """LangGraph 节点：回表 + 交叉编码器精排 + 悬崖截断"""
    query = state.get("rewritten_query") or state.get("original_query", "")
    rrf_chunks = state.get("rrf_chunks") or []

    if not rrf_chunks:
        return {"final_chunks": []}

    # 1. MongoDB 回表：chunk_id → 完整文本 + 文档元数据 + 来源映射
    enriched = lookback_and_assemble(rrf_chunks)
    if not enriched:
        return {"final_chunks": []}

    s = get_settings()
    if not s.enable_rerank:
        logger.info("Rerank 已禁用，直接使用 RRF 结果")
        return {"final_chunks": enriched}
    
    # 2. 交叉编码器打分
    try:
        scored = _rerank_docs(query, enriched)
    except Exception as e:
        logger.warning("Reranker 失败，使用 RRF 排序: %s", e)
        return {"final_chunks": enriched}
    
    # 3. 悬崖截断
    final = _cliff_cutoff(scored, s)

    logger.info("Rerank: %d 候选 → %d 精排 → %d 最终", len(rrf_chunks), len(scored), len(final))
    return {"final_chunks": final}

def _rerank_docs(query: str, docs: list[dict]) -> list[dict]:
    """用交叉编码器为每个文档打分，按分数降序排列"""
    reranker = get_bge_reranker()

    texts = [d.get("chunk_text", "") for d in docs]
    if not any(texts):
        return docs
    
    results = reranker(query, texts, top_k=len(texts))

    # BGERerankFunction 返回 RerankResult 列表（按 score 降序）
    # 每个 result 有 .index（原始位置）和 .score
    scored = []
    for r in results:
        doc = docs[r.index].copy()
        doc["rerank_score"] = float(r.score)
        scored.append(doc)
    
    return scored


def _cliff_cutoff(ranked_docs: list[dict], settings) -> list[dict]:
    """悬崖截断 — 在 [min, max] 范围内找最大分数断崖

    示例：scores = [0.95, 0.92, 0.88, 0.12, 0.08]
    gaps:               0.03   0.04   0.76   0.04
    → 0.76 是最大断崖 → 保留前 3 条
    """
    if not ranked_docs:
        return []
    
    upper = min(settings.rerank_max_top_k, len(ranked_docs))
    lower = min(settings.rerank_min_top_k, upper)

    if upper <= lower:
        return ranked_docs[:upper]
    
    max_gap = 0.8
    cutoff_pos = upper

    for i in range(lower - 1, upper - 1):
        current = ranked_docs[i].get("rerank_score")
        next_val = ranked_docs[i + 1].get("rerank_score")
        if current is None or next_val is None:
            continue

        abs_gap = current - next_val
        should_cut = abs_gap >= settings.rerank_gap_abs

        if not should_cut and abs(current) > 1.0:
            rel_gap = abs_gap / (abs(current) + 1e-6)
            if rel_gap >= settings.rerank_gap_ratio:
                should_cut = True

        if should_cut and abs_gap > max_gap:
            max_gap = abs_gap
            cutoff_pos = i + 1
        
    result = ranked_docs[:cutoff_pos]

    if settings.rerank_min_score is not None:
        filtered = [d for d in result if d.get("rerank_score", 0) >= settings.rerank_min_score]
        if len(filtered) >= lower:
            result = filtered

    return result
