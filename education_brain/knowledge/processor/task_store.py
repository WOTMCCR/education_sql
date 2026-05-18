"""导入任务状态管理 — 对应 PLAN.md §5.4 / §6.2 步骤2,5"""
from knowledge.core.clients import get_mongo_db
from knowledge.models.ingest import IngestTask, TaskStatus

COLLECTION = "ingest_task"

def create_task(task : IngestTask) -> str:
    db = get_mongo_db()
    db[COLLECTION].insert_one(task.model_dump())
    return task.task_id

def update_task(task : IngestTask) -> None:
    db = get_mongo_db()
    db[COLLECTION].update_one(
        {"task_id": task.task_id},
        {"$set": task.model_dump()},
    )

def get_task(task_id: str) -> dict | None:
    db = get_mongo_db()
    doc = db[COLLECTION].find_one(
        {"task_id": task_id}, 
        {"_id": 0}
    )
    return doc