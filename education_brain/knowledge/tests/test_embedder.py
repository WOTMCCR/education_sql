# knowledge/tests/test_embedder.py
"""embedder 单元测试 — Mock BGE-M3，验证分 batch 逻辑"""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import numpy as np
from scipy.sparse import csr_array

from knowledge.models.document import KnowledgeChunk


def _make_chunk(chunk_id: str, text: str, doc_id: str = "doc1") -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        chunk_text=text,
    )


def _make_mock_bge_m3(dim: int = 1024):
    """构造一个假的 BGEM3EmbeddingFunction"""
    def mock_call(texts):
        n = len(texts)
        return {
            "dense": [np.random.randn(dim).astype(np.float32) for _ in range(n)],
            "sparse": [{0: 0.5, 10: 0.3} for _ in range(n)],
        }
    mock = MagicMock(side_effect=mock_call)
    return mock


def test_embed_chunks_basic():
    """基本向量化：3 个 chunk，batch_size=2 → 应分 2 个 batch"""
    chunks = [
        _make_chunk("c1", "Python 是一种编程语言"),
        _make_chunk("c2", "MySQL 是关系数据库"),
        _make_chunk("c3", "Redis 是缓存系统"),
    ]

    mock_model = _make_mock_bge_m3()

    with patch("knowledge.processor.embedder.encode_bge_documents", side_effect=mock_model), \
         patch("knowledge.processor.embedder.get_settings") as mock_settings:

        mock_settings.return_value = SimpleNamespace(embedding_batch_size=2)

        from knowledge.processor.embedder import embed_chunks
        records = embed_chunks(chunks, doc_type="course_doc")

    assert len(records) == 3
    # 验证 batch 被调用了 2 次（2 + 1）
    assert mock_model.call_count == 2

    # 验证字段填充
    r = records[0]
    assert r.chunk_id == "c1"
    assert r.doc_id == "doc1"
    assert r.doc_type == "course_doc"
    assert len(r.dense_vector) == 1024
    assert isinstance(r.sparse_vector, dict)


def test_embed_chunks_empty():
    """空输入直接返回空列表，不调用模型"""
    from knowledge.processor.embedder import embed_chunks

    with patch("knowledge.processor.embedder.encode_bge_documents") as mock_model:
        records = embed_chunks([], doc_type="course_doc")

    assert records == []
    mock_model.assert_not_called()


def test_embed_chunks_batch_failure():
    """某个 batch 失败时，其他 batch 的结果仍然返回"""
    chunks = [
        _make_chunk("c1", "正常文本"),
        _make_chunk("c2", "正常文本"),
        _make_chunk("c3", "正常文本"),
        _make_chunk("c4", "正常文本"),
    ]

    call_count = {"n": 0}

    def mock_call(texts):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("GPU OOM 模拟")
        n = len(texts)
        return {
            "dense": [np.random.randn(1024).astype(np.float32) for _ in range(n)],
            "sparse": [{0: 0.5} for _ in range(n)],
        }

    mock_model = MagicMock(side_effect=mock_call)

    with patch("knowledge.processor.embedder.encode_bge_documents", side_effect=mock_model), \
         patch("knowledge.processor.embedder.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(embedding_batch_size=2)

        from knowledge.processor.embedder import embed_chunks
        records = embed_chunks(chunks, doc_type="course_doc")

    # 第一个 batch (c1, c2) 成功，第二个 batch (c3, c4) 失败
    assert len(records) == 2
    assert records[0].chunk_id == "c1"
    assert records[1].chunk_id == "c2"


def test_embed_chunks_converts_sparse_matrix_row_to_dict():
    """BGE-M3 返回 scipy sparse 矩阵时，应转换成 Milvus 可接受的 dict。"""
    chunks = [_make_chunk("c1", "Python 连接 MySQL")]

    def mock_call(texts):
        assert texts == ["Python 连接 MySQL"]
        return {
            "dense": [np.random.randn(1024).astype(np.float32)],
            "sparse": csr_array([[0.0, 0.5, 0.0, 0.3]]),
        }

    mock_model = MagicMock(side_effect=mock_call)

    with patch("knowledge.processor.embedder.encode_bge_documents", side_effect=mock_model), \
         patch("knowledge.processor.embedder.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(embedding_batch_size=2)

        from knowledge.processor.embedder import embed_chunks
        records = embed_chunks(chunks, doc_type="course_doc")

    assert len(records) == 1
    assert records[0].sparse_vector == {1: 0.5, 3: 0.3}
