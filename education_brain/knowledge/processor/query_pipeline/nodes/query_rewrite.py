"""查询改写节点 — 对应 PLAN.md §7.5.1

两个职责：
1. 指代消解：「它怎么做反向传播」→ 从历史找到「它」指代的框架
2. 口语→检索：「Python 怎么连数据库」→「Python MySQL 数据库连接 pymysql」
"""
import logging

from knowledge.core.config import get_settings
from knowledge.core.llm import chat_completion_text
from knowledge.prompt.query_prompt import REWRITE_SYSTEM_PROMPT, REWRITE_USER_PROMPT
from knowledge.processor.query_pipeline.state import QueryGraphState

logger = logging.getLogger(__name__)

def query_rewrite(state: QueryGraphState) -> dict:
    """LangGraph 节点：改写查询"""
    query = state.get("original_query" , "")
    history = state.get("history" , [])

    if not query:
        return {"rewritten_query": query}
    
    # 无历史 + 短查询：不需要改写
    if not history and len(query) < 20:
        return {"rewritten_query": query}
    
    s = get_settings()
    if not s.openai_api_key or not s.llm_model:
        return {"rewritten_query": query}
    

    history_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in history[-6:]
    ) if history else "（无历史）"

    rewritten = chat_completion_text(
        model=s.llm_model,
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": REWRITE_USER_PROMPT.format(
                history=history_text, query=query,
            )},
        ],
        purpose="查询改写",
        temperature=0.1,
        max_tokens=200,
        trigger_cooldown=False,
    )
    if rewritten:
        logger.info("查询改写: %r → %r", query[:30], rewritten[:50])
        return {"rewritten_query": rewritten}
    
    return {"rewritten_query": query}
