# knowledge/models/ingest.py
"""导入任务模型 — 对应 PLAN.md §5.4 ingest_task"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

# 既是枚举成员（可以做 == 比较），又是字符串（序列化到 JSON/MongoDB 时自动变成 "running"，不需要手动 .value
class TaskStatus(str , Enum): 
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"

class ProgressLog(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""

class SubTask(BaseModel):
    file: str = ""
    status: TaskStatus = TaskStatus.PENDING
    error: str = ""
    chunks: int = 0


class IngestTask(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    task_type: str  # "catalog" | "questions" | "documents"
    status: TaskStatus = TaskStatus.PENDING
    sub_tasks: list[SubTask] = Field(default_factory=list)
    progress_logs: list[ProgressLog] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 结果统计
    series_count: int = 0
    module_count: int = 0
    question_count: int = 0
    warning_count: int = 0

    def add_log(self, message: str):
        self.progress_logs.append(ProgressLog(message=message))
        self.updated_at = datetime.now(timezone.utc)