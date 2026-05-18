# Education Knowledge Base Implementation Plan

> Status: historical implementation plan
>
> This document records an earlier execution plan. It is useful for tracing implementation history, but should not be treated as the current frontend/backend integration contract.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an education knowledge base that imports real course, question-bank, and document data into MongoDB, Milvus, and MinIO, then serves search and cited QA through FastAPI and LangGraph.

**Architecture:** Use MongoDB as the business source of truth, Milvus as the vector retrieval store, and MinIO as object storage for extracted images and future raw assets. Split the system into deterministic importers for catalog and question-bank data, document parsing/chunking for course and project docs, an async import pipeline driven by BackgroundTasks + LangGraph, and a query pipeline that routes course search, question search, document search, and QA separately.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, PyMongo, PyMilvus, MinIO Python SDK, LangGraph, python-docx, pytest, SSE, BGE-M3, BGE-Reranker.

---

### Task 1: Bootstrap The Python Service Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `knowledge/__init__.py`
- Create: `knowledge/main.py`
- Create: `knowledge/core/config.py`
- Create: `knowledge/core/deps.py`
- Create: `knowledge/core/exceptions.py`
- Create: `knowledge/api/__init__.py`
- Create: `tests/test_app_boot.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from knowledge.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_boot.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `app`

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app_boot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml knowledge/__init__.py knowledge/main.py knowledge/core/config.py knowledge/core/deps.py knowledge/core/exceptions.py knowledge/api/__init__.py tests/test_app_boot.py
git commit -m "chore: bootstrap education knowledge base service"
```

### Task 2: Define MongoDB, Milvus, And MinIO Data Contracts

**Files:**
- Create: `knowledge/schema/common.py`
- Create: `knowledge/schema/catalog.py`
- Create: `knowledge/schema/questions.py`
- Create: `knowledge/schema/documents.py`
- Create: `knowledge/schema/tasks.py`
- Create: `knowledge/util/mongo_collections.py`
- Test: `tests/test_schema_defaults.py`

- [ ] **Step 1: Write the failing test**

```python
from knowledge.schema.tasks import IngestTask


def test_ingest_task_defaults():
    task = IngestTask(task_id="t1", task_type="catalog")
    assert task.status == "pending"
    assert task.progress_logs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema_defaults.py -v`
Expected: FAIL with import error or missing fields

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class IngestTask(BaseModel):
    task_id: str
    task_type: str
    status: str = "pending"
    progress_logs: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema_defaults.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/schema/common.py knowledge/schema/catalog.py knowledge/schema/questions.py knowledge/schema/documents.py knowledge/schema/tasks.py knowledge/util/mongo_collections.py tests/test_schema_defaults.py
git commit -m "feat: define storage contracts for mongo milvus and minio"
```

### Task 3: Import The Course Catalog From `课程介绍.md`

**Files:**
- Create: `knowledge/util/catalog_parser.py`
- Create: `knowledge/services/catalog_import_service.py`
- Create: `tests/fixtures/catalog_sample.md`
- Test: `tests/test_catalog_parser.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from knowledge.util.catalog_parser import parse_catalog_markdown


def test_parse_catalog_series_and_modules():
    result = parse_catalog_markdown(Path("tests/fixtures/catalog_sample.md"))
    assert len(result.series) == 1
    assert result.series[0].series_code == "general_purpose_programming_foundation"
    assert len(result.modules) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_catalog_parser.py -v`
Expected: FAIL because parser does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def parse_catalog_markdown(path):
    # Parse ## series blocks and ### 课程 subsections into series/modules objects.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_catalog_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/util/catalog_parser.py knowledge/services/catalog_import_service.py tests/fixtures/catalog_sample.md tests/test_catalog_parser.py
git commit -m "feat: add deterministic catalog importer"
```

### Task 4: Import The Question Bank From `题目资料.md`

**Files:**
- Create: `knowledge/util/question_bank_parser.py`
- Create: `knowledge/services/question_import_service.py`
- Create: `tests/fixtures/questions_sample.md`
- Test: `tests/test_question_bank_parser.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from knowledge.util.question_bank_parser import parse_question_banks


def test_parse_question_bank_with_options_and_flags():
    result = parse_question_banks(Path("tests/fixtures/questions_sample.md"))
    assert len(result.banks) == 1
    assert len(result.questions) == 2
    assert result.questions[0].question_type == "单选题"
    assert result.questions[0].options[0]["label"] == "A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_question_bank_parser.py -v`
Expected: FAIL because parser does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def parse_question_banks(path):
    # Split by ## bank and ### question_code, normalize options/answers/quality_flags.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_question_bank_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/util/question_bank_parser.py knowledge/services/question_import_service.py tests/fixtures/questions_sample.md tests/test_question_bank_parser.py
