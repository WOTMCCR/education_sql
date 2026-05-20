from __future__ import annotations

from functools import cache

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from knowledge.analytics.meta_qa.nodes import run_meta_qa_node
from knowledge.analytics.meta_qa.state import MetaQaState
from knowledge.runtime.checkpointer import get_graph_checkpointer


@cache
def build_meta_qa_graph() -> CompiledStateGraph:
    wf = StateGraph(MetaQaState)
    wf.add_node("run_meta_qa", run_meta_qa_node)
    wf.set_entry_point("run_meta_qa")
    wf.add_edge("run_meta_qa", END)
    return wf.compile(checkpointer=get_graph_checkpointer())
