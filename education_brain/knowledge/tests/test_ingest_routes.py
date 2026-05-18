from fastapi import BackgroundTasks

from knowledge.api.routes import ingest as ingest_module


def test_ingest_documents_uses_file_path_field(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.md"
    file_path.write_text("# sample\n", encoding="utf-8")

    monkeypatch.setattr(
        ingest_module,
        "_discover_document_files",
        lambda doc_type: [file_path],
    )
    monkeypatch.setattr(ingest_module, "create_task", lambda task: None)

    response = ingest_module.ingest_documents(
        ingest_module.DocumentsRequest(doc_type="project_doc"),
        BackgroundTasks(),
    )

    assert response.task_id
