# knowledge/processor/document_store.py
"""文档 MongoDB 写入 — 对应 PLAN.md §6.4 步骤 3e"""

import logging
from pymongo.database import Database

from knowledge.models.document import KnowledgeDocument, KnowledgeChunk, SourceMapping

logger = logging.getLogger(__name__)

def save_document(
    db: Database,
    doc: KnowledgeDocument,
    chunks: list[KnowledgeChunk],
)->int:
    """
    将文档元数据和分块结果写入 MongoDB。

    写入策略(PLAN.md §6.4 步骤 3e):
      先写 knowledge_document(文件级元数据)
      再批量写 knowledge_chunk(分块结果)
      按 doc_id 做 upsert, 重复导入先删除旧 chunk 再写入新 chunk。

    为什么先删旧 chunk 再写新 chunk(而不是逐个 upsert)
      文档重新导入后，分块数量和 chunk_id 都会变化。
      如果用 upsert , 旧的 chunk(新版本不再存在的)不会被删除，
      导致数据库中残留"幽灵 chunk"。
      先删后写保证数据库中只有最新版本的 chunk。

    返回：写入的 chunk 数量
    """
    col_doc = db["knowledge_document"]
    col_chunk = db["knowledge_chunk"]

    # upsert 文档元数据
    col_doc.update_one(
        {"doc_id": doc.doc_id},
        {"$set": doc.model_dump()},
        upsert=True,
    )

    # 删除旧 chunk → 写入新 chunk
    col_chunk.delete_many({"doc_id": doc.doc_id})
    if chunks:
        col_chunk.insert_many([c.model_dump() for c in chunks])

    # 建索引（幂等）
    col_doc.create_index("doc_id", unique=True)
    col_doc.create_index("doc_type")

    col_chunk.create_index("chunk_id", unique=True)
    col_chunk.create_index("doc_id")

    logger.info(
        "MongoDB 写入完成: doc_id=%s, %d chunks",
        doc.doc_id, len(chunks),
    )
    return len(chunks)

def save_source_mapping(db : Database , mapping : SourceMapping) -> None:
    """
    写入来源映射记录。

    按 (source_file, doc_id) 做 upsert。
    mapping_type="rule" 的记录可以被 mapping_type="manual" 覆盖。
    """
    col = db["source_mapping"]
    filter_key = {"source_file": mapping.source_file}
    if mapping.doc_id:
        filter_key["doc_id"] = mapping.doc_id

    col.update_one(
        filter_key,
        {"$set": mapping.model_dump()},
        upsert=True,
    )
    col.create_index("source_file")
    col.create_index("doc_id")

