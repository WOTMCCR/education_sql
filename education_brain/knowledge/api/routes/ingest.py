"""导入接口 — 对应 PLAN.md §3.1 / §6.2"""
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from knowledge.core.config import get_settings
from knowledge.models.ingest import IngestTask, TaskStatus
from knowledge.processor.task_store import create_task, get_task, update_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

# ── 文件浏览 API ──

BROWSABLE_EXTENSIONS = frozenset({
    ".md", ".docx", ".doc", ".txt", ".pdf",
    ".xlsx", ".xls", ".csv", ".json",
})


class FileEntry(BaseModel):
    name: str
    path: str
    nav_path: str
    is_dir: bool
    children_count: int = 0


class BrowseResponse(BaseModel):
    current_path: str
    parent_path: str | None
    entries: list[FileEntry]


@router.get("/browse", response_model=BrowseResponse)
def browse_files(path: str = Query("", description="相对于 data_dir 的子路径")):
    """浏览服务器端 data_dir 下的文件和文件夹

    返回的 FileEntry 中：
    - nav_path: 相对于 data_dir，用于浏览导航
    - path:     相对于 PROJECT_ROOT，用于传给导入接口
    """
    from knowledge.core.config import PROJECT_ROOT

    s = get_settings()
    data_dir = s.data_dir_path.resolve()

    if path:
        target = (data_dir / path).resolve()
    else:
        target = data_dir

    # 路径遍历保护
    if not str(target).startswith(str(data_dir)):
        raise HTTPException(403, "不允许访问 data_dir 之外的路径")

    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")

    if not target.is_dir():
        raise HTTPException(400, f"路径不是文件夹: {path}")

    entries: list[FileEntry] = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name.startswith("."):
            continue
        nav_rel = str(item.relative_to(data_dir))
        ingest_rel = str(item.relative_to(PROJECT_ROOT))
        if item.is_dir():
            children = sum(1 for c in item.iterdir() if not c.name.startswith("."))
            entries.append(FileEntry(name=item.name, path=ingest_rel, nav_path=nav_rel, is_dir=True, children_count=children))
        elif item.suffix.lower() in BROWSABLE_EXTENSIONS:
            entries.append(FileEntry(name=item.name, path=ingest_rel, nav_path=nav_rel, is_dir=False))

    parent_path = None
    if target != data_dir:
        parent_rel = target.parent.relative_to(data_dir)
        parent_path = str(parent_rel) if str(parent_rel) != "." else ""

    return BrowseResponse(
        current_path=str(target.relative_to(data_dir)) if target != data_dir else "",
        parent_path=parent_path,
        entries=entries,
    )


# 请求/响应模型
class CatalogRequest(BaseModel):
    file_path : str = ""

class IngestResponse(BaseModel):
    task_id: str


# 后台任务: 课程目录导入
def _run_catalog_ingest(task : IngestTask , file_path : Path):
    """在 backgroundTasks 中执行 , 不阻塞 HTTP 响应"""
    try:
        task.status = TaskStatus.RUNNING
        task.add_log(f"开始解析: {file_path.name}")
        update_task(task)

        # 解析
        from knowledge.processor.catalog_parser import parse_catalog
        series_list, module_list = parse_catalog(file_path)
        task.add_log(f"解析完成: {len(series_list)} 系列, {len(module_list)} 模块")

        # 写入 MongoDB
        from knowledge.core.clients import get_mongo_db
        from knowledge.processor.catalog_store import save_catalog
        s_count , m_count = save_catalog(get_mongo_db() , series_list , module_list)

        task.series_count = s_count
        task.module_count = m_count

        task.status = TaskStatus.COMPLETED
        task.add_log(f"写入完成: {s_count} 系列, {m_count} 模块")
    
    except Exception as e:
        logger.exception("课程目录导入失败")
        task.status = TaskStatus.FAILED
        task.add_log(f"导入失败: {e}")
    
    finally:
        update_task(task)

# endpoints
@router.post("/catalog", response_model=IngestResponse, status_code=202)
def ingest_catalog(req: CatalogRequest, background: BackgroundTasks):
    """导入课程目录

    POST 立即返回 task_id(HTTP 202) , 后台异步执行解析和写入 , 请求已接收，正在处理中
    客户端轮询 GET /ingest/tasks/{task_id} 查看进度。
    """
    s = get_settings()
    file_path = s.resolve_path(req.file_path) if req.file_path else s.data_dir_path / "课程介绍.md"

    if not file_path.is_file():
        raise HTTPException(400, f"文件不存在: {file_path}")
    
    task = IngestTask(task_type="catalog")
    create_task(task)

    background.add_task(_run_catalog_ingest , task , file_path)
    return IngestResponse(task_id=task.task_id)

@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """查询导入任务状态"""
    doc = get_task(task_id)
    if doc is None:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return doc

class QuestionsRequest(BaseModel):
    file_path: str = ""

