from __future__ import annotations

import json
import hashlib
import math
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
import pymysql
import yaml
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from knowledge.core.clients import get_analytics_mysql_connection
from knowledge.core.config import get_settings


META_TABLE_DDL = [
    """
    CREATE TABLE IF NOT EXISTS meta_table_info (
        table_name VARCHAR(128) PRIMARY KEY,
        domain_name VARCHAR(128) NULL,
        business_name VARCHAR(255) NULL,
        description TEXT NULL,
        aliases_json JSON NULL,
        row_count BIGINT NULL,
        enabled TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数表元信息'
    """,
    """
    CREATE TABLE IF NOT EXISTS meta_column_info (
        full_name VARCHAR(255) PRIMARY KEY,
        table_name VARCHAR(128) NOT NULL,
        column_name VARCHAR(128) NOT NULL,
        ordinal_position INT NOT NULL,
        data_type VARCHAR(128) NOT NULL,
        column_type VARCHAR(255) NOT NULL,
        is_nullable TINYINT NOT NULL DEFAULT 1,
        column_key VARCHAR(32) NULL,
        description TEXT NULL,
        business_role VARCHAR(64) NULL,
        aliases_json JSON NULL,
        enum_values_json JSON NULL,
        is_metric_candidate TINYINT NOT NULL DEFAULT 0,
        is_dimension_candidate TINYINT NOT NULL DEFAULT 0,
        enabled TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_meta_column_table (table_name),
        KEY idx_meta_column_column (column_name)
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数字段元信息'
    """,
    """
    CREATE TABLE IF NOT EXISTS meta_metric_info (
        metric_id VARCHAR(128) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT NULL,
        metric_type VARCHAR(64) NOT NULL DEFAULT 'aggregate',
        formula TEXT NOT NULL,
        base_table VARCHAR(128) NOT NULL,
        time_column VARCHAR(255) NULL,
        unit VARCHAR(64) NULL,
        default_filters_json JSON NULL,
        allowed_dimensions_json JSON NULL,
        relevant_columns_json JSON NULL,
        aliases_json JSON NULL,
        enabled TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_meta_metric_base_table (base_table)
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数指标元信息'
    """,
    """
    CREATE TABLE IF NOT EXISTS meta_column_metric (
        metric_id VARCHAR(128) NOT NULL,
        full_name VARCHAR(255) NOT NULL,
        relation_type VARCHAR(64) NOT NULL DEFAULT 'relevant',
        weight DECIMAL(8, 4) NOT NULL DEFAULT 1,
        description TEXT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (metric_id, full_name),
        CONSTRAINT fk_meta_column_metric_metric FOREIGN KEY (
            metric_id
        ) REFERENCES meta_metric_info (metric_id)
        ON DELETE CASCADE,
        CONSTRAINT fk_meta_column_metric_column FOREIGN KEY (
            full_name
        ) REFERENCES meta_column_info (full_name)
        ON DELETE CASCADE
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数指标字段关系'
    """,
    """
    CREATE TABLE IF NOT EXISTS meta_join_info (
        join_id VARCHAR(128) PRIMARY KEY,
        left_table VARCHAR(128) NOT NULL,
        left_column VARCHAR(128) NOT NULL,
        right_table VARCHAR(128) NOT NULL,
        right_column VARCHAR(128) NOT NULL,
        join_type VARCHAR(64) NOT NULL DEFAULT 'many_to_one',
        relationship_type VARCHAR(64) NULL,
        path_group VARCHAR(128) NULL,
        description TEXT NULL,
        enabled TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_meta_join_left (left_table, left_column),
        KEY idx_meta_join_right (right_table, right_column),
        KEY idx_meta_join_group (path_group)
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数表关联路径'
    """,
    """
    CREATE TABLE IF NOT EXISTS meta_dimension_info (
        dimension_id VARCHAR(128) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        table_name VARCHAR(128) NOT NULL,
        column_name VARCHAR(128) NOT NULL,
        key_column VARCHAR(128) NULL,
        time_grain VARCHAR(32) NULL,
        value_sql TEXT NULL,
        aliases_json JSON NULL,
        enabled TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_meta_dimension_field (table_name, column_name)
    ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '问数维度元信息'
    """,
]

