from __future__ import annotations

from typing import Any

from knowledge.analytics.meta_store import find_join_path


def build_join_plan(base_table: str, target_tables: list[str]) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    seen_edges: set[str] = set()
    warnings: list[str] = []
    normalized_targets = list(dict.fromkeys([table for table in target_tables if table and table != base_table]))

    for target_table in normalized_targets:
        path = find_join_path(base_table, target_table)
        if not path:
            raise ValueError(f"无法从 {base_table} 关联到 {target_table}")
        for edge in path:
            join_id = str(edge.get("join_id") or "")
            if join_id in seen_edges:
                continue
            edges.append(edge)
            seen_edges.add(join_id)
            if edge.get("join_type") == "one_to_many":
                warnings.append(f"join {join_id} 是 one_to_many，聚合时需关注重复计数风险。")

    tables = [base_table]
    columns: list[str] = []
    for edge in edges:
        for table in (edge["left_table"], edge["right_table"]):
            if table not in tables:
                tables.append(table)
        columns.extend(
            [
                f"{edge['left_table']}.{edge['left_column']}",
                f"{edge['right_table']}.{edge['right_column']}",
            ]
        )

    return {
        "base_table": base_table,
        "target_tables": normalized_targets,
        "edges": edges,
        "tables": tables,
        "columns": list(dict.fromkeys(columns)),
        "warnings": list(dict.fromkeys(warnings)),
    }
