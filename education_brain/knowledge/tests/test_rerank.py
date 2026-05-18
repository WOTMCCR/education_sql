from types import SimpleNamespace

from knowledge.processor.query_pipeline.nodes import rerank as rerank_node


def test_rerank_returns_enriched_docs_when_disabled(monkeypatch):
    enriched = [
        {"chunk_id": "c1", "chunk_text": "Python 连接数据库"},
        {"chunk_id": "c2", "chunk_text": "FastAPI 基础"},
    ]

    monkeypatch.setattr(
        rerank_node,
        "get_settings",
        lambda: SimpleNamespace(
            enable_rerank=False,
            rerank_max_top_k=10,
            rerank_min_top_k=3,
            rerank_gap_abs=0.5,
            rerank_gap_ratio=0.25,
            rerank_min_score=None,
        ),
    )
    monkeypatch.setattr(
        rerank_node,
        "lookback_and_assemble",
        lambda hits: enriched,
    )

    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("禁用 rerank 时不应调用交叉编码器")

    monkeypatch.setattr(rerank_node, "_rerank_docs", fail_if_called)

    result = rerank_node.rerank(
        {
            "original_query": "Python",
            "rrf_chunks": [
                {"chunk_id": "c1", "doc_id": "d1"},
                {"chunk_id": "c2", "doc_id": "d1"},
            ],
        }
    )

    assert result == {"final_chunks": enriched}
    assert called["value"] is False
