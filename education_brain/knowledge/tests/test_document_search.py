from knowledge.service import document_search


def test_search_documents_uses_service_pipeline(monkeypatch):
    called = {}

    monkeypatch.setattr(
        document_search,
        "encode_query",
        lambda text: ([0.1, 0.2], {1: 0.5}),
    )

    def fake_hybrid_search(dense, sparse, *, doc_type="", limit=5):
        called["dense"] = dense
        called["sparse"] = sparse
        called["doc_type"] = doc_type
        called["limit"] = limit
        return [
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "doc_type": "project_doc",
                "distance": 0.95,
            }
        ]

    monkeypatch.setattr(document_search, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(
        document_search,
        "lookback_and_assemble",
        lambda hits: [{"chunk_id": hits[0]["chunk_id"], "chunk_text": "hello"}],
    )

    results = document_search.search_documents(
        query="掌柜智库是什么",
        doc_type="project_doc",
        limit=3,
    )

    assert results == [{"chunk_id": "c1", "chunk_text": "hello"}]
    assert called == {
        "dense": [0.1, 0.2],
        "sparse": {1: 0.5},
        "doc_type": "project_doc",
        "limit": 3,
    }
