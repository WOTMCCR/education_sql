# knowledge/api/routes/search.py
"""课程查询接口 — 对应 PLAN.md §3.1 / §7.3"""

from fastapi import APIRouter, Query

from knowledge.service.course_search import search_courses as search_courses_service
from knowledge.service.question_search import search_questions as search_questions_service

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/courses")
def search_courses(
    keyword: str = Query(default="", description="关键词，匹配名称/描述/分类"),
    audience: str = Query(default="", description="适合人群筛选，如 '在校生'"),
    goal: str = Query(default="", description="学习目标筛选，如 '求职上岸'"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """
    课程查询 — 结构化路径，不走向量检索。

    支持关键词 + 人群 + 目标组合过滤。
    返回匹配的系列及其下属模块。
    """
    return search_courses_service(
        keyword=keyword,
        audience=audience,
        goal=goal,
        page=page,
        size=size,
    )

@router.get("/questions")
def search_questions(
    keyword: str = Query(default="", description="关键词，匹配题干"),
    bank_code: str = Query(default="", description="题库编码"),
    question_type: str = Query(default="", description="题型，如 '单选题'"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """题目检索 - 结构化路径
    支持按题库 , 题型 , 关键词组合过滤
    """
    return search_questions_service(
        keyword=keyword,
        bank_code=bank_code,
        question_type=question_type,
        page=page,
        size=size,
    )

@router.get("/documents")
def search_documents_api(
    query: str = Query(description="搜索文本（必填）"),
    doc_type: str = Query(default="", description="文档类型过滤: course_doc / project_doc / 空=全部"),
    limit: int = Query(default=5, ge=1, le=20, description="返回结果数量"),
):
    """文档向量检索 — Milvus 混合搜索 + MongoDB 回表

    与课程/题目检索不同，文档检索走向量路径：
    用户查询 → BGE-M3 编码 → Milvus dense+sparse 混合检索 → MongoDB 回表取全文
    """
    if not query.strip():
        return {"total": 0, "items": []}

    from knowledge.service.document_search import search_documents
    results = search_documents(query=query, doc_type=doc_type, limit=limit)

    return {
        "total": len(results),
        "query": query,
        "doc_type": doc_type or "all",
        "items": results,
    }
