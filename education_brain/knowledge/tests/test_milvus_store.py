from types import SimpleNamespace

import pytest

from knowledge.core.errors import StorageError
from knowledge.processor import milvus_store
from knowledge.processor.embedder import EmbeddingRecord


def test_ensure_collection_loads_existing_collection(monkeypatch):
    captured = {"loaded": False}

    class FakeMilvus:
        def has_collection(self, collection_name):
            return True

        def load_collection(self, collection_name):
            captured["loaded"] = True
            captured["collection_name"] = collection_name

    monkeypatch.setattr(milvus_store, "get_milvus", lambda: FakeMilvus())
    monkeypatch.setattr(
        milvus_store,
        "get_settings",
        lambda: SimpleNamespace(milvus_collection="edu_chunks", embedding_dim=1024),
    )

    milvus_store.ensure_collection()

    assert captured["loaded"] is True
    assert captured["collection_name"] == "edu_chunks"


def test_upsert_vectors_wraps_milvus_error_in_storage_error(monkeypatch):
    class FakeMilvus:
        def upsert(self, collection_name, data):
            raise RuntimeError("collection not loaded")

    monkeypatch.setattr(milvus_store, "get_milvus", lambda: FakeMilvus())
    monkeypatch.setattr(
        milvus_store,
        "get_settings",
        lambda: SimpleNamespace(milvus_collection="edu_chunks"),
    )

    with pytest.raises(StorageError) as exc:
        milvus_store.upsert_vectors(
            [
                EmbeddingRecord(
                    chunk_id="c1",
                    doc_id="d1",
                    doc_type="project_doc",
                    dense_vector=[0.1, 0.2],
                    sparse_vector={1: 0.5},
                )
            ]
        )

    assert "Milvus 写入失败" in str(exc.value)


def test_hybrid_search_loads_collection_and_returns_hits(monkeypatch):
    captured = {"loaded": False}

    class FakeMilvus:
        def has_collection(self, collection_name):
            return True

        def load_collection(self, collection_name):
            captured["loaded"] = True
            captured["collection_name"] = collection_name

        def hybrid_search(self, **kwargs):
            captured["kwargs"] = kwargs
            return [[
                {
                    "distance": 0.91,
                    "entity": {
                        "chunk_id": "c1",
                        "doc_id": "d1",
                        "doc_type": "project_doc",
                    },
                }
            ]]

    monkeypatch.setattr(milvus_store, "get_milvus", lambda: FakeMilvus())
    monkeypatch.setattr(
        milvus_store,
        "get_settings",
        lambda: SimpleNamespace(
            milvus_collection="edu_chunks",
            query_dense_weight=0.5,
            query_sparse_weight=0.5,
        ),
    )

    hits = milvus_store.hybrid_search(
        dense=[0.1, 0.2],
        sparse={1: 0.8},
        doc_type="project_doc",
        limit=3,
    )

    assert captured["loaded"] is True
    assert captured["collection_name"] == "edu_chunks"
    assert captured["kwargs"]["collection_name"] == "edu_chunks"
    assert captured["kwargs"]["limit"] == 3
    assert hits == [
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "doc_type": "project_doc",
            "distance": 0.91,
        }
    ]
