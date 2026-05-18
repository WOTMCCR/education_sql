"""聊天数据模型。"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ChatMode = Literal["data_qa", "meta_qa"]


class ChatRequest(BaseModel):
    query: str
    mode: str = ""
    session_id: str = ""


class ChatResponse(BaseModel):
    """统一聊天返回结构。"""

    task_id: str
    intent: str
    result_type: str
    mode: ChatMode
    items: list[dict] = Field(default_factory=list)
    summary: str = ""
    answer: str = ""
    citations: list[dict] = Field(default_factory=list)
    blocks: list[dict] | None = None


class ChatMessage(BaseModel):
    """单条对话消息。"""

    session_id: str
    task_id: str = ""
    role: str                       # user / assistant
    content: str
    mode: ChatMode | None = None
    result_type: str = ""
    items: list[dict] = Field(default_factory=list)
    summary: str = ""
    answer: str = ""
    citations: list[dict] = Field(default_factory=list)
    blocks: list[dict] | None = None
    intent: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
