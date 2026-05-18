"""同步聊天意图处理。

提供两类能力：
1. `/chat/query` 同步路径复用
2. 流式入口中非 `knowledge` 意图的快速结果复用
"""

from knowledge.models.chat import ChatResponse
from knowledge.service.chat_formatter import (
    build_course_search_summary,
    build_question_search_summary,
    format_answer_response,
    format_search_response,
)
from knowledge.service.course_search import search_courses
from knowledge.service.question_search import search_questions


def handle_chat_intent(
    *,
    task_id: str,
    intent_result,
    query: str,
    session_id: str,
) -> ChatResponse:
    """根据意图返回统一 ChatResponse。"""
    if intent_result.intent == "course_intro":
        summary, items, citations = handle_course(intent_result.slots)
        return format_search_response(
            task_id=task_id,
            intent=intent_result.intent,
            items=items,
            summary=summary,
            citations=citations,
        )
    if intent_result.intent == "question_search":
        summary, items, citations = handle_question(intent_result.slots)
        return format_search_response(
            task_id=task_id,
            intent=intent_result.intent,
            items=items,
            summary=summary,
            citations=citations,
        )
    answer, citations = handle_knowledge(query, session_id)
    return format_answer_response(
        task_id=task_id,
        intent=intent_result.intent,
        answer=answer,
        citations=citations,
    )


def handle_course(slots: dict[str, str]) -> tuple[str, list[dict], list[dict]]:
    """课程查询 — 走结构化路径。"""
    keyword = slots.get("keyword", "")
    results = search_courses(
        keyword=keyword,
        audience=slots.get("audience", ""),
        goal=slots.get("goal", ""),
        page=1,
        size=10,
    )
    series_list = results["items"]

    if not series_list:
        return build_course_search_summary(keyword=keyword, items=[]), [], []

    return build_course_search_summary(keyword=keyword, items=series_list), series_list, []


def handle_question(slots: dict[str, str]) -> tuple[str, list[dict], list[dict]]:
    """题目检索 — 走结构化路径。"""
    results = search_questions(
        keyword=slots.get("keyword", ""),
        bank_code=slots.get("bank_code", ""),
        question_type=slots.get("question_type", ""),
        page=1,
        size=5,
    )
    items = results["items"]

    return build_question_search_summary(
        keyword=slots.get("keyword", ""),
        question_type=slots.get("question_type", ""),
        items=items,
    ), items, []


def handle_knowledge(query: str, session_id: str) -> tuple[str, list[dict]]:
    """知识问题统一走 LangGraph 查询管线。"""
    from knowledge.processor.query_pipeline.graph import build_query_graph
    from knowledge.processor.query_pipeline.state import create_default_state
    from knowledge.service.chat_history import get_recent_messages

    history = get_recent_messages(session_id, limit=6)

    state = create_default_state(
        session_id=session_id,
        original_query=query,
        history=history,
    )

    graph = build_query_graph()
    result = graph.invoke(state)

    return result.get("answer", ""), result.get("citations", [])
