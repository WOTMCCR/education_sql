"""
BGE-M3 向量化 — 对应 PLAN.md §6.4 步骤 4

将 KnowledgeChunk 的文本转换为稠密+稀疏双向量。
分 batch 推理，避免 GPU OOM。
"""

import logging
from dataclasses import dataclass
from typing import Any

from knowledge.core.clients import encode_bge_documents
from knowledge.core.config import get_settings
from knowledge.models.document import KnowledgeChunk

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingRecord:
    """一个 chunk 的向量化结果，对齐 Milvus schema"""
    chunk_id: str
    doc_id: str
    doc_type: str
    dense_vector: list[float]
    sparse_vector: dict  # {int_index: float_weight}


def csr_row_to_sparse_dict(sparse, row: int = 0) -> dict[int, float]:
    """将 BGE-M3 输出的单条 sparse 向量统一转成 Milvus 可接受的 dict。"""
    if isinstance(sparse, dict):
        return {
            int(index): float(value)
            for index, value in sparse.items()
        }

    if isinstance(sparse, (list, tuple)):
        return csr_row_to_sparse_dict(sparse[row])

    # scipy CSR 稀疏矩阵：取指定行
    if hasattr(sparse, "indptr") and hasattr(sparse, "indices") and hasattr(sparse, "data"):
        start = sparse.indptr[row]
        end = sparse.indptr[row + 1]
        return {
            int(index): float(value)
            for index, value in zip(
                sparse.indices[start:end].tolist(),
                sparse.data[start:end].tolist(),
            )
        }

    # scipy sparse row（csr_array / csr_matrix / coo 等）
    if hasattr(sparse, "tocoo"):
        coo = sparse.tocoo()

        # scipy sparse array 用 coords，matrix 用 col
        if hasattr(coo, "coords"):
            indices = coo.coords[-1].tolist()
        else:
            indices = coo.col.tolist()

        values = coo.data.tolist()
        return {
            int(index): float(value)
            for index, value in zip(indices, values)
        }

    raise TypeError(f"不支持的 sparse 向量类型: {type(sparse)!r}")

def embed_chunks(
    chunks: list[KnowledgeChunk],
    doc_type: str = "course_doc",
) -> list[EmbeddingRecord]:
    """
    批量生成 embedding。

    参数：
        chunks:    KnowledgeChunk 列表（来自 chunker 输出）
        doc_type:  文档类型，透传到 EmbeddingRecord 供 Milvus 过滤用

    返回：
        EmbeddingRecord 列表，与输入 chunks 一一对应

    失败处理：
        单 batch 失败记录 warning，跳过该 batch 的 chunks。
        不阻断后续 batch 的处理。
    """
    if not chunks:
        return []

    s = get_settings()
    batch_size = s.embedding_batch_size

    records: list[EmbeddingRecord] = []

    # 分 batch 处理
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.chunk_text for c in batch]

        try:
            # BGEM3EmbeddingFunction 返回:
            #   dense: list[np.ndarray]
            #   sparse: 可能是 list[dict]，也可能是 scipy sparse 矩阵
            result = encode_bge_documents(texts)

            dense_list = result["dense"]
            sparse_list = result["sparse"]

            for j , chunk in enumerate(batch):
                records.append(EmbeddingRecord(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    doc_type=doc_type,
                    dense_vector=dense_list[j].tolist()
                        if hasattr(dense_list[j], "tolist")
                        else list(dense_list[j]),
                    sparse_vector=csr_row_to_sparse_dict(sparse_list, row=j),
                ))
        except Exception as e:
            logger.warning(
                "Embedding batch 失败 (batch %d-%d): %s",
                i, i + len(batch), e,
            )
            continue
    
    logger.info(
        "向量化完成: %d/%d chunks 成功",
        len(records), len(chunks),
    )
    return records