NAMESPACE = uuid.UUID("7ad3ce2b-639b-4c18-8894-e38c97eca084")
META_TABLES = [
    "meta_column_metric",
    "meta_dimension_info",
    "meta_join_info",
    "meta_metric_info",
    "meta_column_info",
    "meta_table_info",
]


@dataclass(frozen=True)
class TableMeta:
    table_name: str
    domain_name: str | None
    business_name: str | None
    description: str | None
    aliases: list[str]
    row_count: int


@dataclass(frozen=True)
class ColumnMeta:
    full_name: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    column_type: str
    is_nullable: bool
    column_key: str | None
    description: str | None
    business_role: str | None
    aliases: list[str]
    is_metric_candidate: bool
    is_dimension_candidate: bool


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def json_dump(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return data


def resolve_repo_path(raw: str | None, *, cwd: Path | None = None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    base = cwd or Path.cwd()
    candidate = (base / path).resolve()
    if candidate.exists():
        return candidate
    for parent in [base, *base.parents]:
        joined = (parent / path).resolve()
        if joined.exists():
            return joined
    return candidate


def readme_table_docs(readme_path: Path) -> dict[str, dict[str, Any]]:
    text = readme_path.read_text(encoding="utf-8")
    domain_by_pos: list[tuple[int, str]] = [
        (m.start(), m.group(1).strip()) for m in re.finditer(r"^###\s+(.+)$", text, re.M)
    ]
    headers = list(re.finditer(r"^####\s+`([^`]+)`\s*$", text, re.M))
    docs: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(headers):
        table = match.group(1)
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[start:end]
        desc = next((line.strip() for line in block.splitlines() if line.strip()), "")
        domain = None
        for pos, name in domain_by_pos:
            if pos < match.start():
                domain = name
            else:
                break
        columns: dict[str, str] = {}
        for col, col_desc in re.findall(r"^-\s+`([^`]+)`：(.+)$", block, re.M):
            columns[col] = col_desc.strip()
        docs[table] = {
            "domain": domain,
            "description": desc,
            "columns": columns,
        }
    return docs


def mysql_dict_connection():
    return pymysql.connect(
        **get_settings().analytics_mysql_connect_kwargs,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def fetch_business_tables(connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME AS table_name, COALESCE(TABLE_ROWS, 0) AS row_count
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME NOT LIKE 'meta\\_%'
            ORDER BY TABLE_NAME
            """
        )
        return list(cursor.fetchall())


def fetch_columns(connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                TABLE_NAME AS table_name,
                COLUMN_NAME AS column_name,
                ORDINAL_POSITION AS ordinal_position,
                DATA_TYPE AS data_type,
                COLUMN_TYPE AS column_type,
                IS_NULLABLE AS is_nullable,
                COLUMN_KEY AS column_key
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME NOT LIKE 'meta\\_%'
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """
        )
        return list(cursor.fetchall())


def build_table_meta(rows: list[dict[str, Any]], docs: dict[str, dict[str, Any]]) -> list[TableMeta]:
    result: list[TableMeta] = []
    for row in rows:
        table = row["table_name"]
        doc = docs.get(table, {})
        desc = doc.get("description")
        business_name = desc.split("，", 1)[0].replace("表", "表") if desc else table
        result.append(
            TableMeta(
                table_name=table,
                domain_name=doc.get("domain"),
                business_name=business_name,
                description=desc,
                aliases=[business_name, table] if business_name != table else [table],
                row_count=int(row.get("row_count") or 0),
            )
        )
    return result


def infer_business_role(column_name: str, data_type: str) -> str | None:
    if column_name == "id" or column_name.endswith("_id"):
        return "identifier"
    if column_name.endswith("_amount") or data_type in {"decimal", "double", "float"}:
        return "measure"
    if column_name.endswith("_at") or column_name.endswith("_date") or data_type in {"date", "datetime", "timestamp"}:
        return "time"
    if column_name.endswith("_status") or column_name.endswith("_type") or column_name.endswith("_flag"):
        return "category"
    if column_name.endswith("_name") or column_name.endswith("_code"):
        return "dimension"
    return None


def derive_aliases(column_name: str, description: str | None) -> list[str]:
    aliases = [column_name]
    if description:
        head = re.split(r"[，。；,;]", description, maxsplit=1)[0].strip()
        if head:
            aliases.append(head)
        aliases.extend(re.findall(r"“([^”]{1,20})”", description))
    return list(dict.fromkeys(aliases))


def build_column_meta(rows: list[dict[str, Any]], docs: dict[str, dict[str, Any]]) -> list[ColumnMeta]:
    result: list[ColumnMeta] = []
    for row in rows:
        table = row["table_name"]
        column = row["column_name"]
        desc = docs.get(table, {}).get("columns", {}).get(column)
        role = infer_business_role(column, row["data_type"])
        result.append(
            ColumnMeta(
                full_name=f"{table}.{column}",
                table_name=table,
                column_name=column,
                ordinal_position=int(row["ordinal_position"]),
                data_type=row["data_type"],
                column_type=row["column_type"],
                is_nullable=row["is_nullable"] == "YES",
                column_key=row.get("column_key") or None,
                description=desc,
                business_role=role,
                aliases=derive_aliases(column, desc),
                is_metric_candidate=role == "measure",
                is_dimension_candidate=role in {"category", "dimension", "time"},
            )
        )
    return result


def ensure_meta_tables(connection) -> None:
    with connection.cursor() as cursor:
        for ddl in META_TABLE_DDL:
            cursor.execute(ddl)
    connection.commit()


def clear_meta_tables(connection) -> None:
    with connection.cursor() as cursor:
        for table in META_TABLES:
            cursor.execute(f"DELETE FROM {table}")
    connection.commit()


def insert_meta_tables(connection, tables: list[TableMeta]) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO meta_table_info
                (table_name, domain_name, business_name, description, aliases_json, row_count)
            VALUES
                (%s, %s, %s, %s, CAST(%s AS JSON), %s)
            """,
            [
                (t.table_name, t.domain_name, t.business_name, t.description, json_dump(t.aliases), t.row_count)
                for t in tables
            ],
        )
    connection.commit()


def insert_meta_columns(connection, columns: list[ColumnMeta]) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO meta_column_info
                (full_name, table_name, column_name, ordinal_position, data_type, column_type,
                 is_nullable, column_key, description, business_role, aliases_json,
                 enum_values_json, is_metric_candidate, is_dimension_candidate)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON),
                 CAST(%s AS JSON), %s, %s)
            """,
            [
                (
                    c.full_name,
                    c.table_name,
                    c.column_name,
                    c.ordinal_position,
                    c.data_type,
                    c.column_type,
                    1 if c.is_nullable else 0,
                    c.column_key,
                    c.description,
                    c.business_role,
                    json_dump(c.aliases),
                    json_dump([]),
                    1 if c.is_metric_candidate else 0,
                    1 if c.is_dimension_candidate else 0,
                )
                for c in columns
            ],
        )
    connection.commit()


def insert_yaml_meta(connection, config: dict[str, Any]) -> None:
    metrics = config.get("metrics") or []
    dimensions = config.get("dimensions") or []
    joins = config.get("joins") or []
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO meta_metric_info
                (metric_id, name, description, metric_type, formula, base_table, time_column,
                 unit, default_filters_json, allowed_dimensions_json, relevant_columns_json, aliases_json)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON), CAST(%s AS JSON),
                 CAST(%s AS JSON), CAST(%s AS JSON))
            """,
            [
                (
                    m["id"],
                    m["name"],
                    m.get("description"),
                    m.get("metric_type", "aggregate"),
                    m["formula"],
                    m["base_table"],
                    m.get("time_column"),
                    m.get("unit"),
                    json_dump(m.get("default_filters")),
                    json_dump(m.get("allowed_dimensions")),
                    json_dump(m.get("relevant_columns")),
                    json_dump(m.get("aliases")),
                )
                for m in metrics
            ],
        )
        column_metric_rows = []
        for metric in metrics:
            for full_name in metric.get("relevant_columns") or []:
                column_metric_rows.append((metric["id"], full_name, "relevant", 1, None))
        if column_metric_rows:
            cursor.executemany(
                """
                INSERT INTO meta_column_metric
                    (metric_id, full_name, relation_type, weight, description)
                VALUES (%s, %s, %s, %s, %s)
                """,
                column_metric_rows,
            )
        cursor.executemany(
            """
            INSERT INTO meta_join_info
                (join_id, left_table, left_column, right_table, right_column, join_type,
                 relationship_type, path_group, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    j["id"],
                    j["left_table"],
                    j["left_column"],
                    j["right_table"],
                    j["right_column"],
                    j.get("join_type", "many_to_one"),
                    j.get("relationship_type"),
                    j.get("path_group"),
                    j.get("description"),
                )
                for j in joins
            ],
        )
        cursor.executemany(
            """
            INSERT INTO meta_dimension_info
                (dimension_id, name, table_name, column_name, key_column, time_grain, value_sql, aliases_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
            """,
            [
                (
                    d["id"],
                    d["name"],
                    d["table_name"],
                    d["column_name"],
                    d.get("key_column"),
                    d.get("time_grain"),
                    d.get("value_sql"),
                    json_dump(d.get("aliases")),
                )
                for d in dimensions
            ],
        )
    connection.commit()


