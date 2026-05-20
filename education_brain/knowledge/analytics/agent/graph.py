from __future__ import annotations

from functools import cache

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from knowledge.analytics.agent.nodes.core import (
    add_extra_context_node,
    correct_sql_node,
    execute_sql_node,
    expand_search_keywords_node,
    extract_keywords_node,
    filter_metric_node,
    filter_table_node,
    generate_sql_node,
    merge_retrieved_info_node,
    recall_column_node,
    recall_metric_node,
    recall_value_node,
    structure_intent_node,
    validate_sql_node,
)
from knowledge.analytics.agent.state import DataAgentState
from knowledge.runtime.checkpointer import get_graph_checkpointer


def _recall_fan_out(_: DataAgentState) -> list[str]:
    return ["recall_column", "recall_metric", "recall_value"]


def _filter_fan_out(_: DataAgentState) -> list[str]:
    return ["filter_table", "filter_metric"]


@cache
def build_data_qa_graph() -> CompiledStateGraph:
    wf = StateGraph(DataAgentState)

    wf.add_node("extract_keywords", extract_keywords_node)
    wf.add_node("expand_search_keywords", expand_search_keywords_node)
    wf.add_node("recall_column", recall_column_node)
    wf.add_node("recall_metric", recall_metric_node)
    wf.add_node("recall_value", recall_value_node)
    wf.add_node("merge_retrieved_info", merge_retrieved_info_node)
    wf.add_node("structure_intent", structure_intent_node)
    wf.add_node("filter_table", filter_table_node)
    wf.add_node("filter_metric", filter_metric_node)
    wf.add_node("add_extra_context", add_extra_context_node)
    wf.add_node("generate_sql", generate_sql_node)
    wf.add_node("validate_sql", validate_sql_node)
    wf.add_node("correct_sql", correct_sql_node)
    wf.add_node("execute_sql", execute_sql_node)

    wf.set_entry_point("extract_keywords")
    wf.add_edge("extract_keywords", "expand_search_keywords")
    wf.add_conditional_edges("expand_search_keywords", _recall_fan_out)
    wf.add_edge("recall_column", "merge_retrieved_info")
    wf.add_edge("recall_metric", "merge_retrieved_info")
    wf.add_edge("recall_value", "merge_retrieved_info")
    wf.add_edge("merge_retrieved_info", "structure_intent")
    wf.add_conditional_edges("structure_intent", _filter_fan_out)
    wf.add_edge("filter_table", "add_extra_context")
    wf.add_edge("filter_metric", "add_extra_context")
    wf.add_edge("add_extra_context", "generate_sql")
    wf.add_edge("generate_sql", "validate_sql")
    wf.add_edge("validate_sql", "correct_sql")
    wf.add_edge("correct_sql", "execute_sql")
    wf.add_edge("execute_sql", END)

    return wf.compile(checkpointer=get_graph_checkpointer())