git commit -m "feat: add deterministic question bank importer"
```

### Task 5: Parse Documents, Extract Images, And Upload Assets To MinIO

**Files:**
- Create: `knowledge/util/docx_parser.py`
- Create: `knowledge/util/markdown_parser.py`
- Create: `knowledge/util/chunk_builder.py`
- Create: `knowledge/util/minio_asset_store.py`
- Create: `knowledge/services/document_import_service.py`
- Test: `tests/test_chunk_builder.py`
- Test: `tests/test_minio_asset_store.py`

- [ ] **Step 1: Write the failing tests**

```python
from knowledge.util.chunk_builder import build_chunks


def test_build_chunks_keeps_section_path():
    blocks = [
        {"section_path": ["项目架构", "技术栈"], "text": "FastAPI + LangGraph"}
    ]
    chunks = build_chunks(blocks, max_chars=200)
    assert chunks[0]["section_path"] == ["项目架构", "技术栈"]
```

```python
from knowledge.util.minio_asset_store import build_object_key


def test_build_object_key_is_stable():
    key = build_object_key(doc_id="doc1", image_name="image1.png")
    assert key == "documents/doc1/images/image1.png"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chunk_builder.py tests/test_minio_asset_store.py -v`
Expected: FAIL because utilities do not exist

- [ ] **Step 3: Write minimal implementation**

```python
def build_chunks(blocks, max_chars):
    # Merge adjacent text blocks while preserving section_path and asset refs.
    ...


def build_object_key(doc_id, image_name):
    return f"documents/{doc_id}/images/{image_name}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chunk_builder.py tests/test_minio_asset_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/util/docx_parser.py knowledge/util/markdown_parser.py knowledge/util/chunk_builder.py knowledge/util/minio_asset_store.py knowledge/services/document_import_service.py tests/test_chunk_builder.py tests/test_minio_asset_store.py
git commit -m "feat: add document parsing chunking and minio asset support"
```

### Task 6: Build The Async Import Pipeline With BackgroundTasks And LangGraph

**Files:**
- Create: `knowledge/processor/import_pipeline/state.py`
- Create: `knowledge/processor/import_pipeline/base.py`
- Create: `knowledge/processor/import_pipeline/graph.py`
- Create: `knowledge/processor/import_pipeline/nodes/catalog_import_node.py`
- Create: `knowledge/processor/import_pipeline/nodes/question_import_node.py`
- Create: `knowledge/processor/import_pipeline/nodes/document_import_node.py`
- Create: `knowledge/processor/import_pipeline/nodes/vectorize_node.py`
- Create: `knowledge/processor/import_pipeline/nodes/milvus_import_node.py`
- Create: `knowledge/util/task_util.py`
- Create: `knowledge/api/ingest_router.py`
- Test: `tests/test_import_graph.py`

- [ ] **Step 1: Write the failing test**

```python
from knowledge.processor.import_pipeline.graph import build_import_graph


def test_import_graph_builds():
    graph = build_import_graph()
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_import_graph.py -v`
Expected: FAIL because graph builder does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def build_import_graph():
    # Build a LangGraph StateGraph routing catalog/questions/documents to matching nodes.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_import_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/processor/import_pipeline/state.py knowledge/processor/import_pipeline/base.py knowledge/processor/import_pipeline/graph.py knowledge/processor/import_pipeline/nodes/catalog_import_node.py knowledge/processor/import_pipeline/nodes/question_import_node.py knowledge/processor/import_pipeline/nodes/document_import_node.py knowledge/processor/import_pipeline/nodes/vectorize_node.py knowledge/processor/import_pipeline/nodes/milvus_import_node.py knowledge/util/task_util.py knowledge/api/ingest_router.py tests/test_import_graph.py
git commit -m "feat: add async import pipeline with task tracking"
```

### Task 7: Add Course, Question, And Document Search APIs

**Files:**
- Create: `knowledge/services/course_search_service.py`
- Create: `knowledge/services/question_search_service.py`
- Create: `knowledge/services/document_search_service.py`
- Create: `knowledge/api/search_router.py`
- Create: `knowledge/schema/search_schema.py`
- Test: `tests/test_search_filters.py`

- [ ] **Step 1: Write the failing test**

```python
from knowledge.services.question_search_service import build_question_filters


def test_build_question_filters():
    filters = build_question_filters(bank_code="postgraduate_math_bank", question_type="单选题")
    assert filters["bank_code"] == "postgraduate_math_bank"
    assert filters["question_type"] == "单选题"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_search_filters.py -v`