def validate_config(config: dict[str, Any], columns: list[ColumnMeta], tables: list[TableMeta]) -> None:
    table_names = {t.table_name for t in tables}
    full_names = {c.full_name for c in columns}
    errors: list[str] = []
    for metric in config.get("metrics") or []:
        if metric.get("base_table") not in table_names:
            errors.append(f"metric {metric.get('id')} base_table not found: {metric.get('base_table')}")
        for key in [metric.get("time_column"), *(metric.get("relevant_columns") or [])]:
            if key and key not in full_names:
                errors.append(f"metric {metric.get('id')} column not found: {key}")
        for key in referenced_full_names(metric.get("formula")):
            if key not in full_names:
                errors.append(f"metric {metric.get('id')} formula column not found: {key}")
        for filter_expr in metric.get("default_filters") or []:
            for key in referenced_full_names(filter_expr):
                if key not in full_names:
                    errors.append(f"metric {metric.get('id')} filter column not found: {key}")
    for dim in config.get("dimensions") or []:
        table = dim.get("table_name")
        if table != "*" and table not in table_names:
            errors.append(f"dimension {dim.get('id')} table not found: {table}")
        if table != "*" and f"{table}.{dim.get('column_name')}" not in full_names:
            errors.append(f"dimension {dim.get('id')} column not found: {table}.{dim.get('column_name')}")
    for join in config.get("joins") or []:
        left = f"{join.get('left_table')}.{join.get('left_column')}"
        right = f"{join.get('right_table')}.{join.get('right_column')}"
        if left not in full_names:
            errors.append(f"join {join.get('id')} left column not found: {left}")
        if right not in full_names:
            errors.append(f"join {join.get('id')} right column not found: {right}")
    if errors:
        raise ValueError("Invalid education_meta.yaml:\n- " + "\n- ".join(errors))