def _run_questions_ingest(task : IngestTask , file_path : Path):
    try:
        task.status = TaskStatus.RUNNING
        task.add_log(f"开始解析: {file_path.name}")
        update_task(task)

        from knowledge.processor.question_parser import parse_questions
        bank_list, item_list = parse_questions(file_path)
        task.add_log(f"解析完成: {len(bank_list)} 题库, {len(item_list)} 题目")

        # 统计质量标记
        flagged = sum(1 for q in item_list if q.quality_flags)
        if flagged:
            task.add_log(f"质量标记: {flagged} 题存在标记")
            task.warning_count = flagged

        from knowledge.core.clients import get_mongo_db
        from knowledge.processor.question_store import save_questions
        b_count, q_count = save_questions(get_mongo_db(), bank_list, item_list)

        task.question_count = q_count
        task.status = TaskStatus.COMPLETED
        task.add_log(f"写入完成: {b_count} 题库, {q_count} 题目")

    except Exception as e:
        logger.exception("题库导入失败")
        task.status = TaskStatus.FAILED
        task.add_log(f"导入失败: {e}")
    finally:
        update_task(task)

@router.post("/questions", response_model=IngestResponse, status_code=202)
def ingest_questions(req: QuestionsRequest, background: BackgroundTasks):
    """导入题库"""
    s = get_settings()
    file_path = s.resolve_path(req.file_path) if req.file_path else s.data_dir_path / "题目资料.md"

    if not file_path.is_file():
        raise HTTPException(400, f"文件不存在: {file_path}")        

    task = IngestTask(task_type="questions")
    create_task(task)

    background.add_task(_run_questions_ingest , task , file_path)
    return IngestResponse(task_id=task.task_id)

# ── 文档导入请求 ──

import tempfile
from uuid import uuid4


class DocumentsRequest(BaseModel):
    """文档导入请求

    file_path: 文件路径列表（相对于 data_dir 或绝对路径）
               为空时自动扫描 data_dir 下的课程文档和项目文档
    doc_type:   文档类型 "course_doc" | "project_doc"
    """

    file_path : list[str] = []
    doc_type : str = "course_doc"

def _discover_document_files(doc_type: str) -> list[Path]:
    """
    自动发现待导入的文档文件。

    当请求未指定 file_path 时，扫描 data_dir 下的对应目录：
    - course_doc → data/数据/课程文档/*.docx
    - project_doc → data/数据/项目文档/ 下所有 .docx 和 .md
    """
    s = get_settings()
    data_dir = s.data_dir_path

    if doc_type == "course_doc":
        doc_dir = data_dir / "课程文档"
        return sorted(doc_dir.glob("*.docx")) if doc_dir.exists() else []
    else:
        # 项目文档：.docx + 递归搜索 .md
        doc_dir = data_dir / "项目文档"
        if not doc_dir.exists():
            return []
        files = list(doc_dir.glob("*.docx"))
        files.extend(doc_dir.rglob("*.md"))
        return sorted(files)

