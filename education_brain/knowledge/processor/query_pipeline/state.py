"""
查询管线状态定义 — 对应 PLAN.md §7.5

所有查询节点通过 state dict 传递数据。
TypedDict 提供类型提示,LangGraph 负责合并。

Annotated Reducer:
  并行节点(向量检索 + HyDE)写同一类字段时,
  Reducer 告诉 LangGraph "追加合并"而非"后写覆盖"。
"""

import copy
from typing import Annotated, TypedDict

def _merge_list(existing: list, new: list) -> list:
    """列表合并 Reducer — 追加而非覆盖

    LangGraph fan-out 中多个并行节点写同一个 key 时，
    默认行为是"后写覆盖前写"。Reducer 让它变成"追加"。
    """
    return (existing or []) + (new or [])

class QueryGraphState(TypedDict, total=False):
    """查询管线状态 — 字段按流转顺序排列

    1. 用户输入 → 2. 意图/改写 → 3. 两路检索 → 4. 融合精排 → 5. 答案
    """

    # ── 1. 用户输入 ──
    session_id: str
    original_query: str
    history: list[dict]         # 近期对话历史

    # ── 2. 意图分类 + 查询改写 ──
    intent: str                 # course_intro / question_search / knowledge
    rewritten_query: str

    # ── 3. 两路检索结果（Reducer 合并） ──
    embedding_chunks: Annotated[list[dict], _merge_list]
    hyde_chunks: Annotated[list[dict], _merge_list]

    # ── 4. 融合与精排 ──
    rrf_chunks: list[dict]
    final_chunks: list[dict]    # Rerank 后的最终结果

    # ── 5. 输出 ──
    answer: str
    citations: list[dict]

_DEFAULT_STATE: QueryGraphState = {
    "session_id": "",
    "original_query": "",
    "history": [],
    "intent": "",
    "rewritten_query": "",
    "embedding_chunks": [],
    "hyde_chunks": [],
    "rrf_chunks": [],
    "final_chunks": [],
    "answer": "",
    "citations": [],
}

def create_default_state(**overrides) -> QueryGraphState:
    """创建默认查询状态，支持字段覆盖"""
    state = copy.deepcopy(_DEFAULT_STATE)
    state.update(overrides)
    return state
