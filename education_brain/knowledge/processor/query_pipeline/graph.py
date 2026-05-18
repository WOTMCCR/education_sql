"""查询管线 LangGraph 编排 — 对应 PLAN.md §7.5

流程：
  query_rewrite → [fan-out]
                    ├─ vector_search ─┐
                    └─ hyde_search   ─┤ → rrf_fusion → rerank → answer_generate → END

fan-out/fan-in：LangGraph 原生并行。
三路变两路：教育场景首版不做 Web MCP 搜索（PLAN.md §9）。
"""

import logging
from functools import cache

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from knowledge.core.config import get_settings
from knowledge.processor.query_pipeline.nodes.answer_generate import answer_generate
from knowledge.processor.query_pipeline.nodes.hyde_search import hyde_search
from knowledge.processor.query_pipeline.nodes.query_rewrite import query_rewrite
from knowledge.processor.query_pipeline.nodes.rerank import rerank
from knowledge.processor.query_pipeline.nodes.rrf_fusion import rrf_fusion
from knowledge.processor.query_pipeline.nodes.vector_search import vector_search
from knowledge.processor.query_pipeline.state import QueryGraphState

logger = logging.getLogger(__name__)

def _safe_node(fn, name: str):
    """容错包装 — 并行节点异常时返回空结果而非中断管线

    只用于 fan-out 的并行分支。
    单路失败不应杀死整个管线——另一路的结果仍然有价值。
    """
    def wrapper(state: QueryGraphState) -> dict:
        try:
            return fn(state)
        except Exception as e:
            logger.warning("%s 执行失败，降级为空结果: %s", name, e)
            return {}
    return wrapper

def _fan_out_router(state: QueryGraphState) -> list[str]:
    """query_rewrite 之后的路由 — 返回列表触发并行"""
    s = get_settings()
    if not s.enable_hyde or not s.openai_api_key or not s.effective_hyde_model:
        return ["vector_search"]
    return ["vector_search", "hyde_search"]

@cache
def build_query_graph() -> CompiledStateGraph:
    """构建并编译查询管线图（单例）"""
    wf = StateGraph(QueryGraphState)

    # ── 注册节点 ──
    wf.add_node("query_rewrite", query_rewrite)
    wf.add_node("vector_search", _safe_node(vector_search, "vector_search"))
    wf.add_node("hyde_search", _safe_node(hyde_search, "hyde_search"))
    wf.add_node("rrf_fusion", rrf_fusion)
    wf.add_node("rerank", rerank)
    wf.add_node("answer_generate", answer_generate)

    # ── 入口 ──
    wf.set_entry_point("query_rewrite")

    # ── fan-out：改写后两路并行检索 ──
    wf.add_conditional_edges("query_rewrite", _fan_out_router)

    # ── fan-in：两路完成 → RRF 融合 ──
    wf.add_edge("vector_search", "rrf_fusion")
    wf.add_edge("hyde_search", "rrf_fusion")

    # ── 线性：融合 → 精排 → 答案 ──
    wf.add_edge("rrf_fusion", "rerank")
    wf.add_edge("rerank", "answer_generate")
    wf.add_edge("answer_generate", END)

    return wf.compile()

# ---- 在 graph.py 末尾新增 ----

@cache
def build_retrieval_graph() -> CompiledStateGraph:
    """构建检索子图（单例） — 流式路径专用。

    与 build_query_graph() 共享所有节点定义和路由逻辑，
    唯一区别是终止于 rerank → END，不包含 answer_generate。

    这样做的好处：
    1. 同步和流式路径使用完全相同的检索节点，不会漂移
    2. 修改 query_rewrite / vector_search 等节点时，两条路径同时生效
    3. 流式路径在图结束后拿到 state["final_chunks"]，
       然后在图外面调用 answer_generate_stream() 逐 token 输出

    为什么不在 build_query_graph() 上加参数控制？
    @cache 装饰器要求参数可 hash，且两个图的生命周期一样长（都是单例），
    分开两个函数更清晰。
    """
    wf = StateGraph(QueryGraphState)

    # ── 注册节点（与完整图完全相同，除了没有 answer_generate）──
    wf.add_node("query_rewrite", query_rewrite)
    wf.add_node("vector_search", _safe_node(vector_search, "vector_search"))
    wf.add_node("hyde_search", _safe_node(hyde_search, "hyde_search"))
    wf.add_node("rrf_fusion", rrf_fusion)
    wf.add_node("rerank", rerank)

    # ── 入口 ──
    wf.set_entry_point("query_rewrite")

    # ── fan-out：改写后两路并行检索（复用同一个路由函数）──
    wf.add_conditional_edges("query_rewrite", _fan_out_router)

    # ── fan-in：两路完成 → RRF 融合 ──
    wf.add_edge("vector_search", "rrf_fusion")
    wf.add_edge("hyde_search", "rrf_fusion")

    # ── 线性：融合 → 精排 → END（这里不接 answer_generate）──
    wf.add_edge("rrf_fusion", "rerank")
    wf.add_edge("rerank", END)

    return wf.compile()