Expected: FAIL because service function does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def build_question_filters(bank_code=None, question_type=None, keyword=None):
    filters = {}
    if bank_code:
        filters["bank_code"] = bank_code
    if question_type:
        filters["question_type"] = question_type
    return filters
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_search_filters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/services/course_search_service.py knowledge/services/question_search_service.py knowledge/services/document_search_service.py knowledge/api/search_router.py knowledge/schema/search_schema.py tests/test_search_filters.py
git commit -m "feat: add structured search services and APIs"
```

### Task 8: Build The Query Pipeline, Chat History, And SSE Output

**Files:**
- Create: `knowledge/processor/query_pipeline/state.py`
- Create: `knowledge/processor/query_pipeline/query_base.py`
- Create: `knowledge/processor/query_pipeline/graph.py`
- Create: `knowledge/processor/query_pipeline/nodes/intent_route_node.py`
- Create: `knowledge/processor/query_pipeline/nodes/vector_search_node.py`
- Create: `knowledge/processor/query_pipeline/nodes/rerank_node.py`
- Create: `knowledge/processor/query_pipeline/nodes/answer_output_node.py`
- Create: `knowledge/util/mongo_history_util.py`
- Create: `knowledge/util/sse_util.py`
- Create: `knowledge/services/query_service.py`
- Create: `knowledge/api/query_router.py`
- Create: `knowledge/prompt/query_prompt.py`
- Create: `knowledge/front/chat.html`
- Test: `tests/test_query_graph.py`

- [ ] **Step 1: Write the failing test**

```python
from knowledge.processor.query_pipeline.graph import build_query_graph


def test_query_graph_builds():
    graph = build_query_graph()
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_query_graph.py -v`
Expected: FAIL because query graph does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def build_query_graph():
    # Route course/question searches directly and run QA through vector search + rerank + answer output.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_query_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/processor/query_pipeline/state.py knowledge/processor/query_pipeline/query_base.py knowledge/processor/query_pipeline/graph.py knowledge/processor/query_pipeline/nodes/intent_route_node.py knowledge/processor/query_pipeline/nodes/vector_search_node.py knowledge/processor/query_pipeline/nodes/rerank_node.py knowledge/processor/query_pipeline/nodes/answer_output_node.py knowledge/util/mongo_history_util.py knowledge/util/sse_util.py knowledge/services/query_service.py knowledge/api/query_router.py knowledge/prompt/query_prompt.py knowledge/front/chat.html tests/test_query_graph.py
git commit -m "feat: add query pipeline history and streaming qa"
```

### Task 9: End-To-End Verification With Real Data Slices

**Files:**
- Create: `tests/e2e/test_catalog_import_e2e.py`
- Create: `tests/e2e/test_question_import_e2e.py`
- Create: `tests/e2e/test_document_import_e2e.py`
- Create: `tests/e2e/test_search_and_query_e2e.py`
- Modify: `docs/PLAN.md`
- Modify: `docs/需求文档.md`

- [ ] **Step 1: Write the failing end-to-end tests**

```python
def test_catalog_import_e2e():
    # Import a small real slice and assert MongoDB records were written.
    ...
```

```python
def test_document_query_e2e():
    # Import one project doc, search a known section, and assert citations are returned.
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/e2e -v`
Expected: FAIL because pipelines or fixtures are incomplete

- [ ] **Step 3: Write minimal implementation support**

```python
# Add fixtures, seed slices, and test helpers needed to validate
# catalog import, question import, document import, and cited QA.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/e2e -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_catalog_import_e2e.py tests/e2e/test_question_import_e2e.py tests/e2e/test_document_import_e2e.py tests/e2e/test_search_and_query_e2e.py docs/PLAN.md docs/需求文档.md
git commit -m "test: add end to end coverage for education knowledge base"
```

### Task 10: Final Integration And Release Checklist

**Files:**
- Modify: `knowledge/main.py`
- Modify: `knowledge/api/ingest_router.py`
- Modify: `knowledge/api/search_router.py`
- Modify: `knowledge/api/query_router.py`
- Modify: `docs/implementation-plans/2026-04-17-education-kb-implementation.md`

- [ ] **Step 1: Add final integration checks**

```python
# Register all routers under main app and ensure /health, /ingest, /search, /chat all mount correctly.
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest tests -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python -m py_compile $(find knowledge -name '*.py' | tr '\n' ' ')`
Expected: no output

- [ ] **Step 4: Smoke-check the app**

Run: `python -m uvicorn knowledge.main:app --reload`
Expected: app starts and exposes `/health`

- [ ] **Step 5: Commit**

```bash
git add knowledge/main.py knowledge/api/ingest_router.py knowledge/api/search_router.py knowledge/api/query_router.py docs/implementation-plans/2026-04-17-education-kb-implementation.md
git commit -m "chore: finalize integration plan and release checklist"
```
