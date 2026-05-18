"""
文档向量检索服务 — 对应 PLAN.md §7 Step 7

三步流程：
  1. 查询编码:BGE-M3 encode_queries → dense + sparse
  2. Milvus 混合检索:WeightedRanker 融合 dense + sparse
  3. MongoDB 回表:chunk_id → 完整文本 + 文档元数据 + 来源映射

设计为独立 service 函数, Step 7 由 API 直接调用，
Step 8 由 LangGraph 节点复用 encode_query() 和 hybrid_search()。
"""

import logging

from knowledge.core.clients import encode_bge_queries, get_mongo_db
from knowledge.processor.embedder import csr_row_to_sparse_dict
from knowledge.processor.milvus_store import hybrid_search

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 查询编码
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def encode_query(text: str) -> tuple[list[float], dict[int, float]]:
    """用 BGE-M3 编码查询文本，返回 (dense_vector, sparse_dict)

    使用 encode_queries() 而非 encode_documents():
    查询编码会添加特殊前缀，让模型理解「这是一个搜索意图」，
    与导入时的文档编码语义配对，提升检索精度。
    """
    result = encode_bge_queries([text])

    dense = result["dense"][0]
    dense_list = dense.tolist() if hasattr(dense, "tolist") else list(dense)

    sparse = csr_row_to_sparse_dict(result["sparse"], row=0)

    return dense_list , sparse

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: MongoDB 回表 + 来源组装
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def lookback_and_assemble(hits: list[dict]) -> list[dict]:
    """用 Milvus 返回的 chunk_id 回 MongoDB 取完整信息

    三张表批量查询：
    1. knowledge_chunk  → chunk_text, section_path, chunk_kind
    2. knowledge_document → title, source_file, doc_type
    3. source_mapping → series_code, project_name（文档与课程的关联）

    批量查询而非逐条：避免 N+1 查询问题。
    """
    if not hits:
        return []

    db = get_mongo_db()

    chunk_ids = [h["chunk_id"] for h in hits]
    doc_ids = list({h["doc_id"] for h in hits})

    # 批量查 chunk 全文
    chunk_map: dict[str, dict] = {}
    for doc in db["knowledge_chunk"].find(
        {"chunk_id": {"$in": chunk_ids}},
        {"_id": 0},
    ):
        chunk_map[doc["chunk_id"]] = doc

    # 批量查文档元数据
    doc_map: dict[str, dict] = {}
    for doc in db["knowledge_document"].find(
        {"doc_id": {"$in": doc_ids}},
        {"_id": 0},
    ):
        doc_map[doc["doc_id"]] = doc

    # 批量查来源映射
    source_files = [
        doc_map[did].get("source_file", "")
        for did in doc_ids
        if did in doc_map
    ]
    mapping_map: dict[str, dict] = {}
    if source_files:
        for doc in db["source_mapping"].find(
            {"source_file": {"$in": source_files}},
            {"_id": 0},
        ):
            mapping_map[doc.get("source_file", "")] = doc
    
    # 组装结果——保持 Milvus 返回的排序（按相关性降序）
    results = []
    for hit in hits:
        cid = hit["chunk_id"]
        did = hit["doc_id"]

        chunk = chunk_map.get(cid, {})
        doc_meta = doc_map.get(did, {})
        source_file = doc_meta.get("source_file", "")
        mapping = mapping_map.get(source_file, {})

        results.append({
            # 检索信息
            "distance": hit["distance"],
            # chunk 内容
            "chunk_id": cid,
            "chunk_text": chunk.get("chunk_text", ""),
            "section_path": chunk.get("section_path", []),
            "chunk_kind": chunk.get("chunk_kind", "text"),
            "chunk_index": chunk.get("chunk_index", 0),
            # 文档信息
            "doc_id": did,
            "doc_type": hit.get("doc_type", ""),
            "doc_title": doc_meta.get("title", ""),
            "source_file": source_file,
            # 来源映射
            "series_code": mapping.get("series_code", ""),
            "project_name": mapping.get("project_name", ""),
            "mapping_type": mapping.get("mapping_type", ""),
        })

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 对外接口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_documents(
    query: str,
    doc_type: str = "",
    limit: int = 5,
) -> list[dict]:
    """文档向量检索完整流程：编码 → 搜索 → 回表

    参数：
        query:    用户搜索文本
        doc_type: 可选过滤，"course_doc" | "project_doc" | ""（全部）
        limit:    返回结果数量上限

    返回：
        按相关性降序排列的文档片段列表，每条包含：
        - chunk 全文和位置信息（section_path）
        - 文档元数据（标题、文件名）
        - 来源映射（关联的课程系列或项目名称）
    """
    # 1. 查询编码
    dense, sparse = encode_query(query)

    # 2. Milvus 混合检索
    hits = hybrid_search(dense, sparse, doc_type=doc_type, limit=limit)

    if not hits:
        logger.info("文档检索无结果: query=%r, doc_type=%r", query, doc_type)
        return []

    # 3. MongoDB 回表 + 组装
    results = lookback_and_assemble(hits)

    logger.info(
        "文档检索完成: query=%r, %d 条结果",
        query[:50], len(results),
    )
    return results
