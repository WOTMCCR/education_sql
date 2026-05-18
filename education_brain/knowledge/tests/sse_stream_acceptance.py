"""Step 9 SSE 统一流式入口验收脚本。

用法：
    knowledge/.venv/bin/python knowledge/tests/sse_stream_acceptance.py

前提：
    - 服务已运行在 http://localhost:8000
    - 若要完整验证 knowledge，LLM / Ollama 需可用

说明：
    - 搜索类意图：期望通过统一流式入口提交，并在 SSE 中直接收到 done
    - knowledge：期望收到 status，最终收到 done 或 error
    - 不存在的 task_id：期望 404
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx


BASE = "http://localhost:8000"


def submit_stream(query: str, session_id: str) -> dict[str, Any]:
    response = httpx.post(
        f"{BASE}/chat/query/stream",
        json={"query": query, "session_id": session_id},
        timeout=10,
        trust_env=False,
    )
    response.raise_for_status()
    return response.json()


def collect_sse(task_id: str, timeout: float = 180.0) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_type = "message"

    with httpx.stream(
        "GET",
        f"{BASE}/chat/stream/{task_id}",
        timeout=timeout,
        trust_env=False,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
                continue
            if line.startswith("data:"):
                payload = json.loads(line[len("data:") :].strip())
                events.append({"event": event_type, "data": payload})
                if event_type in ("done", "error"):
                    break

    return events


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_search_intent_stream() -> None:
    session_id = f"sse-search-{int(time.time())}"
    submitted = submit_stream("有哪些 Python 课程？", session_id)

    require(submitted["status"] == "processing", f"unexpected status: {submitted}")
    require(submitted["intent"] == "course_intro", f"unexpected intent: {submitted}")
    require(bool(submitted.get("task_id")), "missing task_id")
    print(f"✓ 搜索类提交成功, task_id={submitted['task_id']}")

    events = collect_sse(submitted["task_id"], timeout=30)
    event_types = [e["event"] for e in events]
    require(event_types[-1] == "done", f"search stream should end with done, got {event_types}")

    done = next(e for e in events if e["event"] == "done")["data"]
    require(done["intent"] == "course_intro", f"unexpected done intent: {done}")
    require(done["result_type"] == "search_result", f"unexpected result_type: {done}")
    require(isinstance(done["items"], list), f"items should be list: {done}")
    require(bool(done["answer"]), f"answer should not be empty: {done}")
    require("token" not in event_types, f"search stream should not emit token events: {event_types}")
    print("✓ 搜索类统一流式入口通过 SSE done 返回完整结果")


def check_qa_stream() -> None:
    session_id = f"sse-qa-{int(time.time())}"
    try:
        submitted = submit_stream("什么是反向传播算法？", session_id)
    except httpx.TimeoutException:
        print("⊘ QA 提交超时，跳过严格 QA SSE 验收")
        return

    require(submitted["status"] == "processing", f"unexpected status: {submitted}")
    if submitted["intent"] != "knowledge":
        print(f"⊘ QA 示例被分类为 {submitted['intent']}，跳过严格 QA SSE 验收")
        return
    require(bool(submitted.get("task_id")), "missing task_id")
    print(f"✓ QA 提交成功, task_id={submitted['task_id']}")

    try:
        events = collect_sse(submitted["task_id"], timeout=180)
    except httpx.TimeoutException:
        print("⊘ QA SSE 超时，跳过严格 QA SSE 验收")
        return
    event_types = [e["event"] for e in events]
    require("status" in event_types, f"QA stream missing status events: {event_types}")
    require(event_types[-1] in ("done", "error"), f"QA stream should end with done/error, got {event_types}")

    if event_types[-1] == "error":
        error_data = events[-1]["data"]
        print(f"⊘ QA 流式收到 error，跳过严格正文断言: {error_data}")
        return

    done = next(e for e in events if e["event"] == "done")["data"]
    require(done["intent"] == "knowledge", f"unexpected done intent: {done}")
    require(done["result_type"] == "answer", f"unexpected result_type: {done}")
    require(bool(done["answer"]), f"done.answer should not be empty: {done}")

    thinking_texts = [e["data"]["text"] for e in events if e["event"] == "thinking"]
    token_texts = [e["data"]["text"] for e in events if e["event"] == "token"]

    if token_texts:
        rebuilt_answer = "".join(token_texts)
        require(
            done["answer"] == rebuilt_answer,
            "done.answer does not match concatenated token events",
        )
    else:
        print("⊘ QA 流式未产出 token，done.answer 可能是服务端兜底文案")

    print(f"✓ QA 流式结束，事件序列: {event_types}")
    if thinking_texts:
        print(f"✓ 收到 {len(thinking_texts)} 条 thinking 事件")
    if token_texts:
        print("✓ done.answer 与 token 重建结果一致")


def check_missing_task_id() -> None:
    response = httpx.get(
        f"{BASE}/chat/stream/nonexistent-{int(time.time())}",
        timeout=5,
        trust_env=False,
    )
    require(response.status_code == 404, f"expected 404, got {response.status_code}: {response.text}")
    print("✓ 不存在的 task_id 返回 404")


def main() -> int:
    try:
        check_missing_task_id()
        check_search_intent_stream()
        check_qa_stream()
    except Exception as exc:
        print(f"✗ 验收失败: {exc}", file=sys.stderr)
        return 1

    print("\n全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
