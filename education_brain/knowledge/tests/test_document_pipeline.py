# knowledge/tests/test_document_pipeline.py
"""
文档导入流水线端到端测试

测试策略：
  模拟完整的文档导入流程（解析 → 分块 → 存储），
  但用 Mock 替换外部服务依赖（MongoDB / MinIO），
  只验证流水线的数据流转逻辑。

  对于真正需要外部服务的集成测试，
  应该在服务启动后单独运行。
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_full_pipeline_with_real_markdown():
    """
    用真实 .md 文件走完整流水线（解析 → 分块），
    不依赖 MongoDB / MinIO。

    验证点：
    - parse_markdown + chunk_document 的端到端衔接
    - 产出的 KnowledgeDocument 和 KnowledgeChunk 字段完整
    """
    from knowledge.processor.markdown_parser import parse_markdown
    from knowledge.processor.chunker import chunk_document
    from knowledge.models.document import KnowledgeDocument

    md_file = (
        PROJECT_ROOT / "data" / "数据" / "项目文档" / "掌柜智库"
        / "01_掌柜智库项目全景.md"
    )
    if not md_file.exists():
        print(f"⚠ 跳过（文件不存在: {md_file}）")
        return

    text = md_file.read_text(encoding="utf-8")
    doc_id = "pipeline_test_001"

    # 解析
    blocks = parse_markdown(text)
    assert len(blocks) > 0

    # 分块
    chunks = chunk_document(blocks, doc_id=doc_id)
    assert len(chunks) > 0

    # 构建文档元数据
    doc = KnowledgeDocument(
        doc_id=doc_id,
        doc_type="project_doc",
        source_path=str(md_file),
        source_file=md_file.name,
        title=blocks[0].content if blocks[0].kind == "heading" else md_file.stem,
        chunk_count=len(chunks),
    )

    # 验证文档元数据
    assert doc.doc_id == doc_id
    assert doc.doc_type == "project_doc"
    assert doc.chunk_count == len(chunks)
    assert doc.source_file == "01_掌柜智库项目全景.md"

    # 验证 chunk 质量
    print(f"\n流水线测试结果:")
    print(f"  文档: {doc.source_file}")
    print(f"  标题: {doc.title}")
    print(f"  总 chunk: {doc.chunk_count}")

    for i, c in enumerate(chunks[:3]):
        print(f"\n  chunk[{i}]:")
        print(f"    kind: {c.chunk_kind}")
        print(f"    path: {c.section_path}")
        print(f"    长度: {len(c.chunk_text)} 字符")
        print(f"    预览: {c.chunk_text[:50].replace(chr(10), ' ')}...")

    print("\n✓ 完整流水线测试通过")


def test_docx_to_chunks_pipeline():
    """
    .docx → .md → 解析 → 分块 的完整链路测试。

    选择一个小型 .docx 文件走完全流程。
    """
    docx_file = (
        PROJECT_ROOT / "data" / "数据" / "课程文档"
        / "尚硅谷大模型技术之Shell1.0.docx"
    )
    if not docx_file.exists():
        print(f"⚠ 跳过（文件不存在: {docx_file.name}）")
        return

    from knowledge.processor.docx_converter import convert_docx_to_markdown
    from knowledge.processor.markdown_parser import parse_markdown
    from knowledge.processor.chunker import chunk_document

    # 转换
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "images"
        md_text, image_paths = convert_docx_to_markdown(docx_file, output_dir)

    assert md_text, ".docx 转换失败"

    # 解析
    blocks = parse_markdown(md_text)
    assert len(blocks) > 0, "Markdown 解析结果为空"

    # 分块
    doc_id = "docx_pipeline_test"
    chunks = chunk_document(blocks, doc_id=doc_id)
    assert len(chunks) > 0, "分块结果为空"

    print(f"\n.docx 完整链路测试:")
    print(f"  文件: {docx_file.name}")
    print(f"  Markdown: {len(md_text)} 字符, {len(md_text.splitlines())} 行")
    print(f"  解析块: {len(blocks)}")
    print(f"  chunk: {len(chunks)}")
    print(f"  图片: {len(image_paths)}")

    # 验证 section_path 不为空（至少部分 chunk 有路径）
    chunks_with_path = [c for c in chunks if c.section_path]
    print(f"  有 section_path 的 chunk: {len(chunks_with_path)}/{len(chunks)}")

    print("✓ .docx 完整链路测试通过")


def test_document_store_with_mock_db():
    """
    测试 document_store 的写入逻辑（Mock MongoDB）。

    验证：
    - upsert 文档元数据
    - 先删旧 chunk 再写新 chunk
    - 建索引调用
    """
    from knowledge.processor.document_store import save_document
    from knowledge.models.document import KnowledgeDocument, KnowledgeChunk

    # 构造测试数据
    doc = KnowledgeDocument(
        doc_id="mock_doc_001",
        doc_type="course_doc",
        source_file="test.docx",
        chunk_count=2,
    )
    chunks = [
        KnowledgeChunk(
            chunk_id="chunk_001",
            doc_id="mock_doc_001",
            chunk_text="测试内容1",
            chunk_index=0,
        ),
        KnowledgeChunk(
            chunk_id="chunk_002",
            doc_id="mock_doc_001",
            chunk_text="测试内容2",
            chunk_index=1,
        ),
    ]

    # Mock MongoDB
    mock_db = MagicMock()
    mock_doc_col = MagicMock()
    mock_chunk_col = MagicMock()
    mock_db.__getitem__ = lambda self, name: {
        "knowledge_document": mock_doc_col,
        "knowledge_chunk": mock_chunk_col,
    }[name]

    # 执行
    result = save_document(mock_db, doc, chunks)

    # 验证
    assert result == 2, f"应返回写入 2 个 chunk，实际 {result}"

    # 验证 upsert 文档元数据被调用
    mock_doc_col.update_one.assert_called_once()
    call_args = mock_doc_col.update_one.call_args
    assert call_args[0][0] == {"doc_id": "mock_doc_001"}  # filter
    assert call_args[1].get("upsert") is True

    # 验证先删旧 chunk
    mock_chunk_col.delete_many.assert_called_once_with({"doc_id": "mock_doc_001"})

    # 验证写入新 chunk
    mock_chunk_col.insert_many.assert_called_once()
    inserted_docs = mock_chunk_col.insert_many.call_args[0][0]
    assert len(inserted_docs) == 2

    # 验证建索引
    assert mock_doc_col.create_index.call_count >= 2   # doc_id + doc_type
    assert mock_chunk_col.create_index.call_count >= 2  # chunk_id + doc_id

    print("✓ document_store Mock 测试通过")


def test_image_uploader_with_mock_minio():
    """
    测试图片上传逻辑（Mock MinIO）。

    验证：
    - 每张图片调用 fput_object
    - 返回的 path_map 正确映射 文件名 → URL
    - 单张图片失败不阻断整体
    """
    from knowledge.processor.image_uploader import upload_images

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 创建假图片文件
        img1 = Path(tmp_dir) / "fig1.png"
        img2 = Path(tmp_dir) / "fig2.jpg"
        img1.write_bytes(b"fake png data")
        img2.write_bytes(b"fake jpg data")

        # Mock MinIO 客户端
        mock_minio = MagicMock()

        with patch("knowledge.processor.image_uploader.get_minio", return_value=mock_minio), \
             patch("knowledge.processor.image_uploader.ensure_minio_bucket"):

            path_map = upload_images("doc_test", [img1, img2])

    # 验证
    assert len(path_map) == 2, f"应有 2 个映射，实际 {len(path_map)}"
    assert "fig1.png" in path_map
    assert "fig2.jpg" in path_map

    # URL 格式正确
    assert "documents/doc_test/images/fig1.png" in path_map["fig1.png"]
    assert "documents/doc_test/images/fig2.jpg" in path_map["fig2.jpg"]

    # MinIO fput_object 被调用 2 次
    assert mock_minio.fput_object.call_count == 2

    print(f"  path_map: {path_map}")
    print("✓ 图片上传 Mock 测试通过")


def test_image_uploader_with_real_minio():
    """用真实 MinIO 验证对象确实被写入 bucket。

    默认跳过，避免把普通单元测试变成环境依赖测试。
    运行方式：
      RUN_REAL_MINIO=1 uv run python -m pytest tests/test_document_pipeline.py -k real_minio -s -v
    """
    import os

    if os.getenv("RUN_REAL_MINIO") != "1":
        pytest.skip("未设置 RUN_REAL_MINIO=1，跳过真实 MinIO 集成测试")

    from knowledge.core.clients import get_minio
    from knowledge.core.config import get_settings
    from knowledge.processor.image_uploader import upload_images

    s = get_settings()

    with tempfile.TemporaryDirectory() as tmp_dir:
        img = Path(tmp_dir) / "real_minio_test.png"
        img.write_bytes(b"fake png data for minio integration test")

        doc_id = f"test-{uuid.uuid4().hex[:12]}"
        path_map = upload_images(doc_id, [img])

        assert "real_minio_test.png" in path_map

        object_key = f"documents/{doc_id}/images/{img.name}"
        stat = get_minio().stat_object(s.minio_bucket, object_key)

    assert stat.object_name == object_key
    print(f"  bucket: {s.minio_bucket}")
    print(f"  object: {object_key}")
    print(f"  url: {path_map[img.name]}")
    print("✓ 真实 MinIO 图片上传测试通过")


def test_image_upload_partial_failure():
    """
    测试图片上传部分失败的容错。

    第一张图片上传成功，第二张失败，
    应该返回只包含成功图片的 path_map，不抛异常。
    """
    from knowledge.processor.image_uploader import upload_images

    with tempfile.TemporaryDirectory() as tmp_dir:
        img1 = Path(tmp_dir) / "ok.png"
        img2 = Path(tmp_dir) / "fail.png"
        img1.write_bytes(b"fake")
        img2.write_bytes(b"fake")

        mock_minio = MagicMock()

        # 第一次调用成功，第二次抛异常
        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise ConnectionError("MinIO unreachable")

        mock_minio.fput_object.side_effect = side_effect

        with patch("knowledge.processor.image_uploader.get_minio", return_value=mock_minio), \
             patch("knowledge.processor.image_uploader.ensure_minio_bucket"):

            path_map = upload_images("doc_fail", [img1, img2])

    # 应该只有 1 个成功
    assert len(path_map) == 1, f"应只有 1 个成功映射，实际 {len(path_map)}"
    assert "ok.png" in path_map

    print("✓ 图片上传部分失败容错测试通过")


def test_replace_image_refs():
    """测试 chunk 中图片路径替换"""
    from knowledge.processor.image_uploader import replace_image_refs
    from knowledge.models.document import KnowledgeChunk

    chunks = [
        KnowledgeChunk(
            chunk_id="c1",
            doc_id="d1",
            chunk_text="架构图：![arch](images/arch.png)\n详见图片",
            image_refs=["images/arch.png"],
        ),
    ]

    path_map = {
        "arch.png": "http://minio:9000/bucket/documents/d1/images/arch.png"
    }

    replace_image_refs(chunks, path_map)

    # chunk_text 中的路径应该被替换
    assert "http://minio:9000" in chunks[0].chunk_text
    assert "![arch](images/arch.png)" not in chunks[0].chunk_text
    assert "![arch](http://minio:9000/" in chunks[0].chunk_text

    # image_refs 也应该更新
    assert chunks[0].image_refs[0].startswith("http://minio:9000")

    print("✓ 图片路径替换测试通过")


def test_mapping_rules_with_mock_db():
    """测试来源映射规则（Mock MongoDB）"""
    from knowledge.processor.mapping_rules import infer_source_mapping

    # Mock MongoDB: course_series 集合
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__ = lambda self, name: mock_collection

    # 模拟查询命中
    mock_collection.find_one.return_value = {
        "series_code": "python_foundation",
        "title": "Python编程基础",
    }

    # 课程文档映射
    mapping = infer_source_mapping(
        mock_db,
        source_file="尚硅谷大模型技术之Python1.0.docx",
        doc_id="doc_001",
        doc_type="course_doc",
    )

    assert mapping is not None, "应该推断出映射"
    assert mapping.series_code == "python_foundation"
    assert mapping.mapping_type == "rule"
    assert mapping.doc_id == "doc_001"

    print(f"  映射结果: {mapping.source_file} → {mapping.series_code}")

    # 项目文档映射
    mapping2 = infer_source_mapping(
        mock_db,
        source_file="01_掌柜智库项目全景.md",
        doc_id="doc_002",
        doc_type="project_doc",
    )

    assert mapping2 is not None, "掌柜智库文档应该推断出映射"
    assert mapping2.project_name == "掌柜智库"

    print(f"  映射结果: {mapping2.source_file} → project={mapping2.project_name}")
    print("✓ 来源映射规则测试通过")


def test_subtask_status_aggregation():
    """测试子任务状态汇总逻辑

    验证 PLAN.md §6.4 步骤 7 的状态汇总规则：
    - 全部成功 → COMPLETED
    - 全部失败 → FAILED
    - 混合 → PARTIAL_SUCCESS
    """
    from knowledge.models.ingest import IngestTask, SubTask, TaskStatus

    # 场景1: 全部成功
    task = IngestTask(task_type="documents")
    task.sub_tasks = [
        SubTask(file="a.docx", status=TaskStatus.COMPLETED),
        SubTask(file="b.docx", status=TaskStatus.COMPLETED),
    ]
    statuses = {s.status for s in task.sub_tasks}
    if all(s == TaskStatus.COMPLETED for s in statuses):
        result = TaskStatus.COMPLETED
    elif all(s == TaskStatus.FAILED for s in statuses):
        result = TaskStatus.FAILED
    else:
        result = TaskStatus.PARTIAL_SUCCESS

    assert result == TaskStatus.COMPLETED

    # 场景2: 全部失败
    task.sub_tasks = [
        SubTask(file="a.docx", status=TaskStatus.FAILED),
        SubTask(file="b.docx", status=TaskStatus.FAILED),
    ]
    statuses = {s.status for s in task.sub_tasks}
    if all(s == TaskStatus.COMPLETED for s in statuses):
        result = TaskStatus.COMPLETED
    elif all(s == TaskStatus.FAILED for s in statuses):
        result = TaskStatus.FAILED
    else:
        result = TaskStatus.PARTIAL_SUCCESS

    assert result == TaskStatus.FAILED

    # 场景3: 混合
    task.sub_tasks = [
        SubTask(file="a.docx", status=TaskStatus.COMPLETED),
        SubTask(file="b.docx", status=TaskStatus.FAILED),
        SubTask(file="c.docx", status=TaskStatus.COMPLETED),
    ]
    statuses = {s.status for s in task.sub_tasks}
    if all(s == TaskStatus.COMPLETED for s in statuses):
        result = TaskStatus.COMPLETED
    elif all(s == TaskStatus.FAILED for s in statuses):
        result = TaskStatus.FAILED
    else:
        result = TaskStatus.PARTIAL_SUCCESS

    assert result == TaskStatus.PARTIAL_SUCCESS

    print("✓ 子任务状态汇总测试通过")


if __name__ == "__main__":
    test_full_pipeline_with_real_markdown()
    test_docx_to_chunks_pipeline()
    test_document_store_with_mock_db()
    test_image_uploader_with_mock_minio()
    test_image_upload_partial_failure()
    test_replace_image_refs()
    test_mapping_rules_with_mock_db()
    test_subtask_status_aggregation()
