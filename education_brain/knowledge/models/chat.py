"""聊天数据模型。"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ChatMode = Literal["data_qa", "meta_qa"]
MetaCitationKind = Literal["metric", "column", "table", "dimension", "join", "value"]
MetaCitationSource = Literal[
    "meta_metric_info",
    "meta_column_info",
    "meta_table_info",
    "meta_dimension_info",
    "meta_join_info",
]


class MetaCitation(BaseModel):
    kind: MetaCitationKind
    id: str
    name: str
    source: MetaCitationSource
    description: str = ""


class MetaQaResponse(BaseModel):
    answer_markdown: str
    citations: list[MetaCitation] = Field(default_factory=list)
    unsupported_reason: str = ""
    suggested_mode: ChatMode = "meta_qa"
    trace_summary: dict = Field(default_factory=dict)


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
    trace: dict | None = None
    thread_id: str = ""
    checkpoint_id: str = ""
    graph_name: str = ""


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
    trace: dict | None = None
    intent: str = ""
    thread_id: str = ""
    checkpoint_id: str = ""
    graph_name: str = ""
    graph_run_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
