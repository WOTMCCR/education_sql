from __future__ import annotations

import re
from typing import Any

from knowledge.analytics.meta_store import mysql_dict_connection


RESERVED_TABLES = {"order"}
FORBIDDEN_SQL_TOKENS = {
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DROP",
    "EXEC",
    "GRANT",
    "INTO",
    "INSERT",
    "LOAD",
    "LOCK",
    "OUTFILE",
    "REPLACE",
    "REVOKE",
    "SET",
    "TRUNCATE",
    "UNLOCK",
    "UPDATE",
    "USE",
    "DUMPFILE",
}
FORBIDDEN_SQL_FUNCTIONS = {
    "GET_LOCK",
    "IS_FREE_LOCK",
    "IS_USED_LOCK",
    "MASTER_POS_WAIT",
    "RELEASE_ALL_LOCKS",
    "RELEASE_LOCK",
    "SLEEP",
    "UUID_SHORT",
}


def quote_table(table_name: str) -> str:
    if table_name in RESERVED_TABLES:
        return f"`{table_name}`"
    return table_name


def sql_field(full_name: str) -> str:
    table_name, column_name = full_name.split(".", 1)
    return f"{quote_table(table_name)}.{column_name}"


def render_join(edge: dict[str, Any], joined: set[str]) -> tuple[str, str] | None:
    left = edge["left_table"]
    right = edge["right_table"]
    if left in joined and right not in joined:
        joined.add(right)
        return (
            f"JOIN {quote_table(right)} ON "
            f"{quote_table(left)}.{edge['left_column']} = {quote_table(right)}.{edge['right_column']}",
            right,
        )
    if right in joined and left not in joined:
        joined.add(left)
        return (
            f"JOIN {quote_table(left)} ON "
            f"{quote_table(left)}.{edge['left_column']} = {quote_table(right)}.{edge['right_column']}",
            left,
        )
    return None


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n\r]*", " ", sql)
    sql = re.sub(r"#[^\n\r]*", " ", sql)
    return sql


def contains_sql_comment(sql: str) -> bool:
    return "/*" in sql or "*/" in sql or "--" in sql or "#" in sql


def is_safe_select_sql(sql: str) -> bool:
    if contains_sql_comment(sql):
        return False
    normalized = strip_sql_comments(sql).strip()
    if not normalized:
        return False
    if ";" in normalized:
        return False
    if not re.match(r"^\s*SELECT\b", normalized, flags=re.I):
        return False
    tokens = {token.upper() for token in re.findall(r"\b[A-Za-z_]+\b", normalized)}
    if tokens & FORBIDDEN_SQL_TOKENS:
        return False
    function_names = {name.upper() for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", normalized)}
    return not (function_names & FORBIDDEN_SQL_FUNCTIONS)


def ensure_default_limit(sql: str, limit: int = 1000) -> str:
    """Append a conservative LIMIT for non-aggregate detail SELECT statements."""
    normalized = strip_sql_comments(sql).strip()
    if re.search(r"\bLIMIT\s+\d+\b", normalized, flags=re.I):
        return sql
    if re.search(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", normalized, flags=re.I):
        return sql
    return f"{sql.rstrip()} LIMIT {limit}"


def question_contains_dangerous_sql(question: str) -> bool:
    if ";" in question or "/*" in question or "--" in question or "#" in question:
        return True
    tokens = {token.upper() for token in re.findall(r"\b[A-Za-z_]+\b", question)}
    return bool(tokens & FORBIDDEN_SQL_TOKENS)


def explain_sql(sql: str) -> None:
    if not is_safe_select_sql(sql):
        raise ValueError("Unsafe SQL cannot be explained")
    connection = mysql_dict_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN {sql}")
            cursor.fetchall()
    finally:
        connection.close()


def execute_select(sql: str) -> list[dict[str, Any]]:
    if not is_safe_select_sql(sql):
        raise ValueError("Unsafe SQL cannot be executed")
    connection = mysql_dict_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(sql)
            rows = list(cursor.fetchall())
            connection.commit()
            return rows
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
