from __future__ import annotations

from functools import cache
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from knowledge.core.config import get_settings


@cache
def get_graph_checkpointer() -> Any:
    settings = get_settings()
    backend = (settings.graph_checkpoint_backend or "memory").lower()
    if backend == "none":
        return None
    if backend == "mongodb":
        try:
            from langgraph.checkpoint.mongodb import MongoDBSaver  # type: ignore
        except Exception:
            try:
                from langgraph.checkpoint.pymongo import MongoDBSaver  # type: ignore
            except Exception:
                return InMemorySaver()
        db_name = settings.graph_checkpoint_db or settings.mongo_db
        return MongoDBSaver.from_conn_string(settings.mongo_uri, db_name)
    return InMemorySaver()
