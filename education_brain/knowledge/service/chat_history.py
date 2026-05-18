"""对话历史服务 — 对应 PLAN.md §7.5.8

fire-and-forget 设计：保存失败不影响已返回的回答。
"""


import logging

from knowledge.core.clients import get_mongo_db
from knowledge.models.chat import ChatMessage

logger = logging.getLogger(__name__)

def save_message(msg: ChatMessage) -> None:
    """保存一条对话消息到 MongoDB"""
    try:
        db = get_mongo_db()
        db["chat_history"].insert_one(msg.model_dump())
    except Exception as e:
        logger.warning("对话历史保存失败: %s", e)

def get_recent_messages(session_id: str, limit: int = 10) -> list[dict]:
    """获取最近 N 条对话历史（用于查询改写的指代消解）"""
    if not session_id:
        return []

    try:
        db = get_mongo_db()
        cursor = (
            db["chat_history"]
            .find(
                {"session_id": session_id},
                {
                    "_id": 0,
                    "session_id": 1,
                    "task_id": 1,
                    "role": 1,
                    "content": 1,
                    "mode": 1,
                    "intent": 1,
                    "result_type": 1,
                    "items": 1,
                    "summary": 1,
                    "answer": 1,
                    "citations": 1,
                    "blocks": 1,
                    "trace": 1,
                    "created_at": 1,
                },
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        messages = list(cursor)
        messages.reverse()      # 按时间正序
        return messages
    except Exception as e:
        logger.warning("对话历史读取失败: %s", e)
        return []
