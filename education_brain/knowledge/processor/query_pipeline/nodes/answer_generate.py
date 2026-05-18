"""答案生成节点 — 对应 PLAN.md §7.5.7

将检索到的 chunk 按字符预算组装到 prompt，LLM 生成引用式回答。
"""

import logging

from knowledge.core.config import get_settings
from knowledge.core.llm import chat_completion_text
from knowledge.processor.query_pipeline.state import QueryGraphState
from knowledge.prompt.query_prompt import (
    ANSWER_FALLBACK_SYSTEM_PROMPT,
    ANSWER_FALLBACK_USER_PROMPT,
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT,
)

logger = logging.getLogger(__name__)


def answer_generate(state: QueryGraphState) -> dict:
    """LangGraph 节点：基于检索结果生成引用式回答"""
    query = state.get("original_query", "")
    chunks = state.get("final_chunks") or []

    s = get_settings()

    if not chunks:
        answer = _generate_fallback_answer(query, s)
        return {"answer": answer, "citations": []}

    # 1. 按字符预算组装上下文
    context_budget = min(s.max_context_chars, s.answer_max_context_chars)
    context, citations = _build_context(chunks, context_budget)

    # 2. LLM 生成回答
    answer = _generate_answer(query, context, s)

    return {"answer": answer, "citations": citations}

def _build_context(chunks: list[dict], max_chars: int) -> tuple[str, list[dict]]:
    """按字符预算组装上下文，返回 (context_text, citations)

    Rerank 排序靠前的 chunk 优先进入 prompt。
    超出预算的 chunk 被截断，确保不超 LLM 上下文窗口。
    """

    parts = []
    citations = []
    used_chars = 0

    for i, chunk in enumerate(chunks):
        text = chunk.get("chunk_text", "")
        if not text:
            continue

        # 预算检查
        if used_chars + len(text) > max_chars:
            remaining = max_chars - used_chars
            if remaining > 200:
                text = text[:remaining]
            else:
                break

        # 组装来源标签
        source_file = chunk.get("source_file", "未知文件")
        section = " > ".join(chunk.get("section_path", [])) or "—"
        doc_title = chunk.get("doc_title", "")
        label = f"[来源{i+1}: {doc_title or source_file} > {section}]"

        parts.append(f"{label}\n{text}")
        used_chars += len(text) + len(label) + 2

        citations.append({
            "index": i + 1,
            "chunk_id": chunk.get("chunk_id", ""),
            "doc_id": chunk.get("doc_id", ""),
            "doc_title": doc_title,
            "source_file": source_file,
            "section_path": chunk.get("section_path", []),
            "series_code": chunk.get("series_code", ""),
            "project_name": chunk.get("project_name", ""),
        })

    context = "\n\n---\n\n".join(parts)
    return context, citations

def _generate_answer(query: str, context: str, s) -> str:
    """调用 LLM 生成引用式回答"""
    if not s.openai_api_key or not s.effective_answer_model:
        return f"(LLM 未配置，以下是检索到的相关内容) \n\n{context}"
    
    answer = chat_completion_text(
        model=s.effective_answer_model,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": ANSWER_USER_PROMPT.format(
                context=context, query=query,
            )},
        ],
        purpose="答案生成",
        temperature=0.3,
        max_tokens=s.answer_max_tokens,
        timeout=s.answer_timeout_seconds,
        trigger_cooldown=False,
    )
    if answer:
        return answer
    return f"（答案生成暂时不可用，以下是检索到的相关内容）\n\n{context}"

_FALLBACK_HARDCODED = "抱歉，未找到与您问题相关的内容。请尝试换一种方式提问。"


def _generate_fallback_answer(query: str, s) -> str:
    if not s.openai_api_key or not s.effective_answer_model:
        return _FALLBACK_HARDCODED
    answer = chat_completion_text(
        model=s.effective_answer_model,
        messages=[
            {"role": "system", "content": ANSWER_FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": ANSWER_FALLBACK_USER_PROMPT.format(query=query)},
        ],
        purpose="无检索结果兜底回答",
        temperature=0.5,
        max_tokens=s.answer_max_tokens,
        trigger_cooldown=False,
    )
    return answer or _FALLBACK_HARDCODED


from collections.abc import AsyncGenerator
from knowledge.core.llm import chat_completion_stream, StreamChunk

async def answer_generate_stream(
    state: QueryGraphState,
) -> AsyncGenerator[dict, None]:
    """流式答案生成 — 非 LangGraph 节点，而是流式路径专用函数。

    与同步版 answer_generate() 的区别：

    1. answer_generate() 是 LangGraph 节点，返回 dict 更新 state
    2. answer_generate_stream() 是 async generator，yield SSE 事件 dict
    3. 两者共享 _build_context() 组装逻辑，确保上下文构建方式一致

    yield 的事件格式遵循 Step 9 SSE 协议：
    - {"event": "thinking", "data": {"text": "..."}}
    - {"event": "token",    "data": {"text": "..."}}
    - {"event": "citation", "data": {"citations": [...]}}

    注意：本函数不 yield done/error 事件。
    done 和 error 由路由层统一发出，原因：
    - done 需要携带完整拼接后的 answer
    - error 需要路由层决定是否附带 fallback_answer
    - 历史保存也在路由层做
    """
    query = state.get("original_query", "")
    chunks = state.get("final_chunks") or []
    s = get_settings()

    if not chunks:
        async for event in _stream_fallback_answer(query, s):
            yield event
        return


    # 1. 组装上下文（复用同步版的 _build_context）
    context_budget = min(s.max_context_chars, s.answer_max_context_chars)
    context, citations = _build_context(chunks, context_budget)

    # 2. 检查 LLM 是否可用
    if not s.openai_api_key or not s.effective_answer_model:
        # LLM 未配置 — 把 context 当作答案直接输出
        fallback = f"(LLM 未配置，以下是检索到的相关内容)\n\n{context}"
        yield {"event": "token", "data": {"text": fallback}}
        if citations:
            yield {"event": "citation", "data": {"citations": citations}}
        return
    
    # 3. 流式调用 LLM
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": ANSWER_USER_PROMPT.format(
            context=context, query=query,
        )},
    ]


    async for chunk in chat_completion_stream(
        model=s.effective_answer_model,
        messages=messages,
        purpose="流式答案生成",
        temperature=0.3,
        max_tokens=s.answer_max_tokens,
        timeout=s.answer_timeout_seconds,
    ):
        # StreamChunk(kind, text) → SSE event dict
        if chunk.kind == "thinking":
            yield {"event": "thinking", "data": {"text": chunk.text}}
        elif chunk.kind == "content":
            yield {"event": "token", "data": {"text": chunk.text}}

    # 4. 正文结束后推送引用
    if citations:
        yield {"event": "citation", "data": {"citations": citations}}


async def _stream_fallback_answer(
    query: str, s,
) -> AsyncGenerator[dict, None]:
    if not s.openai_api_key or not s.effective_answer_model:
        yield {"event": "token", "data": {"text": _FALLBACK_HARDCODED}}
        return

    async for chunk in chat_completion_stream(
        model=s.effective_answer_model,
        messages=[
            {"role": "system", "content": ANSWER_FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": ANSWER_FALLBACK_USER_PROMPT.format(query=query)},
        ],
        purpose="无检索结果兜底流式回答",
        temperature=0.5,
        max_tokens=s.answer_max_tokens,
        timeout=s.answer_timeout_seconds,
    ):
        if chunk.kind == "thinking":
            yield {"event": "thinking", "data": {"text": chunk.text}}
        elif chunk.kind == "content":
            yield {"event": "token", "data": {"text": chunk.text}}