def referenced_full_names(expression: str | None) -> set[str]:
    if not expression:
        return set()
    names: set[str] = set()
    for table, column in re.findall(r"`?([A-Za-z_][A-Za-z0-9_]*)`?\.`?([A-Za-z_][A-Za-z0-9_]*)`?", expression):
        names.add(f"{table}.{column}")
    return names


def make_column_text(column: ColumnMeta) -> str:
    parts = [
        column.full_name,
        column.table_name,
        column.column_name,
        column.description or "",
        column.business_role or "",
        " ".join(column.aliases),
    ]
    return " ".join(p for p in parts if p)


def make_metric_text(metric: dict[str, Any]) -> str:
    parts = [
        metric.get("id", ""),
        metric.get("name", ""),
        metric.get("description", ""),
        metric.get("formula", ""),
        " ".join(metric.get("aliases") or []),
        " ".join(metric.get("relevant_columns") or []),
    ]
    return " ".join(p for p in parts if p)


def embed_texts(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if s.analytics_embedding_mode == "local_hash":
        return [hash_embedding(text) for text in texts]
    vectors: list[list[float]] = []
    with httpx.Client(base_url=s.analytics_embedding_url, timeout=60.0, trust_env=False) as client:
        for start in range(0, len(texts), 1):
            chunk = texts[start : start + 1]
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    response = client.post("/embed", json={"inputs": chunk})
                    response.raise_for_status()
                    vectors.extend(response.json())
                    last_error = None
                    time.sleep(0.05)
                    break
                except Exception as e:
                    last_error = e
                    time.sleep(1 + attempt)
            if last_error is not None:
                raise last_error
    return vectors


def hash_embedding(text: str, dimensions: int = 1024) -> list[float]:
    """Deterministic lexical vector fallback for emergency local smoke tests."""
    vector = [0.0] * dimensions
    tokens = [text[i : i + size] for size in (1, 2, 3) for i in range(max(0, len(text) - size + 1))]
    for token in tokens or [text]:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def recreate_qdrant_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_qdrant_points(
    client: QdrantClient,
    collection_name: str,
    entities: Iterable[dict[str, Any]],
    text_key: str = "text",
) -> int:
    entity_list = list(entities)
    if not entity_list:
        return 0
    vectors = embed_texts([e[text_key] for e in entity_list])
    points = [
        PointStruct(
            id=stable_uuid(collection_name, str(entity["id"])),
            vector=vector,
            payload={k: v for k, v in entity.items() if k != text_key},
        )
        for entity, vector in zip(entity_list, vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def build_qdrant_indexes(config: dict[str, Any], columns: list[ColumnMeta], recreate: bool) -> dict[str, int]:
    s = get_settings()
    client = QdrantClient(url=s.analytics_qdrant_url, timeout=30.0, trust_env=False)
    sample_vector = embed_texts(["教育问数字段"])[0]
    collections = config.get("collections") or {}
    column_collection = collections.get("qdrant_columns", s.analytics_qdrant_column_collection)
    metric_collection = collections.get("qdrant_metrics", s.analytics_qdrant_metric_collection)
    if recreate or not client.collection_exists(column_collection):
        recreate_qdrant_collection(client, column_collection, len(sample_vector))
    if recreate or not client.collection_exists(metric_collection):
        recreate_qdrant_collection(client, metric_collection, len(sample_vector))
    column_count = upsert_qdrant_points(
        client,
        column_collection,
        [
            {
                "id": c.full_name,
                "full_name": c.full_name,
                "table_name": c.table_name,
                "column_name": c.column_name,
                "description": c.description,
                "business_role": c.business_role,
                "text": make_column_text(c),
            }
            for c in columns
        ],
    )
    metric_count = upsert_qdrant_points(
        client,
        metric_collection,
        [
            {
                "id": m["id"],
                "metric_id": m["id"],
                "name": m["name"],
                "description": m.get("description"),
                "aliases": m.get("aliases") or [],
                "text": make_metric_text(m),
            }
            for m in config.get("metrics") or []
        ],
    )
    return {"qdrant_columns": column_count, "qdrant_metrics": metric_count}


def create_dimension_index(client: Elasticsearch, index_name: str, recreate: bool) -> None:
    if recreate and client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)
    if client.indices.exists(index=index_name):
        return
    client.indices.create(
        index=index_name,
        mappings={
            "properties": {
                "field": {"type": "keyword"},
                "dimension_id": {"type": "keyword"},
                "value_id": {"type": "keyword"},
                "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                "code": {"type": "keyword"},
                "table_name": {"type": "keyword"},
                "column_name": {"type": "keyword"},
            }
        },
    )


def build_elasticsearch_values(connection, config: dict[str, Any], recreate: bool) -> dict[str, int]:
    s = get_settings()
    index_name = (config.get("collections") or {}).get(
        "elasticsearch_values",
        s.analytics_es_dimension_values_index,
    )
    client = Elasticsearch(s.analytics_es_url, request_timeout=30.0)
    create_dimension_index(client, index_name, recreate)
    count = 0
    with connection.cursor() as cursor:
        for dimension in config.get("dimensions") or []:
            value_sql = dimension.get("value_sql")
            if not value_sql:
                continue
            cursor.execute(value_sql)
            for row in cursor.fetchall():
                doc = {
                    "field": f"{dimension['table_name']}.{dimension['column_name']}",
                    "dimension_id": dimension["id"],
                    "value_id": str(row.get("value_id") or ""),
                    "value": row.get("value"),
                    "code": row.get("code"),
                    "table_name": dimension["table_name"],
                    "column_name": dimension["column_name"],
                }
                if not doc["value"]:
                    continue
                client.index(index=index_name, id=stable_uuid(index_name, doc["field"], str(doc["value_id"]), str(doc["value"])), document=doc)
                count += 1
    client.indices.refresh(index=index_name)
    client.close()
    return {"es_dimension_values": count}


def meta_counts(connection) -> dict[str, int]:
    queries = {
        "tables": "SELECT COUNT(*) AS c FROM meta_table_info",
        "columns": "SELECT COUNT(*) AS c FROM meta_column_info",
        "metrics": "SELECT COUNT(*) AS c FROM meta_metric_info",
        "joins": "SELECT COUNT(*) AS c FROM meta_join_info",
        "dimensions": "SELECT COUNT(*) AS c FROM meta_dimension_info",
    }
    counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        for key, sql in queries.items():
            cursor.execute(sql)
            counts[key] = int(cursor.fetchone()["c"])
    return counts


def build_all(config_path: Path, recreate: bool) -> dict[str, int]:
    config = load_yaml(config_path)
    readme_path = resolve_repo_path((config.get("sources") or {}).get("readme_path"), cwd=config_path.parent)
    if readme_path is None or not readme_path.exists():
        raise FileNotFoundError(f"README source not found: {readme_path}")
    docs = readme_table_docs(readme_path)
    connection = mysql_dict_connection()
    try:
        ensure_meta_tables(connection)
        table_rows = fetch_business_tables(connection)
        column_rows = fetch_columns(connection)
        tables = build_table_meta(table_rows, docs)
        columns = build_column_meta(column_rows, docs)
        validate_config(config, columns, tables)
        clear_meta_tables(connection)
        insert_meta_tables(connection, tables)
        insert_meta_columns(connection, columns)
        insert_yaml_meta(connection, config)
        counts = meta_counts(connection)
        counts.update(build_qdrant_indexes(config, columns, recreate=recreate))
        counts.update(build_elasticsearch_values(connection, config, recreate=recreate))
        return counts
    finally:
        connection.close()


def get_counts_safe() -> dict[str, int]:
    connection = mysql_dict_connection()
    try:
        ensure_meta_tables(connection)
        return meta_counts(connection)
    finally:
        connection.close()


def mysql_like_search(table: str, query: str, limit: int) -> list[dict[str, Any]]:
    connection = mysql_dict_connection()
    try:
        with connection.cursor() as cursor:
            if table == "metrics":
                cursor.execute(
                    """
                    SELECT metric_id AS id, name, description, 0.1 AS score
                    FROM meta_metric_info
                    WHERE name LIKE %s OR description LIKE %s OR JSON_SEARCH(aliases_json, 'one', %s) IS NOT NULL
                    LIMIT %s
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT full_name AS id, full_name, table_name, column_name, description, 0.1 AS score
                    FROM meta_column_info
                    WHERE full_name LIKE %s OR description LIKE %s OR JSON_SEARCH(aliases_json, 'one', %s) IS NOT NULL
                    LIMIT %s
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                )
            return list(cursor.fetchall())
    finally:
        connection.close()
