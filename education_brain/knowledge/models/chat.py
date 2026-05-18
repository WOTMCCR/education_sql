"""对话历史数据模型 — 对应 PLAN.md §5.4"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ChatResponse(BaseModel):
    """统一聊天返回结构"""

    task_id: str
    intent: str
    result_type: str
    items: list[dict] = Field(default_factory=list)
    summary: str = ""
    answer: str = ""
    citations: list[dict] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """单条对话消息"""

    session_id: str
    task_id: str = ""
    role: str                       # user / assistant
    content: str
    result_type: str = ""
    items: list[dict] = Field(default_factory=list)
    summary: str = ""
    answer: str = ""
    citations: list[dict] = Field(default_factory=list)
    intent: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ---- 在 models/chat.py 末尾新增 ----

class StreamSubmitResponse(BaseModel):
    """POST /chat/query/stream 的返回结构。

    客户端收到此响应后，用 task_id 去 GET /chat/stream/{task_id} 消费 SSE。

    为什么单独建模型而不是复用 ChatResponse？
    ChatResponse 的 result_type/items/answer 字段对流式提交入口没有意义——
    此时答案还没开始生成。如果复用 ChatResponse，前端要处理
    "这个 ChatResponse 有时有 answer 有时没有"的分支，不如给一个语义明确的模型。
    """
    task_id: str
    intent: str
    status: str = "processing"