def _run_documents_ingest(task: IngestTask, files: list[Path], doc_type: str):
    """
    文档导入后台任务 — 对应 PLAN.md §6.4

    核心设计：每个文件作为独立子任务。
    1 个文件失败不影响其他文件的导入。

    流程（每个文件）：
      1. .docx → .md 转换（.md 文件跳过此步）
      2. Markdown 结构解析
      3. 智能分块
      4. 图片上传 MinIO
      5. 图片路径替换
      6. 写入 MongoDB
      7. 来源映射推断
      8. 更新子任务状态
    """
    try:
        task.status = TaskStatus.RUNNING
        task.add_log(f"开始文档导入: {len(files)} 个文件, 类型={doc_type}")
        update_task(task)

        from knowledge.core.clients import get_mongo_db
        from knowledge.models.document import KnowledgeDocument
        from knowledge.processor.chunker import chunk_document
        from knowledge.processor.document_store import (
            save_document,
            save_source_mapping,
        )
        from knowledge.processor.docx_converter import convert_docx_to_markdown
        from knowledge.processor.image_uploader import replace_image_refs, upload_images
        from knowledge.processor.mapping_rules import infer_source_mapping
        from knowledge.processor.markdown_parser import parse_markdown

        db = get_mongo_db()
        total_chunks = 0

        for i , file_path in enumerate(files):
            sub = task.sub_tasks[i]
            doc_id = uuid4().hex[:16]

            try:
                sub.status = TaskStatus.RUNNING
                task.add_log(f"[{i+1}/{len(files)}] 处理: {file_path.name}")
                update_task(task)

                # ── 步骤1: 格式统一（.docx → .md 转换）──
                with tempfile.TemporaryDirectory() as tmp_dir:
                    image_dir = Path(tmp_dir) / "images"

                    if file_path.suffix.lower() == ".docx":
                        md_text, image_paths = convert_docx_to_markdown(
                            file_path, image_dir
                        )
                    else:
                        # 原生 .md 文件直接读取
                        md_text = file_path.read_text(encoding="utf-8")
                        image_paths = []
                
                    # ── 步骤2: Markdown 结构解析 ──
                    parsed_blocks = parse_markdown(md_text)

                    # ── 步骤3: 智能分块 ──
                    chunks = chunk_document(parsed_blocks, doc_id)

                    # ── 步骤4-5: 图片上传 + 路径替换 ──
                    if image_paths:
                        path_map = upload_images(doc_id, image_paths)
                        replace_image_refs(chunks, path_map)
                        image_count = len(path_map)
                    else:
                        image_count = 0

                # ── 步骤6: 写入 MongoDB ──
                doc = KnowledgeDocument(
                    doc_id=doc_id,
                    doc_type=doc_type,
                    source_path=str(file_path),
                    source_file=file_path.name,
                    title=_extract_title(file_path, parsed_blocks),
                    chunk_count=len(chunks),
                    image_count=image_count,
                    ingest_task_id=task.task_id,
                )
                save_document(db , doc , chunks)

                # ── 步骤6.5: 向量化 + Milvus 入库 ──
                from knowledge.processor.embedder import embed_chunks
                from knowledge.processor.milvus_store import (
                    ensure_collection,
                    upsert_vectors,
                    delete_by_doc_id,
                )

                ensure_collection()
                delete_by_doc_id(doc_id)

                embedding_records = embed_chunks(chunks, doc_type)
                if embedding_records:
                    upsert_vectors(embedding_records)
                    task.add_log(
                        f"[{i+1}/{len(files)}] 向量化: "
                        f"{len(embedding_records)}/{len(chunks)} chunks"
                    )
                else:
                    task.add_log(
                        f"[{i+1}/{len(files)}] 向量化跳过: 无有效 embedding"
                    )

                 # ── 步骤7: 来源映射 ──
                mapping = infer_source_mapping(
                    db, file_path.name, doc_id, doc_type
                )

                if mapping:
                    save_source_mapping(db , mapping)
                
                # ── 步骤8: 更新子任务状态 ──
                sub.status = TaskStatus.COMPLETED
                sub.chunks = len(chunks)
                total_chunks += len(chunks)
                task.add_log(
                    f"[{i+1}/{len(files)}] 完成: {file_path.name} → {len(chunks)} chunks"
                )

            except Exception as e:
                logger.exception("文件处理失败: %s", file_path.name)
                sub.status = TaskStatus.FAILED
                sub.error = str(e)[:200]
                task.add_log(f"[{i+1}/{len(files)}] 失败: {file_path.name} — {e}")

            update_task(task)

        # ── 汇总主任务状态 ──
        statuses = {s.status for s in task.sub_tasks}
        if all(s == TaskStatus.COMPLETED for s in statuses):
            task.status = TaskStatus.COMPLETED
        elif all(s == TaskStatus.FAILED for s in statuses):
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PARTIAL_SUCCESS

        task.add_log(f"导入完成: 共 {total_chunks} chunks")
    
    except Exception as e:
        logger.exception("文档导入流程异常")
        task.status = TaskStatus.FAILED
        task.add_log(f"导入流程异常: {e}")
    finally:
        update_task(task)

def _extract_title(file_path: Path, blocks) -> str:
    """从文件名或首个标题提取文档标题"""
    for block in blocks:
        if block.kind == "heading":
            return block.content
    # 没有标题，用文件名
    return file_path.stem


DOCUMENT_EXTENSIONS = frozenset({".md", ".docx", ".doc", ".txt", ".pdf"})


def _expand_paths_to_files(paths: list[Path]) -> list[Path]:
    """将路径列表中的文件夹展开为其下所有可导入文件"""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in DOCUMENT_EXTENSIONS:
                    files.append(child)
        else:
            files.append(p)
    return files


@router.post("/documents", response_model=IngestResponse, status_code=202)
def ingest_documents(req: DocumentsRequest, background: BackgroundTasks):
    """导入课程/项目文档

    支持三种使用方式：
    1. 指定文件路径：导入指定文件
    2. 指定文件夹路径：导入文件夹下所有文档
    3. 不指定 file_path：自动扫描 data_dir 下的文件
    """
    s = get_settings()

    if req.file_path:
        raw_paths = [s.resolve_path(p) for p in req.file_path]
        missing = [p for p in raw_paths if not p.exists()]
        if missing:
            raise HTTPException(400, f"路径不存在: {[str(m) for m in missing]}")
        files = _expand_paths_to_files(raw_paths)
    else:
        files = _discover_document_files(req.doc_type)

    if not files:
        raise HTTPException(400, "未找到可导入的文档文件")

    # 创建任务 + 子任务
    from knowledge.models.ingest import SubTask
    task = IngestTask(task_type="documents")
    task.sub_tasks = [SubTask(file=f.name) for f in files]
    create_task(task)

    background.add_task(_run_documents_ingest, task, files, req.doc_type)
    return IngestResponse(task_id=task.task_id)
