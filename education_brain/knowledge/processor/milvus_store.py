# knowledge/processor/milvus_store.py
"""
Milvus 向量存储 — 对应 PLAN.md §4.2 / §6.4 步骤 5

职责：
  1. 创建/确保 Collection 存在(schema + 索引)
  2. 写入向量数据(upsert)
  3. 按 doc_id 删除(文档重新导入时清理旧向量)
"""
import logging
from pymilvus import (
    AnnSearchRequest,
    DataType,
    MilvusClient,
    WeightedRanker,
)

from knowledge.core.clients import get_milvus
from knowledge.core.config import get_settings
from knowledge.core.errors import StorageError
from knowledge.processor.embedder import EmbeddingRecord

logger = logging.getLogger(__name__)

def ensure_collection() -> None:
    """
    确保 Milvus collection 存在，不存在则创建。

    Schema(对齐 PLAN.md §4.2):
      chunk_id       VARCHAR(64)         主键
      doc_id         VARCHAR(64)         过滤字段
      doc_type       VARCHAR(32)         过滤字段
      dense_vector   FLOAT_VECTOR(1024)  BGE-M3 稠密向量
      sparse_vector  SPARSE_FLOAT_VECTOR BGE-M3 稀疏向量

    索引：
      dense_vector  → HNSW (IP)
      sparse_vector → SPARSE_INVERTED_INDEX (IP)
    """

    s = get_settings()
    client: MilvusClient = get_milvus()
    col_name = s.milvus_collection

    # 已存在则跳过
    if client.has_collection(col_name):
        client.load_collection(col_name)
        logger.info("Milvus collection 已存在: %s", col_name)
        return
    
    # 定义 schema
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)

    schema.add_field("chunk_id", DataType.VARCHAR, max_length=64, is_primary=True)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
    schema.add_field("doc_type", DataType.VARCHAR, max_length=32)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=s.embedding_dim)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)

    # 创建 collection
    client.create_collection(
        collection_name=col_name,
        schema=schema,
    )

    # 创建索引
    index_params = client.prepare_index_params()

    index_params.add_index(
        field_name="dense_vector",
        index_type="HNSW",
        metric_type="IP",  # Inner Product，BGE-M3 输出的向量已归一化
        params={"M": 16, "efConstruction": 256},
    )

    index_params.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="IP",
    )

    client.create_index(
        collection_name=col_name,
        index_params=index_params,
    )
    client.load_collection(col_name)

    logger.info(
        "Milvus collection 创建完成: %s (dim=%d)",
        col_name, s.embedding_dim,
    )


def upsert_vectors(records: list[EmbeddingRecord]) -> int:
    """
    将向量数据写入 Milvus。

    参数：
        records: EmbeddingRecord 列表（embedder 的输出）

    返回：
        成功写入的记录数

    写入策略：
        使用 upsert，chunk_id 相同的记录会被覆盖。
    """
    if not records:
        return 0

    s = get_settings()
    client: MilvusClient = get_milvus()
    col_name = s.milvus_collection

    data = [
        {
            "chunk_id": r.chunk_id,
            "doc_id": r.doc_id,
            "doc_type": r.doc_type,
            "dense_vector": r.dense_vector,
            "sparse_vector": r.sparse_vector,
        }
        for r in records
    ]

    try:
        result = client.upsert(
            collection_name=col_name,
            data=data,
        )
    except Exception as e:
        raise StorageError(
            message="Milvus 写入失败",
            detail=str(e),
        ) from e

    count = result.get("upsert_count", len(records))
    logger.info("Milvus 写入完成: %d 条记录", count)
    return count


def hybrid_search(
    dense: list[float],
    sparse: dict[int, float],
    *,
    doc_type: str = "",
    limit: int = 5,
) -> list[dict]:
    """执行 Milvus 混合检索，返回统一的命中结果结构。"""
    s = get_settings()
    client: MilvusClient = get_milvus()
    col_name = s.milvus_collection

    if not client.has_collection(col_name):
        logger.info("Milvus collection 不存在，跳过检索: %s", col_name)
        return []

    try:
        client.load_collection(col_name)

        filter_expr = f'doc_type == "{doc_type}"' if doc_type else None

        dense_req = AnnSearchRequest(
            data=[dense],
            anns_field="dense_vector",
            param={"metric_type": "IP"},
            limit=limit,
            expr=filter_expr,
        )

        reqs = [dense_req]
        weights = [s.query_dense_weight]

        if sparse:
            sparse_req = AnnSearchRequest(
                data=[sparse],
                anns_field="sparse_vector",
                param={"metric_type": "IP"},
                limit=limit,
                expr=filter_expr,
            )
            reqs.append(sparse_req)
            weights.append(s.query_sparse_weight)

        raw = client.hybrid_search(
            collection_name=col_name,
            reqs=reqs,
            ranker=WeightedRanker(*weights),
            limit=limit,
            output_fields=["chunk_id", "doc_id", "doc_type"],
        )
    except Exception as e:
        raise StorageError(
            message="Milvus 检索失败",
            detail=str(e),
        ) from e

    hits = []
    for item in raw[0]:
        entity = item.get("entity", {})
        hits.append({
            "chunk_id": entity.get("chunk_id", ""),
            "doc_id": entity.get("doc_id", ""),
            "doc_type": entity.get("doc_type", ""),
            "distance": item.get("distance", 0.0),
        })

    return hits


def delete_by_doc_id(doc_id: str) -> None:
    """
    删除指定文档的所有向量（文档重新导入时调用）。

    Milvus 的 delete 通过表达式过滤:
      filter='doc_id == "xxx"'
    """
    s = get_settings()
    client: MilvusClient = get_milvus()
    col_name = s.milvus_collection

    if not client.has_collection(col_name):
        return

    try:
        client.load_collection(col_name)
        client.delete(
            collection_name=col_name,
            filter=f'doc_id == "{doc_id}"',
        )
    except Exception as e:
        raise StorageError(
            message="Milvus 删除旧向量失败",
            detail=str(e),
        ) from e
    logger.info("Milvus 删除完成: doc_id=%s", doc_id)
