"""HyDE 假设文档检索节点 — 对应 PLAN.md §7.5.3

流程：Query → LLM 生成假设文档 → 拼接(Query + 假设文档) → 向量化 → 检索

假设文档不需要准确，它的价值在于把短查询「膨胀」成
与真实文档风格接近的长文本，缩小 query-doc 语义鸿沟。
"""

import logging

from knowledge.core.clients import encode_bge_queries
from knowledge.core.config import get_settings
from knowledge.core.llm import chat_completion_text
from knowledge.processor.embedder import csr_row_to_sparse_dict
from knowledge.processor.milvus_store import hybrid_search
from knowledge.processor.query_pipeline.state import QueryGraphState
from knowledge.prompt.query_prompt import HYDE_SYSTEM_PROMPT, HYDE_USER_PROMPT

logger = logging.getLogger(__name__)

def hyde_search(state: QueryGraphState) -> dict:
    """LangGraph 节点：HyDE 假设文档检索"""
    query = state.get("rewritten_query") or state.get("original_query" , "")
    if not query:
        return {"hyde_chunks": []}
    
    s = get_settings()

    # 1.生成假设文档
    hypothesis = _generate_hypothesis(query, s)

    if not hypothesis:
        logger.info("HyDE 未生成假设文档，跳过该分支")
        return {"hyde_chunks": []}

    # 2. 拼接原始查询 + 假设文档，保留关键词
    combined = f"{query}\n{hypothesis}"

    # 3. 编码 + 检索
    result = encode_bge_queries([combined]) # BGE-M3 的 encode_queries() 会给输入加特殊前缀，告诉模型「这是一个搜索意图」

    dense = result["dense"][0]
    dense_list = dense.tolist() if hasattr(dense, "tolist") else list(dense)
    sparse = csr_row_to_sparse_dict(result["sparse"], row=0)

    hits = hybrid_search(
        dense_list, sparse,
        limit=s.query_search_limit,
    )

    logger.info("HyDE 检索: hypothesis=%d字, %d 条命中", len(hypothesis), len(hits))
    return {"hyde_chunks": hits}

def _generate_hypothesis(query: str, s) -> str:
    """调用 LLM 生成假设性教学文档片段

    失败时返回空字符串 → combined 退化为原始 query → 等价于普通向量检索。
    """
    if not s.openai_api_key or not s.effective_hyde_model:
        return ""
    
    hypothesis = chat_completion_text(
        model=s.effective_hyde_model,
        messages=[
            {"role": "system", "content": HYDE_SYSTEM_PROMPT},
            {"role": "user", "content": HYDE_USER_PROMPT.format(query=query)},
        ],
        purpose="HyDE 假设文档生成",
        temperature=0.7,
        trigger_cooldown=False,
    )
    return hypothesis or ""
