from types import SimpleNamespace

import pytest

from knowledge.util import demo_data_admin


def test_reset_demo_data_clears_all_demo_targets(monkeypatch):
    dropped_collections = []
    removed_objects = []

    class FakeMongoCollection:
        def __init__(self, name):
            self.name = name

        def drop(self):
            dropped_collections.append(self.name)

    class FakeMongoDB:
        def __getitem__(self, name):
            return FakeMongoCollection(name)

    class FakeMilvus:
        def has_collection(self, name):
            return True

        def drop_collection(self, name):
            dropped_collections.append(f"milvus:{name}")

    class FakeObject:
        def __init__(self, object_name):
            self.object_name = object_name

    class FakeMinio:
        def bucket_exists(self, bucket):
            assert bucket == "education-knowledge"
            return True

        def list_objects(self, bucket, prefix, recursive):
            assert bucket == "education-knowledge"
            assert prefix == "documents/"
            assert recursive is True
            return [FakeObject("documents/a.png"), FakeObject("documents/b.png")]

        def remove_object(self, bucket, object_name):
            removed_objects.append((bucket, object_name))

    monkeypatch.setattr(demo_data_admin, "get_mongo_db", lambda: FakeMongoDB())
    monkeypatch.setattr(demo_data_admin, "get_milvus", lambda: FakeMilvus())
    monkeypatch.setattr(demo_data_admin, "get_minio", lambda: FakeMinio())
    monkeypatch.setattr(
        demo_data_admin,
        "get_settings",
        lambda: SimpleNamespace(
            milvus_collection="edu_chunks",
            minio_bucket="education-knowledge",
        ),
    )

    summary = demo_data_admin.reset_demo_data(include_minio=True)

    assert dropped_collections == [
        "knowledge_document",
        "knowledge_chunk",
        "source_mapping",
        "ingest_task",
        "course_series",
        "course_module",
        "question_bank",
        "question_item",
        "milvus:edu_chunks",
    ]
    assert removed_objects == [
        ("education-knowledge", "documents/a.png"),
        ("education-knowledge", "documents/b.png"),
    ]
    assert summary["minio_removed"] == 2


def test_run_reimport_sequence_calls_ingest_endpoints_in_order():
    posted = []
    polled = []

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self):
            self._task_status = {
                "catalog-task": {"status": "completed"},
                "questions-task": {"status": "completed"},
                "course-doc-task": {"status": "completed"},
                "project-doc-task": {"status": "completed"},
            }

        def post(self, url, json):
            posted.append((url, json))
            if url.endswith("/ingest/catalog"):
                return FakeResponse({"task_id": "catalog-task"})
            if url.endswith("/ingest/questions"):
                return FakeResponse({"task_id": "questions-task"})
            if json == {"doc_type": "course_doc"}:
                return FakeResponse({"task_id": "course-doc-task"})
            return FakeResponse({"task_id": "project-doc-task"})

        def get(self, url):
            polled.append(url)
            task_id = url.rsplit("/", 1)[-1]
            return FakeResponse({"task_id": task_id, **self._task_status[task_id]})

    result = demo_data_admin.run_reimport_sequence(
        api_base_url="http://127.0.0.1:8000",
        client=FakeClient(),
        poll_interval=0,
        timeout_seconds=5,
    )

    assert posted == [
        ("http://127.0.0.1:8000/ingest/catalog", {}),
        ("http://127.0.0.1:8000/ingest/questions", {}),
        ("http://127.0.0.1:8000/ingest/documents", {"doc_type": "course_doc"}),
        ("http://127.0.0.1:8000/ingest/documents", {"doc_type": "project_doc"}),
    ]
    assert polled == [
        "http://127.0.0.1:8000/ingest/tasks/catalog-task",
        "http://127.0.0.1:8000/ingest/tasks/questions-task",
        "http://127.0.0.1:8000/ingest/tasks/course-doc-task",
        "http://127.0.0.1:8000/ingest/tasks/project-doc-task",
    ]
    assert [item["name"] for item in result] == [
        "catalog",
        "questions",
        "course_doc",
        "project_doc",
    ]


def test_run_reimport_sequence_stops_on_non_completed_status():
    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    class FakeClient:
        def post(self, url, json):
            if url.endswith("/ingest/catalog"):
                return FakeResponse({"task_id": "catalog-task"})
            return FakeResponse({"task_id": "unused"})

        def get(self, url):
            return FakeResponse({"task_id": "catalog-task", "status": "partial_success"})

    with pytest.raises(RuntimeError, match="catalog"):
        demo_data_admin.run_reimport_sequence(
            api_base_url="http://127.0.0.1:8000",
            client=FakeClient(),
            poll_interval=0,
            timeout_seconds=5,
        )
