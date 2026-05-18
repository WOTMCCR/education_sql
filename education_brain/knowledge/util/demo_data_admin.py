"""演示数据重置与重导工具。"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

import httpx

from knowledge.core.clients import get_minio, get_milvus, get_mongo_db
from knowledge.core.config import get_settings

MONGO_DEMO_COLLECTIONS = [
    "knowledge_document",
    "knowledge_chunk",
    "source_mapping",
    "ingest_task",
    "course_series",
    "course_module",
    "question_bank",
    "question_item",
]

MINIO_DOCUMENTS_PREFIX = "documents/"


@dataclass(frozen=True)
class ReimportJob:
    name: str
    path: str
    payload: dict


REIMPORT_JOBS = [
    ReimportJob(name="catalog", path="/ingest/catalog", payload={}),
    ReimportJob(name="questions", path="/ingest/questions", payload={}),
    ReimportJob(name="course_doc", path="/ingest/documents", payload={"doc_type": "course_doc"}),
    ReimportJob(name="project_doc", path="/ingest/documents", payload={"doc_type": "project_doc"}),
]


def reset_demo_data(*, include_minio: bool) -> dict:
    """清理全量演示数据。"""
    db = get_mongo_db()
    dropped_mongo: list[str] = []
    for name in MONGO_DEMO_COLLECTIONS:
        db[name].drop()
        dropped_mongo.append(name)

    settings = get_settings()
    milvus = get_milvus()
    milvus_dropped = False
    if milvus.has_collection(settings.milvus_collection):
        milvus.drop_collection(settings.milvus_collection)
        milvus_dropped = True

    minio_removed = 0
    if include_minio:
        minio = get_minio()
        if minio.bucket_exists(settings.minio_bucket):
            objects = list(
                minio.list_objects(
                    settings.minio_bucket,
                    prefix=MINIO_DOCUMENTS_PREFIX,
                    recursive=True,
                )
            )
            for obj in objects:
                minio.remove_object(settings.minio_bucket, obj.object_name)
            minio_removed = len(objects)

    return {
        "mongo_dropped": dropped_mongo,
        "milvus_collection": settings.milvus_collection,
        "milvus_dropped": milvus_dropped,
        "minio_removed": minio_removed,
        "minio_prefix": MINIO_DOCUMENTS_PREFIX,
    }


def _normalize_api_base_url(api_base_url: str) -> str:
    return api_base_url.rstrip("/")


def _submit_job(*, client: httpx.Client, api_base_url: str, job: ReimportJob) -> str:
    response = client.post(f"{api_base_url}{job.path}", json=job.payload)
    response.raise_for_status()
    payload = response.json()
    task_id = payload.get("task_id", "")
    if not task_id:
        raise RuntimeError(f"{job.name} 未返回 task_id")
    return str(task_id)


def _poll_task_until_terminal(
    *,
    client: httpx.Client,
    api_base_url: str,
    task_id: str,
    poll_interval: float,
    timeout_seconds: float,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"{api_base_url}/ingest/tasks/{task_id}")
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", ""))
        if status in {"completed", "partial_success", "failed"}:
            return payload
        time.sleep(poll_interval)
    raise RuntimeError(f"任务超时: {task_id}")


def run_reimport_sequence(
    *,
    api_base_url: str,
    client: httpx.Client | None = None,
    poll_interval: float = 1.5,
    timeout_seconds: float = 1800,
) -> list[dict]:
    """按固定顺序重新导入全量演示数据。"""
    base_url = _normalize_api_base_url(api_base_url)
    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)

    results: list[dict] = []
    try:
        for job in REIMPORT_JOBS:
            task_id = _submit_job(client=client, api_base_url=base_url, job=job)
            task_payload = _poll_task_until_terminal(
                client=client,
                api_base_url=base_url,
                task_id=task_id,
                poll_interval=poll_interval,
                timeout_seconds=timeout_seconds,
            )
            status = str(task_payload.get("status", ""))
            if status != "completed":
                raise RuntimeError(f"{job.name} 导入未成功完成: status={status}, task_id={task_id}")
            results.append(
                {
                    "name": job.name,
                    "task_id": task_id,
                    "status": status,
                }
            )
        return results
    finally:
        if own_client and hasattr(client, "close"):
            client.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示数据清理 / 重导工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reset_parser = subparsers.add_parser("reset", help="清理全量演示数据")
    reset_parser.add_argument(
        "--include-minio",
        action="store_true",
        help="同时清理 MinIO documents/ 前缀",
    )
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="确认执行破坏性清理操作",
    )

    reimport_parser = subparsers.add_parser("reimport", help="按固定顺序重新导入全量演示数据")
    reimport_parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000",
        help="后端 API 基地址",
    )
    reimport_parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.5,
        help="轮询间隔秒数",
    )
    reimport_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1800,
        help="单个导入任务超时时间",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "reset":
        if not args.yes:
            parser.error("reset 是破坏性操作，必须显式传入 --yes")
        summary = reset_demo_data(include_minio=args.include_minio)
        print("reset completed")
        print(f"mongo dropped: {', '.join(summary['mongo_dropped'])}")
        if summary["milvus_dropped"]:
            print(f"milvus dropped: {summary['milvus_collection']}")
        else:
            print(f"milvus not found: {summary['milvus_collection']}")
        if args.include_minio:
            print(f"minio removed: {summary['minio_removed']} objects from {summary['minio_prefix']}")
        return 0

    results = run_reimport_sequence(
        api_base_url=args.api_base_url,
        poll_interval=args.poll_interval,
        timeout_seconds=args.timeout_seconds,
    )
    print("reimport completed")
    for item in results:
        print(f"{item['name']}: task_id={item['task_id']} status={item['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
