# 答案生成 & 历史会话 & 前端对接 — 实现计划

> 状态：旧参考实现 / 非当前项目主线文档
>
> 该文档包含较早期的实现思路和分层示意，部分命名、路由和项目上下文已不对应当前仓库。

## Context

本文档是 `query-pipeline-blueprint-legacy.md` 的续篇。前置文档覆盖了查询管线的 Phase 1–6：从 `core/config.py` 扩展、`state.py` / `graph.py` 骨架、到六个查询节点（`item_name_confirm` → 三路并行检索 → `rrf_fusion` → `rerank`）以及基础 API 路由。

**前置文档已完成的部分**（本文档不再重复实现）：
- `core/config.py` 查询管线配置字段（商品名确认、向量检索、HyDE、Web MCP、RRF、Rerank）
- `prompts/query_prompt.py` 的 `ITEM_NAME_*` 和 `HYDE_*` 提示词
- `util/embedding_util.py` 稀疏向量工具
- `processor/query_pipeline/state.py` 的 `QueryGraphState` 基础版
- `processor/query_pipeline/graph.py` 的图编排骨架
- `processor/query_pipeline/nodes/` 中的六个检索节点
- `api/query_router.py` 的基础同步查询接口

**本文档新增内容**：

| 序号 | 内容 | 解决的问题 |
|------|------|-----------|
| 1 | 答案生成节点 `answer_output.py` | 将检索结果组装成提示词，调用 LLM 生成最终回答 |
| 2 | 查询侧 `QueryBaseNode` | 在 `BaseNode` 基础上加入任务追踪 + SSE 进度推送 |
| 3 | 工具层 `task_util` / `sse_util` / `mongo_history_util` | 任务状态管理、SSE 队列推送、MongoDB 历史读写 |
| 4 | 历史会话管理 | `item_name_confirm` 读取历史做指代消解，`answer_output` 统一写入 |
| 5 | Web 层重构 | `QueryService` 服务层 + 完整 `query_router`（含 SSE 端点） |
| 6 | 前端对接 | `chat.html` 实现非流式同步查询和流式 SSE 实时推送 |

**设计原则**：
- 复用 `core/` 基础设施和前置文档已有的查询节点，不重复造轮子
- 查询侧架构与导入侧对称：Router → Service → Processor
- SSE 三层解耦：`task_util` 管状态、`sse_util` 管推送、`QueryBaseNode` 负责协调
- `session_id`（会话标识，跨多轮对话）与 `task_id`（单次查询标识）分离

**用户要求**：不直接修改代码文件，在文档中逐步给出详细指引、代码和架构说明，由用户自己动手操作。

---

## 扩展后的完整架构

### 数据流全景（含答案生成）

```
用户输入 "万用表怎么测电压？"
        ↓
┌─────────────────────────────────┐
│  商品名确认 (item_name_confirm) │  ← ★ 新增：读取 MongoDB 历史做指代消解
│  • 确认 → 继续                  │
│  • 不确定 → 预设 answer 反问    │
│  • 无法识别 → 预设 answer 拒绝  │
└──────────┬──────────────────────┘
           ↓ (确认成功, fan-out)
    ┌──────┼──────────────┐
    ↓      ↓              ↓
┌────────┐ ┌──────────┐ ┌───────────┐
│向量检索 │ │HyDE 检索 │ │Web MCP    │   ← 已有，前置文档实现
│        │ │          │ │           │
└───┬────┘ └────┬─────┘ └─────┬─────┘
    └──────┬────┘             │
           ↓ (fan-in)        │
  ┌─────────────────┐        │
  │  RRF 融合        │        │
  └────────┬────────┘        │
           ↓                  ↓
  ┌────────────────────────────┐
  │  Rerank 重排序              │
  │  → final_chunks            │
  └────────┬───────────────────┘
           ↓
  ┌────────────────────────────┐
  │  ★ 答案生成 (answer_output) │  ← 本文档新增
  │  提示词组装 + 字符预算控制   │
  │  流式/非流式 LLM 调用       │
  │  MongoDB 历史写入           │
  │  SSE 进度推送               │
  └────────────────────────────┘
           ↓
     answer（最终回答）
```

### 前后端交互架构

```
┌─────────────┐                ┌────────────────────────────┐
│  chat.html  │                │     FastAPI 后端             │
│  前端页面    │                │                            │
│             │  POST /query   │  query_router.py            │
│  ┌────────┐ │ ──────────────>│  ┌────────┐                │
│  │非流式  │ │                │  │路由层  │                 │
│  │模式    │ │ <──────────────│  └────┬───┘                │
│  └────────┘ │  JSON response │       │                    │
│             │                │       ↓                    │
│  ┌────────┐ │  POST /query   │  ┌────────────┐            │
│  │流式    │ │ ──────────────>│  │query_      │            │
│  │模式    │ │  task_id 返回   │  │service.py  │            │
│  │        │ │                │  │ 服务层      │            │
│  │        │ │  GET /stream/  │  └────┬───────┘            │
│  │  SSE ◄─┤ │ ──────────────>│       │ BackgroundTasks    │
│  │  连接  │ │  text/event-   │       ↓                    │
│  │        │ │  stream        │  ┌─────────────────┐       │
│  └────────┘ │                │  │ LangGraph        │       │
│             │                │  │ query_pipeline   │       │
│             │                │  │ (所有节点)        │       │
│             │                │  └─────────────────┘       │
└─────────────┘                └────────────────────────────┘
```

> **导入侧用轮询，查询侧用 SSE，为什么不统一？** 导入流程耗时几十秒到几分钟，轮询间隔 1.5 秒足够；查询流程需要 LLM 逐字输出（几十毫秒一个 token），轮询无法满足实时性要求，必须用 SSE 长连接。

### session_id vs task_id

```
session_id：标识一个会话（多轮对话共享，存历史记录用）
  - 前端页面加载时生成一次，存 localStorage
  - 同一浏览器标签页的所有对话共用

task_id：标识一次提问（任务状态、SSE 队列、进度追踪用）
  - 每次提问后端生成新的 task_id
  - 避免同一 session 下多次查询的状态互相覆盖
```

如果不分离，同一个 session 下连续两次提问，第二次的 `_tasks_running_list` 和 `_tasks_done_list` 会覆盖第一次的数据，导致进度混乱。

---

## 实现执行计划

| Phase | 内容 | 涉及文件 |
|-------|------|---------|
| Phase 7 | 扩展基础层（config + state + prompt） | 3 个已有文件追加内容 |
| Phase 8 | 工具层（task_util + sse_util + mongo_history_util） | 3 个新文件 |
| Phase 9 | 查询侧 QueryBaseNode | 1 个新文件 |
| Phase 10 | 答案生成节点 answer_output | 1 个新文件 |
| Phase 11 | item_name_confirm 历史改造 | 1 个已有文件修改 |
| Phase 12 | Web 层（schema + service + deps + paths + router） | 5 个新文件 |
| Phase 13 | 图编排更新 graph.py | 1 个已有文件修改 |
| Phase 14 | 前端 chat.html | 1 个新文件 |
| Phase 15 | 端到端验证 | — |

## 目标目录结构（扩展后）

```
knowledge/
├── core/                              ← 已有
│   ├── config.py                      ← ★ 追加 MongoDB + 答案生成配置
│   ├── clients.py                     ← 不变
│   ├── base.py                        ← 不变
│   ├── exceptions.py                  ← 不变
│   ├── deps.py                        ← 【新建】FastAPI 依赖注入
│   └── paths.py                       ← 【新建】项目路径工具
│
├── prompts/
│   └── query_prompt.py                ← ★ 追加 ANSWER_PROMPT
│
├── processor/
│   ├── import_pipeline/               ← 不动
│   └── query_pipeline/
│       ├── state.py                   ← ★ 追加 task_id / is_stream 字段
│       ├── graph.py                   ← ★ 完整版（含 answer_output + 路由更新）
│       ├── query_base.py              ← 【新建】查询侧 BaseNode（任务追踪 + SSE）
│       └── nodes/
│           ├── item_name_confirm.py   ← ★ 改造：接入 MongoDB 历史
│           ├── answer_output.py       ← 【新建】答案生成节点
│           ├── vector_search.py       ← 不变（前置文档）
│           ├── hyde_search.py         ← 不变（前置文档）
│           ├── web_mcp_search.py      ← 不变（前置文档）
│           ├── rrf_fusion.py          ← 不变（前置文档）
│           └── rerank.py             ← 不变（前置文档）
│
├── schema/                            ← 【新建】
│   └── query_schema.py               ← 查询相关 Pydantic 模型
│
├── services/                          ← 【新建】
│   └── query_service.py              ← 查询业务服务
│
├── util/
│   ├── embedding_util.py              ← 不变
│   ├── task_util.py                   ← 【新建】任务状态管理
│   ├── sse_util.py                    ← 【新建】SSE 队列 + 生成器
│   └── mongo_history_util.py          ← 【新建】MongoDB 历史读写
│
├── api/
│   └── query_router.py                ← ★ 完整版（含 SSE 端点 + 历史端点）
│
└── front/                             ← 【新建】
    └── chat.html                      ← 前端聊天页面
```

---

## Phase 7: 扩展基础层

### 7.1 修改 knowledge/core/config.py

在现有 `Settings` 类中追加答案生成和 MongoDB 相关字段。在 `# Rerank 重排序` 段落之后、`@property` 之前添加：

```python
    # ── MongoDB 历史记录 ──
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "shopkeeper_knowledge"
    mongo_history_collection: str = "chat_history"

    # ── 答案生成 ──
    max_context_chars: int = 12000       # 提示词字符预算上限
    answer_model: str = ""               # 答案生成 LLM（默认 fallback 到 model）
    item_name_catalog_limit: int = 500   # 拉取已有商品名的上限（注入 LLM prompt）
```

> **设计要点**：
> - `max_context_chars = 12000` 约为 4000 token（中文约 3 字/token），留够 LLM 输出空间
> - `answer_model` 为空时代码中 fallback 到 `self.settings.model`，允许答案生成用不同模型（如更强的大模型）
> - `mongo_url` 默认指向本地 MongoDB，开发环境开箱即用
> - `item_name_catalog_limit` 之前在前置文档中可能已添加，如果已有则跳过

### 7.2 修改 knowledge/processor/query_pipeline/state.py

在 `QueryGraphState` 中追加三个字段。打开 `state.py`，在 `# 5.输出` 段落中追加：

```python
    # ── 5. 输出 ──
    answer: str                      # 最终回答（或拦截信息）

    # ── 6. 任务追踪（本次新增） ──
    task_id: str                     # 本次查询的唯一任务 ID（SSE / 进度追踪用）
    is_stream: bool                  # 是否流式输出（True = SSE 推送，False = 同步等待）
    prompt: str                      # 发送给 LLM 的完整提示词（调试用，不影响逻辑）
```

同时在 `_DEFAULT_STATE` 中追加：

```python
    "answer": "",

    # 新增
    "task_id": "",
    "is_stream": False,
    "prompt": "",
```

> **为什么 `task_id` 和 `is_stream` 放在 state 里？** 因为 `QueryBaseNode.__call__` 需要从 state 中读取这两个字段来决定是否推送 SSE 进度。LangGraph 的 state 是节点间唯一的通信通道。

### 7.3 修改 knowledge/prompts/query_prompt.py

在现有文件末尾追加答案生成提示词：

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 答案生成
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANSWER_PROMPT = """\
你是一个专业的商品知识问答助手。请根据以下参考内容回答用户的问题。

【参考内容】
{context}

【历史对话】
{history}

【涉及商品】
{item_names}

【用户问题】
{question}

回答要求：
1. 优先基于参考内容作答，不要编造参考中没有的信息
2. 如果参考内容不足以回答，请如实说明
3. 回答应简洁清晰，使用专业但易懂的语言
4. 如果涉及操作步骤，请分步骤说明
5. 可以引用参考内容中的来源信息（如 [source=xxx]）
"""
```

### Insight

提示词模板为什么用 `.format()` 而不是 f-string？

- **生命周期不同**: `ANSWER_PROMPT` 是模块级常量（import 时就存在），但 `{context}` 等变量要在运行时才有值。f-string 会在定义时求值 → 变量不存在就报错。
- **可复用性**: `.format()` 模板可以被多个函数调用、序列化存储、甚至从配置文件加载。f-string 绑定了定义时的作用域。
- **JSON 花括号**: 提示词模板中如果需要 JSON 示例（`{"key": "value"}`），f-string 需要 `{{'key': 'value'}}`，`.format()` 需要 `{{"key": "value"}}`。两者都需要转义，但 `.format()` 在提示词场景更常见。

### 7.4 验证 Phase 7

```bash
cd /home/ccr/dev/LearningProject/shopkeeper_brain/knowledge

# 语法检查
uv run python -m py_compile knowledge/core/config.py
uv run python -m py_compile knowledge/processor/query_pipeline/state.py
uv run python -m py_compile knowledge/prompts/query_prompt.py

# 验证新配置字段
uv run python -c "
from knowledge.core.config import get_settings
s = get_settings()
print(f'max_context_chars = {s.max_context_chars}')
print(f'mongo_url = {s.mongo_url}')
print(f'mongo_db = {s.mongo_db}')
print('Phase 7 配置加载成功')
"

# 验证新 state 字段
uv run python -c "
from knowledge.processor.query_pipeline.state import create_default_state
state = create_default_state(task_id='test_task', is_stream=True)
print(f'task_id = {state[\"task_id\"]}')
print(f'is_stream = {state[\"is_stream\"]}')
print('Phase 7 状态字段验证成功')
"
```

---

## Phase 8: 工具层

### 8.1 创建 knowledge/util/task_util.py

任务状态管理 — 纯内存字典，无外部依赖。负责记录每个 `task_id` 的运行/完成节点列表和任务状态。

```python
"""
任务追踪工具

纯状态管理 — 用模块级字典记录每个 task_id 的节点进度。
不知道 SSE 的存在，导入侧完全不受影响。

设计:
- _tasks_running_list: 正在执行的节点名列表
- _tasks_done_list: 已完成的节点名列表
- _tasks_status: 任务整体状态 (processing / completed / failed)
- _tasks_result: 任务结果存储（key-value，如 answer）

为什么用模块级字典而不是 Redis？
- 单进程单 worker 够用（FastAPI 默认 uvicorn 1 worker）
- 任务生命周期短（几秒到几十秒），不需要持久化
- 避免引入额外基础设施依赖
- 如果未来需要多 worker，换成 Redis 只需改这个文件
"""

from typing import Dict, List
from collections import defaultdict

# ── 存储结构 ──

_tasks_running_list: Dict[str, List[str]] = defaultdict(list)
_tasks_done_list: Dict[str, List[str]] = defaultdict(list)
_tasks_result: Dict[str, Dict[str, str]] = defaultdict(dict)
_tasks_status: Dict[str, str] = {}

# ── 状态常量 ──

TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# ── 节点中文名映射 ──
# key 必须和 BaseNode.name 以及 graph.py 的 add_node 名一致
# 前端 progress 事件中展示中文名

_NODE_NAME_TO_CN: Dict[str, str] = {
    # 导入侧
    "upload_file": "上传文件",
    "entry": "检查文件",
    "pdf_to_md_node": "PDF转Markdown",
    "md_img_node": "Markdown图片处理",
    "document_split_node": "文档切分",
    "item_name_recognition": "主体名称识别",
    "beg_embedding_chunks_node": "向量生成",
    "import_milvus_node": "导入向量数据库",
    "knowledge_graph_node": "导入知识图谱",
    "__end__": "处理完成",
    # 查询侧
    "item_name_confirm": "确认问题产品",
    "vector_search": "切片搜索",
    "hyde_search": "切片搜索(假设性文档)",
    "web_mcp_search": "网络搜索",
    "rrf_fusion": "倒排融合",
    "rerank": "重排序",
    "answer_output": "生成答案",
}


def _to_cn(node_name: str) -> str:
    """节点名转中文（未登记的保留英文原名）"""
    return _NODE_NAME_TO_CN.get(node_name, node_name)


# ── 运行/完成节点管理 ──

def add_running_task(task_id: str, node_name: str) -> None:
    """将节点标记为"正在运行" """
    running = _tasks_running_list[task_id]
    if node_name not in running:
        running.append(node_name)


def add_done_task(task_id: str, node_name: str) -> None:
    """将节点标记为"已完成"（从 running 移除，加入 done）"""
    if node_name in _tasks_running_list[task_id]:
        _tasks_running_list[task_id].remove(node_name)
    done = _tasks_done_list[task_id]
    if node_name not in done:
        done.append(node_name)


def get_running_task_list(task_id: str) -> List[str]:
    """获取正在运行的节点列表（中文名）"""
    return [_to_cn(n) for n in _tasks_running_list.get(task_id, [])]


def get_done_task_list(task_id: str) -> List[str]:
    """获取已完成的节点列表（中文名）"""
    return [_to_cn(n) for n in _tasks_done_list.get(task_id, [])]


# ── 任务整体状态 ──

def get_task_status(task_id: str) -> str:
    return _tasks_status.get(task_id, "")


def update_task_status(task_id: str, status_name: str) -> None:
    _tasks_status[task_id] = status_name


# ── 任务结果存储 ──

def set_task_result(task_id: str, key: str, value: str) -> None:
    """存储任务结果（如 answer）供路由层取用"""
    _tasks_result[task_id][key] = value


def get_task_result(task_id: str, key: str, default: str = "") -> str:
    """获取任务结果"""
    return _tasks_result[task_id].get(key, default)


# ── 清理 ──

def clear_task(task_id: str):
    """清理任务所有状态（防止内存泄漏）"""
    _tasks_running_list.pop(task_id, None)
    _tasks_done_list.pop(task_id, None)
    _tasks_status.pop(task_id, None)
    _tasks_result.pop(task_id, None)
```

### Insight

task_util 的三个关键设计:

1. **为什么用 `defaultdict` 而不是普通 `dict`？**
   - `_tasks_running_list[new_task_id]` 不存在时，`defaultdict(list)` 自动创建空列表，省去 `if key not in dict: dict[key] = []` 的样板代码。
   - 这是 Pythonic 的标准做法，减少边界检查。

2. **为什么 `_to_cn` 未登记的保留英文？**
   - 如果未来新增节点忘了加映射，进度条会显示英文节点名而不是崩溃。这是"优雅降级"原则。
   - 开发时看到英文名就知道要去补映射。

3. **为什么 `_tasks_result` 用 `Dict[str, Dict[str, str]]`？**
   - 外层 key 是 `task_id`，内层 key 是结果名（如 `"answer"`）。非流式模式下，`answer_output` 节点把答案写入 `_tasks_result`，路由层从中取出返回给前端。
   - 设计为通用 key-value 而不是只存 answer，方便未来扩展（如存 `final_chunks` 序列化结果）。

---

### 8.2 创建 knowledge/util/sse_util.py

SSE 队列 + 生成器 — 纯推送机制，不知道任务状态的存在。

```python
"""
SSE (Server-Sent Events) 工具

核心机制: 用 queue.Queue 解耦 "生产者"（管线节点）和 "消费者"（FastAPI SSE 响应）。

生产者侧: push_sse_event() — 管线节点或 BaseNode 调用，将事件放入队列
消费者侧: sse_generator()  — FastAPI StreamingResponse 消费，逐条推送给前端

┌──────────────┐    queue.put()    ┌──────────────┐    yield    ┌────────────┐
│  管线节点     │ ────────────────> │  Queue       │ ────────> │  前端 SSE  │
│  (后台线程)   │                  │  (线程安全)   │           │  连接      │
└──────────────┘                  └──────────────┘           └────────────┘

为什么用 queue.Queue 而不是 asyncio.Queue？
- 管线节点在后台线程中运行（BackgroundTasks），不是 async 协程
- queue.Queue 是线程安全的，跨线程通信的标准选择
- asyncio.Queue 只在同一个事件循环内安全，不适合跨线程
"""

import json
import queue
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import Request


class SSEEvent:
    """SSE 事件类型常量"""
    READY = "ready"         # 连接建立确认
    PROGRESS = "progress"   # 任务节点进度
    DELTA = "delta"         # LLM 流式输出增量（逐 token）
    FINAL = "final"         # 最终完整答案


# ── 全局 SSE 任务队列存储 ──
# Key: task_id, Value: queue.Queue
_task_stream: Dict[str, queue.Queue] = {}


def get_sse_queue(task_id: str) -> Optional[queue.Queue]:
    """获取指定任务的 SSE 队列"""
    return _task_stream.get(task_id)


def create_sse_queue(task_id: str) -> queue.Queue:
    """创建并注册一个新的 SSE 队列

    注意: 必须在后台任务启动前调用（在路由层的主线程中），
    否则 sse_generator 请求到达时队列可能还不存在。
    """
    q = queue.Queue()
    _task_stream[task_id] = q
    return q


def remove_sse_queue(task_id: str):
    """移除指定任务的队列（防止内存泄漏）"""
    _task_stream.pop(task_id, None)


def _sse_pack(event: str, data: Dict[str, Any]) -> str:
    """打包成标准 SSE 消息格式

    SSE 协议格式:
        event: <事件名>
        data: <JSON 字符串>
        (空行作为消息分隔符)

    ensure_ascii=False 保留中文原文（不转义成 \\uXXXX）
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def push_sse_event(task_id: str, event: str, data: Dict[str, Any]):
    """推送事件到 SSE 队列（生产者调用）

    如果队列不存在（非流式模式），静默跳过。
    这让调用方不需要判断是否是流式模式 — 推就完了，有队列就发，没队列就丢。
    """
    stream_queue = get_sse_queue(task_id)
    if stream_queue:
        stream_queue.put({"event": event, "data": data})


async def sse_generator(task_id: str, request: Request) -> AsyncGenerator[str, None]:
    """SSE 异步生成器 — FastAPI StreamingResponse 的内容源

    工作流程:
    1. 获取队列 → 不存在则立即结束
    2. 循环:
       a. 检测客户端是否断开
       b. 从队列取消息（1 秒超时，避免死等）
       c. 打包成 SSE 格式 yield 给前端
    3. 清理: finally 中移除队列（防止内存泄漏）

    为什么用 run_in_executor？
    - queue.Queue.get() 是同步阻塞方法
    - 如果在 async 函数中直接调用，会阻塞整个 FastAPI 事件循环
    - run_in_executor 把阻塞操作扔到线程池执行，事件循环继续处理其他请求

    为什么设 1 秒超时？
    - 不设超时则 get() 无限等待，客户端断开了也检测不到
    - 1 秒超时后回到循环顶部检查 is_disconnected()，及时退出
    """
    stream_queue = get_sse_queue(task_id)
    if stream_queue is None:
        return

    loop = asyncio.get_running_loop()
    try:
        while True:
            # 检测客户端断开（浏览器关闭标签页、刷新等）
            if await request.is_disconnected():
                break
            try:
                # run_in_executor: 在线程池中执行阻塞的 queue.get()
                # block=True, timeout=1.0: 阻塞最多 1 秒
                msg = await loop.run_in_executor(
                    None, stream_queue.get, True, 1.0
                )
            except queue.Empty:
                # 1 秒内队列为空 → 跳过，重新检查断开状态
                continue

            event = msg.get("event")
            data = msg.get("data")
            yield _sse_pack(event, data)

    except (ConnectionResetError, BrokenPipeError):
        # 客户端强行刷新或关闭标签页，TCP 管道破裂，静默退出
        return
    except asyncio.CancelledError:
        # 服务端中断，协程被取消 → 重新抛出让框架知道
        raise
    finally:
        # 无论正常结束还是异常退出，都清理队列
        remove_sse_queue(task_id)
```

### Insight

SSE 推送的三层解耦设计:

1. **`task_util.py`**（状态层）: 只管理节点的 running/done 列表和任务状态。完全不知道 SSE 的存在。导入侧可以独立使用它做任务追踪（如果需要的话）。

2. **`sse_util.py`**（推送层）: 只管理 Queue 和消息格式化。完全不知道哪些节点在运行。`push_sse_event` 是一个通用的"往队列塞消息"函数。

3. **`QueryBaseNode`**（协调层）: 是唯一同时知道两者的地方。它在节点执行前后调用 `add_running_task` / `add_done_task` 更新状态，然后调用 `push_sse_event` 推送进度。

这种解耦的好处:
- 修改进度推送格式 → 只改 `sse_util`，不动节点代码
- 修改状态管理逻辑（如换成 Redis）→ 只改 `task_util`，不动推送逻辑
- 新增进度信息（如 ETA）→ 在 `QueryBaseNode._push_progress` 中组装，两个工具层都不变

> **每次推送全量快照而非增量**: `done_list` 和 `running_list` 每次都完整推送，前端直接覆盖渲染。即使中间某条 progress 丢了，下一条也能正确显示。

---

### 8.3 创建 knowledge/util/mongo_history_util.py

MongoDB 历史记录读写 — 独立管理自己的 pymongo 连接。

```python
"""
MongoDB 历史对话读写工具

为什么 MongoDB 而不是 Milvus / Redis？
- 历史记录是文档型数据（结构灵活，字段不固定），MongoDB 天然适合
- 需要按 session_id + ts 排序查询，MongoDB 索引支持高效
- 不需要向量检索能力（这不是知识检索，是历史回放）

连接管理:
- 模块级单例 MongoClient，pymongo 内部维护连接池
- 首次调用时创建，进程生命周期内复用
"""

import time
import logging
from typing import List, Dict, Any, Optional

from knowledge.core.config import get_settings

logger = logging.getLogger(__name__)

# ── 模块级单例连接 ──

_mongo_client = None
_mongo_collection = None


def _get_collection():
    """获取 MongoDB 历史记录集合（懒加载单例）

    为什么不用 @cache？
    - pymongo.MongoClient 是有状态的连接池对象，不适合 @cache 的"多次创建无副作用"假设
    - 显式的 global + None 检查更清晰，且支持 close() 资源释放
    """
    global _mongo_client, _mongo_collection
    if _mongo_collection is not None:
        return _mongo_collection

    from pymongo import MongoClient  # 延迟导入: 不是所有环境都需要 MongoDB

    s = get_settings()
    _mongo_client = MongoClient(s.mongo_url)
    db = _mongo_client[s.mongo_db]
    _mongo_collection = db[s.mongo_history_collection]

    # 确保索引存在（幂等操作，重复调用不报错）
    _mongo_collection.create_index([("session_id", 1), ("ts", 1)])

    return _mongo_collection


# ── 写入 ──

def save_chat_message(
    session_id: str,
    role: str,
    text: str,
    rewritten_query: str = "",
    item_names: Optional[List[str]] = None,
    message_id: Optional[str] = None,
) -> None:
    """保存一条聊天记录到 MongoDB

    Args:
        session_id: 会话 ID
        role: "user" 或 "assistant"
        text: 消息内容
        rewritten_query: 重写后的查询（方便回溯）
        item_names: 关联的商品名列表
        message_id: 可选的消息 ID（外部指定时传入）
    """
    collection = _get_collection()
    doc = {
        "session_id": session_id,
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query,
        "item_names": item_names or [],
        "ts": time.time(),
    }
    if message_id:
        doc["message_id"] = message_id

    try:
        collection.insert_one(doc)
    except Exception as e:
        logger.error(f"MongoDB 写入失败: {e}")


# ── 读取 ──

def get_recent_messages(
    session_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """获取指定会话的最近 N 条消息

    按时间正序返回（最早的在前），方便直接拼接成对话上下文。

    Args:
        session_id: 会话 ID
        limit: 最多返回条数（默认 10 条 = 5 轮对话）

    Returns:
        [{"session_id": ..., "role": ..., "text": ..., "ts": ..., ...}, ...]
    """
    collection = _get_collection()
    try:
        cursor = (
            collection.find({"session_id": session_id})
            .sort("ts", -1)     # 先按时间倒序取最近 N 条
            .limit(limit)
        )
        messages = list(cursor)
        messages.reverse()      # 再反转为正序（最早在前）
        return messages
    except Exception as e:
        logger.error(f"MongoDB 读取失败: {e}")
        return []


# ── 回填 ──

def update_message_item_names(
    session_id: str,
    item_names: List[str],
) -> None:
    """回填最近一条 user 消息的 item_names

    场景: item_name_confirm 在第一轮对话中无法识别商品名（item_names=[]），
    第二轮对话通过指代消解确认了商品名。此时需要回填第一轮的记录，
    让后续历史查询能正确关联商品。

    为什么只回填最近一条 user 消息？
    - 当前轮的 user 消息最可能需要补充
    - 更早的消息在当时已经有正确的 item_names（或者确实无关）
    """
    collection = _get_collection()
    try:
        collection.update_one(
            {"session_id": session_id, "role": "user"},
            {"$set": {"item_names": item_names}},
            sort=[("ts", -1)],  # 只更新最近一条
        )
    except Exception as e:
        logger.error(f"MongoDB 回填 item_names 失败: {e}")


# ── 清理 ──

def clear_history(session_id: str) -> int:
    """清除指定会话的所有历史记录

    Returns:
        删除的记录数
    """
    collection = _get_collection()
    try:
        result = collection.delete_many({"session_id": session_id})
        return result.deleted_count
    except Exception as e:
        logger.error(f"MongoDB 清理失败: {e}")
        return 0
```

### Insight

MongoDB 历史记录的设计要点:

1. **为什么 `get_recent_messages` 先倒序取再 reverse？**
   - MongoDB 的 `sort("ts", -1).limit(10)` 会取最近 10 条（性能最优，走索引）
   - 但返回的顺序是最新在前，而对话上下文需要最早在前（先问先答）
   - `reverse()` 是 O(n) 的内存操作，n ≤ 10，代价忽略不计
   - 如果直接 `sort("ts", 1)` 再 `limit(10)`，MongoDB 会从最早的记录开始扫描，万一有上千条历史就不高效了

2. **为什么 `save_chat_message` 吞掉异常而不是抛出？**
   - 历史写入失败不应该中断查询流程 — 用户更关心得到答案
   - 日志记录了错误，运维可以排查
   - 这是"非关键路径容错"原则的体现

3. **索引设计**: `(session_id, ts)` 复合索引支持两种查询模式：
   - `find(session_id=X).sort(ts)` → 查看会话历史
   - `find(session_id=X).sort(ts, -1).limit(N)` → 取最近 N 条

### 8.4 验证 Phase 8

```bash
cd /home/ccr/dev/LearningProject/shopkeeper_brain/knowledge

# 语法检查
uv run python -m py_compile knowledge/util/task_util.py
uv run python -m py_compile knowledge/util/sse_util.py
uv run python -m py_compile knowledge/util/mongo_history_util.py

# 测试 task_util
uv run python -c "
from knowledge.util.task_util import *
task_id = 'test_001'
update_task_status(task_id, TASK_STATUS_PROCESSING)
add_running_task(task_id, 'item_name_confirm')
print(f'running: {get_running_task_list(task_id)}')
add_done_task(task_id, 'item_name_confirm')
print(f'done: {get_done_task_list(task_id)}')
print(f'running after done: {get_running_task_list(task_id)}')
set_task_result(task_id, 'answer', '测试答案')
print(f'result: {get_task_result(task_id, \"answer\")}')
clear_task(task_id)
print('Phase 8 task_util 验证成功')
"
```

---

## Phase 9: 查询侧 QueryBaseNode

### 9.1 为什么不修改 core/base.py？

`core/base.py` 的 `BaseNode` 被导入侧和查询侧共用。导入管线不需要 SSE 推送和任务追踪，如果在 `BaseNode.__call__` 中加入这些逻辑：

- 导入侧节点的 state 没有 `task_id` 字段 → 每次都走空值分支 → 无害但冗余
- 导入侧与查询侧的异常处理不同 → 查询侧需要包装为 `QueryProcessError`
- `BaseNode` 的简洁性是它的价值 — 8 行 `__call__` 一眼看完

所以采用 **继承扩展** 而非修改基类：`QueryBaseNode(BaseNode)` 覆盖 `__call__`，加入任务追踪和 SSE 推送。

### 9.2 创建 knowledge/processor/query_pipeline/query_base.py

```python
"""
查询侧节点基类

继承 core.base.BaseNode，扩展两个能力:
1. 任务追踪: 节点开始/完成时更新 running/done 列表
2. SSE 进度推送: 流式模式下将进度实时推送给前端

使用方式:
    class AnswerOutputNode(QueryBaseNode):
        name = "answer_output"
        def process(self, state): ...

    # 查询管线中的所有节点都应继承 QueryBaseNode
    # 导入管线中的节点继续使用 core.base.BaseNode
"""

import logging

from knowledge.core.base import BaseNode
from knowledge.core.exceptions import PipelineError
from knowledge.util.task_util import (
    add_running_task,
    add_done_task,
    get_task_status,
    get_done_task_list,
    get_running_task_list,
)
from knowledge.util.sse_util import push_sse_event


class QueryBaseNode(BaseNode):
    """查询侧节点基类 — BaseNode + 任务追踪 + SSE 进度推送

    覆盖 __call__ 的执行流程:
        1. 读取 state 中的 task_id 和 is_stream
        2. 标记节点为 running + 推送 progress
        3. 执行 process()
        4. 标记节点为 done + 推送 progress
        5. 异常时包装为 PipelineError（保留原始异常链）
    """

    def __call__(self, state: dict) -> dict:
        task_id = state.get("task_id", "")
        is_stream = state.get("is_stream", False)

        try:
            self.logger.info(f"--- {self.name} 开始 ---")

            # ── 标记 running + 推送进度 ──
            if task_id:
                add_running_task(task_id, self.name)
                if is_stream:
                    self._push_progress(task_id)

            result = self.process(state)

            self.logger.info(f"--- {self.name} 完成 ---")

            # ── 标记 done + 推送进度 ──
            if task_id:
                add_done_task(task_id, self.name)
                if is_stream:
                    self._push_progress(task_id)

            return result

        except Exception as e:
            self.logger.error(f"{self.name} 执行失败: {e}", exc_info=True)
            raise PipelineError(
                message=str(e), node=self.name
            ) from e

    @staticmethod
    def _push_progress(task_id: str):
        """推送当前进度快照

        每次推送全量 done_list + running_list（非增量），
        前端直接覆盖渲染 — 即使中间丢一条 progress，下一条也能正确显示。
        """
        push_sse_event(task_id, "progress", {
            "status": get_task_status(task_id),
            "done_list": get_done_task_list(task_id),
            "running_list": get_running_task_list(task_id),
        })


def setup_logging(level: int = logging.INFO):
    """统一日志配置（供 __main__ 入口使用）"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
```

### Insight

QueryBaseNode 与 BaseNode 的继承设计:

1. **为什么异常包装不同？** `BaseNode.__call__` 直接 `raise`（让原始异常冒泡），`QueryBaseNode` 包装为 `PipelineError`。原因是查询侧需要在 `query_service` 层统一 catch `PipelineError` 来更新任务状态为 `FAILED`。导入侧没有这个需求。

2. **`_push_progress` 为什么是 `@staticmethod`？** 它不依赖实例状态（不用 `self`），只需要 `task_id` 参数。定义为 staticmethod 更清晰地表达"我不需要实例"。

3. **现有查询节点需要改吗？** 前置文档中的六个查询节点（`item_name_confirm` 等）当前继承 `core.base.BaseNode`。要启用进度追踪，它们的 import 需要从 `from knowledge.core.base import BaseNode` 改为 `from knowledge.processor.query_pipeline.query_base import QueryBaseNode`，并把 `class XxxNode(BaseNode)` 改为 `class XxxNode(QueryBaseNode)`。功能代码不需要任何修改。

---

## Phase 10: 答案生成节点

### 10.1 为什么答案生成是最复杂的节点？

答案生成需要整合查询管线的**所有**上游产出：

```
 检索文档 (final_chunks)   ← rerank 输出
 历史对话 (history)        ← item_name_confirm 读取
 图谱三元组 (kg_triples)   ← 可选，知识图谱产出
 商品名 (item_names)       ← item_name_confirm 确认
 用户问题 (rewritten_query) ← item_name_confirm 重写
```

每个区块为 LLM 提供不同维度的信息：参考内容是核心证据，历史对话提供多轮上下文，商品名限定回答范围，用户问题明确回答目标。

### 10.2 字符预算控制

LLM 有输入长度限制，需要控制提示词总长度：

```python
char_budget = self.settings.max_context_chars  # 默认 12000

# 依次分配，优先级递减，前一个消耗后剩余预算传给下一个
context_str, char_budget = self._format_reranked_docs(docs, char_budget)   # 文档优先
history_str, char_budget = self._format_chat_history(history, char_budget)  # 历史次之
```

| 优先级 | 区块 | 理由 |
|--------|------|------|
| 最高 | 检索文档 | 核心参考内容，直接决定答案质量 |
| 次之 | 历史对话 | 理解多轮对话上下文 |

> **`used_chars += len(doc_entry) + 2` 中的 +2**：最后拼接时用 `"\n\n".join()`，每两篇文档之间插入两个换行符，预算计算时要把这 2 个字符也算进去。

### 10.3 实现流程

```
Step 1: 检查已有答案 → 有则直接推送（拦截/反问场景），无则进入生成流程
          │
Step 2: 格式化检索文档 + 历史对话（带字符预算）
          │
Step 3: 填充 ANSWER_PROMPT 模板
          │
Step 4: 调用 LLM（流式 stream / 非流式 invoke）
          │
Step 5: 写入 MongoDB 历史记录
          │
Step 6: 流式模式发送 FINAL 事件
```

### 10.4 创建 knowledge/processor/query_pipeline/nodes/answer_output.py

```python
"""
答案生成节点

职责:
1. 检查是否已有预设答案（item_name_confirm 拦截/反问场景）
2. 组装提示词: 检索文档 + 历史对话 + 商品名 + 用户问题（字符预算控制）
3. 调用 LLM: 流式(stream) 逐 token SSE 推送 / 非流式(invoke) 同步等待
4. 写入 MongoDB 历史记录（用户问题 + 助手回答）
5. 流式模式发送 FINAL 事件

设计原则:
- 统一在此节点写入 MongoDB，item_name_confirm 只读不写，职责清晰
- 流式/非流式由 state["is_stream"] 开关控制，共享提示词组装逻辑
"""

from typing import List, Dict, Any, Tuple

from knowledge.core.clients import get_openai
from knowledge.core.config import get_settings
from knowledge.processor.query_pipeline.query_base import QueryBaseNode
from knowledge.processor.query_pipeline.state import QueryGraphState
from knowledge.prompts.query_prompt import ANSWER_PROMPT
from knowledge.util.mongo_history_util import save_chat_message
from knowledge.util.sse_util import push_sse_event, SSEEvent
from knowledge.util.task_util import set_task_result


class AnswerOutputNode(QueryBaseNode):
    """答案生成 — 查询管线的最终出口"""

    name = "answer_output"

    def process(self, state: QueryGraphState) -> dict:
        task_id = state.get("task_id", "")
        is_stream = state.get("is_stream", False)

        # ── 1. 已有预设答案（拦截/反问） ──
        if state.get("answer"):
            self._push_existing_answer(state, task_id, is_stream)
            has_streamed = False  # 预设答案不走流式生成

        # ── 2. 无预设答案 → 组装提示词 + LLM 生成 ──
        else:
            prompt = self._build_prompt(state)
            state["prompt"] = prompt  # 调试用: 存入 state 方便排查
            self._generate_answer(prompt, state)
            has_streamed = is_stream  # 如果是流式，已经在 _stream_generate 中逐 token 推送了

        # ── 3. 写入 MongoDB 历史 ──
        self._save_history(state)

        # ── 4. 流式模式: 发送 FINAL 事件 ──
        if is_stream:
            if has_streamed:
                # 已经流式输出过 → FINAL 只发空信号，前端用已累积的 delta 文本
                push_sse_event(task_id, SSEEvent.FINAL, {})
            else:
                # 预设答案没走流式 → FINAL 携带完整答案
                push_sse_event(task_id, SSEEvent.FINAL, {
                    "answer": state.get("answer", ""),
                })

        return {"answer": state.get("answer", "")}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 私有方法
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _push_existing_answer(
        self, state: QueryGraphState, task_id: str, is_stream: bool
    ):
        """推送已存在的预设答案（拦截/反问场景）

        非流式模式: 答案存入 task_result，路由层从中取出返回前端
        流式模式: 答案在 FINAL 事件中推送（由 process 末尾处理）
        """
        if not is_stream and task_id:
            set_task_result(task_id, "answer", state.get("answer", ""))

    def _build_prompt(self, state: QueryGraphState) -> str:
        """组装完整提示词（字符预算控制）

        优先级: 检索文档 > 历史对话
        每个区块消耗预算后，剩余传给下一个区块
        """
        char_budget = self.settings.max_context_chars

        # 用户问题 + 商品名
        question = state.get("rewritten_query", state.get("original_query", ""))
        item_names = state.get("item_names") or []

        # 格式化检索文档（优先级最高，先分配预算）
        format_context_str, char_budget = self._format_reranked_docs(
            state.get("final_chunks") or [], char_budget
        )

        # 格式化历史对话（用剩余预算）
        format_history_str, char_budget = self._format_chat_history(
            state.get("history") or [], char_budget
        )

        return ANSWER_PROMPT.format(
            context=format_context_str or "暂无参考内容",
            history=format_history_str or "暂无历史对话",
            item_names="、".join(item_names) if item_names else "未指定",
            question=question,
        )

    def _format_reranked_docs(
        self, reranked_docs: List[Dict[str, Any]], char_budget: int
    ) -> Tuple[str, int]:
        """格式化重排序后的文档

        输出格式:
            [1] [source=local] [chunk_id=chunk_001] [title=操作指导] [score=5.0600]
            测量直流电压时，将旋钮转到DCV档位...

            [2] [source=web] [url=https://...] [title=电压测量指南] [score=3.9600]
            注意：测量前请确认档位与量程...

        元信息标签传给 LLM 的作用:
        - score: 帮 LLM 判断文档可信度（高分 > 低分）
        - source: 帮 LLM 判断来源类型（local > web）
        - title/url: 帮 LLM 在答案中标注引用来源
        """
        formatted_lines = []
        used_chars = 0

        for index, doc in enumerate(reranked_docs, start=1):
            content = doc.get("content", "")
            if not content:
                continue

            # 构建元数据行
            meta_parts = [f"[{index}]"]
            for meta_field, template in [
                ("source", "[source={}]"),
                ("chunk_id", "[chunk_id={}]"),
                ("url", "[url={}]"),
                ("title", "[title={}]"),
            ]:
                value = str(doc.get(meta_field, "")).strip()
                if value:
                    meta_parts.append(template.format(value))

            doc_score = doc.get("score")
            if doc_score is not None:
                meta_parts.append(f"[score={float(doc_score):.4f}]")

            # 拼接: 元数据行 + 换行 + 内容
            doc_entry = " ".join(meta_parts) + "\n" + content

            # 预算检查（+2 是 "\n\n".join 的分隔符）
            separator_usage = 2 if formatted_lines else 0
            total_usage = separator_usage + len(doc_entry)
            if used_chars + total_usage > char_budget:
                break

            formatted_lines.append(doc_entry)
            used_chars += total_usage

        return "\n\n".join(formatted_lines), char_budget - used_chars

    def _format_chat_history(
        self, history: List[Dict[str, Any]], char_budget: int
    ) -> Tuple[str, int]:
        """格式化历史对话

        输出格式:
            用户: 万用表怎么测电压？
            助手: 测量直流电压时...
            用户: 那电阻呢？
        """
        formatted_lines = []
        used_chars = 0
        role_map = {"user": "用户", "assistant": "助手"}

        for msg in history:
            role = msg.get("role", "")
            text = msg.get("text", "")
            if not text or role not in role_map:
                continue

            formatted_line = f"{role_map[role]}: {text}"

            # 预算检查（+1 是 "\n".join 的分隔符）
            separator_usage = 1 if formatted_lines else 0
            total_usage = separator_usage + len(formatted_line)
            if used_chars + total_usage > char_budget:
                break

            formatted_lines.append(formatted_line)
            used_chars += total_usage

        return "\n".join(formatted_lines), char_budget - used_chars

    def _generate_answer(self, prompt: str, state: QueryGraphState):
        """调用 LLM 生成答案（自动选择流式/非流式）"""
        client = get_openai()
        settings = get_settings()
        model = settings.answer_model or settings.model
        task_id = state.get("task_id", "")
        is_stream = state.get("is_stream", False)

        if is_stream:
            state["answer"] = self._stream_generate(client, model, prompt, task_id)
        else:
            state["answer"] = self._invoke_generate(client, model, prompt)
            if task_id:
                set_task_result(task_id, "answer", state["answer"])

    def _stream_generate(
        self, client, model: str, prompt: str, task_id: str
    ) -> str:
        """流式生成: 逐 token 推送 SSE delta 事件

        前端收到 delta 后立即渲染，实现打字机效果。
        全量答案在函数结束后存入 state["answer"]，
        用于后续写入 MongoDB 历史。
        """
        accumulated = ""
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in response:
                delta_text = ""
                if chunk.choices and chunk.choices[0].delta:
                    delta_text = chunk.choices[0].delta.content or ""

                if delta_text:
                    accumulated += delta_text
                    push_sse_event(
                        task_id=task_id,
                        event=SSEEvent.DELTA,
                        data={"delta": delta_text},
                    )
        except Exception as e:
            self.logger.error(f"流式生成出错: {e}")

        return accumulated

    def _invoke_generate(self, client, model: str, prompt: str) -> str:
        """非流式生成: 同步等待完整响应"""
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"生成回答出错: {e}")
            return "抱歉，生成回答时出现错误。"

    def _save_history(self, state: QueryGraphState):
        """保存本轮对话到 MongoDB（用户问题 + 助手回答）

        为什么统一在 answer_output 写入？
        - item_name_confirm 专注于商品确认（只读 MongoDB）
        - answer_output 作为管线最终出口统一写入，职责更清晰
        - 确保只有成功生成答案后才写入（避免写入中间状态）
        """
        answer = state.get("answer", "")
        session_id = state.get("session_id", "")
        if not answer or not session_id:
            return

        user_query = state.get("original_query", "")
        rewritten_query = state.get("rewritten_query", user_query)
        item_names = state.get("item_names") or []

        try:
            # 保存用户消息
            save_chat_message(
                session_id=session_id,
                role="user",
                text=user_query,
                rewritten_query=rewritten_query,
                item_names=item_names,
            )
            # 保存助手回答
            save_chat_message(
                session_id=session_id,
                role="assistant",
                text=answer,
                rewritten_query=rewritten_query,
                item_names=item_names,
            )
        except Exception as e:
            self.logger.error(f"保存历史对话失败: {e}")
```

### Insight

答案生成节点的四个关键设计:

1. **预设答案 vs 生成答案的双路径**: `item_name_confirm` 拦截/反问时会预设 `answer` 字段。`answer_output` 检测到预设答案后跳过 LLM 生成，但仍然执行历史写入和 SSE 推送。这让管线出口统一，不需要在路由层判断"答案是预设的还是生成的"。

2. **流式 FINAL 事件的两种行为**:
   - 走过流式生成 → FINAL 发空信号，前端用已累积的 delta 文本
   - 未走流式生成（预设答案）→ FINAL 携带完整答案

   为什么不统一？因为流式生成时，前端已经通过 delta 事件逐字显示了完整答案，再在 FINAL 中重复发送一次是浪费带宽。FINAL 事件的核心语义是"结束信号"而不是"答案载体"。

3. **字符预算的级联分配**: `_format_reranked_docs` 先用预算，剩余的传给 `_format_chat_history`。这保证了最重要的检索文档不被截断，同时在有余量时保留历史上下文。如果 12000 字符全被文档用完，历史对话就是空的 — 这比截断文档更合理。

4. **`_stream_generate` 使用 OpenAI 原生客户端**: `client.chat.completions.create(stream=True)` 返回一个迭代器。每个 `chunk.choices[0].delta.content` 是一小段文本（通常 1-3 个 token）。`accumulated` 累积全量答案用于后续写入 MongoDB。

---

## Phase 11: item_name_confirm 历史改造

### 11.1 改造内容

现有 `item_name_confirm.py` 中有两个 TODO 标记：

```python
# TODO: 接入实际的历史存储（如 Redis / DB）
chat_history: list[dict] = []
history_text = ""
```

和

```python
# TODO: 回填历史消息中的商品名（接入历史存储后启用）
```

现在需要：
1. 将 `from knowledge.core.base import BaseNode` 改为 `from knowledge.processor.query_pipeline.query_base import QueryBaseNode`
2. 将 `class ItemNameConfirmNode(BaseNode)` 改为 `class ItemNameConfirmNode(QueryBaseNode)`
3. 从 MongoDB 读取历史记录
4. 确认成功后回填 item_names

### 11.2 修改后的 process 方法

```python
def process(self, state: QueryGraphState) -> dict:
    query = state.get("original_query", "")
    if not query or not isinstance(query, str):
        raise ValidationError("original_query 不能为空", node=self.name)

    session_id = state.get("session_id", "")

    # ── ★ 改造: 从 MongoDB 读取历史对话 ──
    from knowledge.util.mongo_history_util import (
        get_recent_messages,
        update_message_item_names,
    )
    chat_history = get_recent_messages(session_id, limit=10)

    # 构造历史对话文本（供 LLM 做指代消解）
    history_text = ""
    for msg in chat_history:
        role = msg.get("role", "")
        content = msg.get("text", "")
        if role and content:
            history_text += f"{role}: {content}\n"

    # 第一阶段: LLM 提取
    extraction = _extract_item_names(query, self.settings, history_text)
    raw_names = extraction.get("item_names", [])
    rewritten = extraction.get("rewritten_query", query)

    self.logger.info(f"LLM提取: names={raw_names}, rewritten={rewritten}")

    # 没提取到任何商品名 → 拦截
    if not raw_names:
        return {
            "answer": "抱歉，我无法从您的问题中识别出具体的商品名称。"
                      "请提供更详细的产品信息，例如品牌和型号。",
            "rewritten_query": rewritten,
            "history": chat_history,
        }

    # 第二阶段: 向量对齐
    confirmed, options = _align_item_names(raw_names, self.settings)
    self.logger.info(f"对齐结果: confirmed={confirmed}, options={options}")

    # 第三阶段: 决策
    if confirmed:
        # ★ 改造: 回填历史消息中的 item_names
        if session_id:
            update_message_item_names(session_id, confirmed)

        return {
            "item_names": confirmed,
            "rewritten_query": rewritten,
            "history": chat_history,
        }

    if options:
        names_str = "、".join(options[:self.settings.item_name_max_options])
        return {
            "answer": f"我不确定您指的是哪款产品。您是在询问以下产品吗：{names_str}？",
            "rewritten_query": rewritten,
            "history": chat_history,
        }

    return {
        "answer": "抱歉，我无法在产品库中找到匹配的产品。请确认产品名称后重试。",
        "rewritten_query": rewritten,
        "history": chat_history,
    }
```

### 11.3 历史对话在 pipeline 中的双用途

```
item_name_confirm
  │
  │  chat_history = get_recent_messages(session_id)
  │  ├── 用途1: 传给 LLM，做指代消解（"它" → "RS-12 万用表"）
  │  └── state["history"] = chat_history  ← 写入 state
  │
  v
  三路检索 → RRF → Rerank
  │
  v
answer_output
  │
  │  state.get("history")  ← 从 state 取出
  │  └── 用途2: 填入提示词【历史对话】区块，LLM 生成更连贯的答案
  │
  v
  LLM 生成答案 + 写入 MongoDB
```

> **`item_name_confirm` 只读 MongoDB，`answer_output` 统一写 MongoDB** — 职责分离。如果两个节点都写，可能出现写入时序问题（如 confirm 先写了用户消息，但答案还没生成）。

---

## Phase 12: Web 层

### 12.1 创建 knowledge/schema/query_schema.py

```bash
# 先创建目录
mkdir -p knowledge/schema
touch knowledge/schema/__init__.py
```

```python
"""查询相关 Pydantic 模型定义

Request/Response 模型供 FastAPI 路由使用。
集中管理避免在路由文件中定义大量 class。
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="查询内容")
    session_id: Optional[str] = Field(None, description="会话ID，不传则后端自动生成")
    is_stream: bool = Field(False, description="是否流式返回（True=SSE推送，False=同步等待）")


class QueryResponse(BaseModel):
    """非流式查询响应（同步等待模式）"""
    message: str = Field(..., description="响应消息")
    session_id: str = Field(..., description="会话ID")
    answer: str = Field("", description="生成的答案")


class StreamSubmitResponse(BaseModel):
    """流式查询提交响应（POST /query 返回 task_id，前端用此建立 SSE 连接）"""
    message: str = Field(..., description="响应消息")
    session_id: str = Field(..., description="会话ID")
    task_id: str = Field(..., description="任务ID，前端用此 ID 请求 GET /stream/{task_id}")


class HistoryItem(BaseModel):
    """单条历史记录"""
    id: str = Field("", alias="_id")
    session_id: str = ""
    role: str = ""
    text: str = ""
    rewritten_query: str = ""
    item_names: List[str] = Field(default_factory=list)
    ts: Optional[float] = None


class HistoryResponse(BaseModel):
    """历史记录响应"""
    session_id: str
    items: List[HistoryItem]
```

---

### 12.2 创建 knowledge/services/query_service.py

```bash
mkdir -p knowledge/services
touch knowledge/services/__init__.py
```

```python
"""
查询业务服务

职责:
- 管理 session_id / task_id 的生成
- 编排 LangGraph 查询流程的执行
- 从 task_result 中取回答案
- 代理历史记录的 CRUD

设计:
- Service 层不知道 HTTP 协议（不处理 Request/Response）
- 不知道 SSE 的存在（由路由层创建队列、由 BaseNode 推送）
- 只负责业务编排逻辑
"""

import uuid
import logging
from typing import List, Dict, Any

from knowledge.util.task_util import (
    update_task_status,
    get_task_result,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)

logger = logging.getLogger(__name__)


class QueryService:

    def generate_session_id(self) -> str:
        """生成新的会话 ID"""
        return str(uuid.uuid4())

    def generate_task_id(self) -> str:
        """生成新的任务 ID"""
        return str(uuid.uuid4())

    def run_query_graph(
        self, task_id: str, session_id: str, user_query: str, is_stream: bool
    ):
        """执行 LangGraph 查询流程

        注意: 流式模式的 SSE 队列由路由层在调用前创建，
        这里不需要关心 SSE 的存在。

        Args:
            task_id: 任务唯一标识
            session_id: 会话标识（跨多轮对话）
            user_query: 用户原始问题
            is_stream: 是否流式输出
        """
        # 延迟导入: 避免模块加载时触发 BGE 模型加载
        from knowledge.processor.query_pipeline.graph import build_query_graph

        update_task_status(task_id, TASK_STATUS_PROCESSING)

        try:
            graph = build_query_graph()

            initial_state = {
                "original_query": user_query,
                "session_id": session_id,
                "task_id": task_id,
                "is_stream": is_stream,
            }

            graph.invoke(initial_state)

            update_task_status(task_id, TASK_STATUS_COMPLETED)

        except Exception as e:
            logger.error(f"查询流程执行失败: {e}", exc_info=True)
            update_task_status(task_id, TASK_STATUS_FAILED)

    def get_answer(self, task_id: str) -> str:
        """从 task_result 中取回答案（非流式模式用）"""
        return get_task_result(task_id, "answer", "")

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取会话历史记录"""
        from knowledge.util.mongo_history_util import get_recent_messages
        records = get_recent_messages(session_id, limit=limit)
        return [
            {
                "_id": str(r.get("_id", "")),
                "session_id": r.get("session_id", ""),
                "role": r.get("role", ""),
                "text": r.get("text", ""),
                "rewritten_query": r.get("rewritten_query", ""),
                "item_names": r.get("item_names", []),
                "ts": r.get("ts"),
            }
            for r in records
        ]

    def clear_history(self, session_id: str) -> int:
        """清除会话历史记录"""
        from knowledge.util.mongo_history_util import clear_history
        return clear_history(session_id)
```

### Insight

Router → Service → Processor 三层架构为什么与导入侧对称？

```
导入侧                                    查询侧
──────────────────────                    ──────────────────────
import_router.py                          query_router.py
  ├── POST /upload                          ├── POST /query
  └── GET /status/{task_id}                 ├── GET /stream/{task_id}
                                            ├── GET /history/{session_id}
                                            └── DELETE /history/{session_id}

import_file_service.py                    query_service.py
  ├── process_upload_file()                 ├── submit_query() / run_query_graph()
  └── run_import_graph()                    ├── get_answer()
                                            └── get_history() / clear_history()

deps.py                                   deps.py（扩展）
  ├── get_task_service()                    └── get_query_service()
  └── get_import_file_service()
```

对称架构的好处:
- **认知负担低**: 熟悉导入侧的人看查询侧代码零学习成本
- **职责清晰**: Router 只管 HTTP 协议转换，Service 只管业务编排，Processor 只管计算逻辑
- **可测试性**: 可以单独测试 Service（不启动 FastAPI）、单独测试 Processor（不需要 Service）

---

### 12.3 创建 knowledge/core/paths.py

```python
"""项目路径工具"""

from pathlib import Path


def get_front_page_dir() -> str:
    """获取前端页面目录路径

    返回 knowledge/front/ 目录的绝对路径。
    """
    return str(Path(__file__).resolve().parents[1] / "front")
```

### 12.4 创建 knowledge/core/deps.py

```python
"""
FastAPI 依赖注入

使用 @lru_cache 实现单例模式，避免每次请求创建新的 Service 实例。
"""

from functools import lru_cache

from knowledge.services.query_service import QueryService


@lru_cache
def get_query_service() -> QueryService:
    """获取查询服务单例"""
    return QueryService()
```

> **为什么 deps.py 放在 core/ 而不是 api/ ？** 因为依赖注入的提供者（Service 实例）属于"基础设施"层面，不属于某个特定的 API 路由。未来可能有多个 router 共享同一个 service。

### 12.5 创建 knowledge/api/query_router.py（完整版）

替换前置文档的基础版本，加入 SSE 端点、历史端点、前端页面服务。

```python
"""
查询 API 路由（完整版）

提供两种查询模式:
- POST /query (is_stream=false) — 同步查询，等待完整结果返回
- POST /query (is_stream=true)  — 提交任务，返回 task_id
- GET  /stream/{task_id}        — SSE 长连接，接收进度和流式答案

历史记录管理:
- GET    /history/{session_id}  — 获取会话历史
- DELETE /history/{session_id}  — 清除会话历史

前端页面:
- GET /chat.html — 返回聊天页面
"""

import os
import asyncio
import logging

import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from knowledge.core.deps import get_query_service
from knowledge.core.paths import get_front_page_dir
from knowledge.schema.query_schema import (
    QueryRequest,
    QueryResponse,
    StreamSubmitResponse,
)
from knowledge.services.query_service import QueryService
from knowledge.util.sse_util import sse_generator, create_sse_queue

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(title="Query Service", description="知识库查询服务")

    # CORS 中间件（开发环境允许所有来源）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载前端静态文件目录
    front_dir = get_front_page_dir()
    if front_dir and os.path.exists(front_dir):
        app.mount("/front", StaticFiles(directory=front_dir))

    register_routes(app)
    return app


def register_routes(app: FastAPI):
    """注册所有路由"""

    # ── 前端页面 ──

    @app.get("/chat.html")
    async def chat_page():
        """返回聊天页面"""
        path = os.path.join(get_front_page_dir(), "chat.html")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="chat.html not found")
        return FileResponse(path)

    # ── 查询接口 ──

    @app.post("/query")
    async def query(
        request: QueryRequest,
        background_tasks: BackgroundTasks,
        service: QueryService = Depends(get_query_service),
    ):
        """统一查询入口（非流式 / 流式由 is_stream 参数控制）

        非流式模式:
            1. run_in_executor 中同步执行 LangGraph
            2. 等待完成后从 task_result 取答案
            3. 返回 QueryResponse

        流式模式:
            1. 创建 SSE 队列（必须在返回前创建，否则前端请求 /stream 时队列不存在）
            2. BackgroundTasks 异步执行 LangGraph
            3. 立即返回 StreamSubmitResponse（含 task_id）
            4. 前端用 task_id 建立 GET /stream/{task_id} SSE 连接
        """
        session_id = request.session_id or service.generate_session_id()
        task_id = service.generate_task_id()

        # ── 流式模式 ──
        if request.is_stream:
            # 必须在返回响应前创建队列
            create_sse_queue(task_id)

            # 后台执行 LangGraph（不阻塞当前请求）
            background_tasks.add_task(
                service.run_query_graph, task_id, session_id, request.query, True
            )

            return StreamSubmitResponse(
                message="Query submitted",
                session_id=session_id,
                task_id=task_id,
            )

        # ── 非流式模式 ──
        # run_in_executor: 在线程池中执行同步的 LangGraph，避免阻塞事件循环
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, service.run_query_graph, task_id, session_id, request.query, False
        )

        answer = service.get_answer(task_id)
        return QueryResponse(
            message="处理完成",
            session_id=session_id,
            answer=answer,
        )

    # ── SSE 流式端点 ──

    @app.get("/stream/{task_id}")
    async def stream(task_id: str, request: Request):
        """SSE 长连接 — 接收进度 + 流式答案

        前端通过 EventSource 连接此端点:
            const es = new EventSource(`/stream/${task_id}`);
            es.addEventListener('delta', ...);
            es.addEventListener('final', ...);
        """
        return StreamingResponse(
            sse_generator(task_id, request),
            media_type="text/event-stream",
        )

    # ── 历史记录管理 ──

    @app.get("/history/{session_id}")
    async def get_history(
        session_id: str,
        limit: int = 50,
        service: QueryService = Depends(get_query_service),
    ):
        """获取会话历史记录"""
        try:
            items = service.get_history(session_id, limit)
            return {"session_id": session_id, "items": items}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"history error: {e}")

    @app.delete("/history/{session_id}")
    async def clear_chat_history(
        session_id: str,
        service: QueryService = Depends(get_query_service),
    ):
        """清除会话历史记录"""
        count = service.clear_history(session_id)
        return {"message": "History cleared", "deleted_count": count}


# ── 独立启动入口 ──

if __name__ == "__main__":
    from knowledge.processor.query_pipeline.query_base import setup_logging
    setup_logging()
    uvicorn.run(app=create_app(), host="0.0.0.0", port=8001)
```

### Insight

非流式与流式模式的关键差异:

```
非流式模式 (is_stream=false):
┌────────┐  POST /query   ┌──────────┐  run_in_executor  ┌────────────┐
│ 前端   │ ──────────────> │ 路由层    │ ────────────────> │ LangGraph  │
│        │                │          │                   │ (同步阻塞)  │
│        │ <────────────── │          │ <──────────────── │            │
│        │  JSON response  │          │  完成             │            │
└────────┘                └──────────┘                   └────────────┘
  一次请求，一次响应。延迟 = LangGraph 执行时间。

流式模式 (is_stream=true):
┌────────┐  POST /query   ┌──────────┐  BackgroundTasks  ┌────────────┐
│ 前端   │ ──────────────> │ 路由层    │ ────────────────> │ LangGraph  │
│        │ <──────────────  │          │                   │ (后台线程)  │
│        │  {task_id}      │          │                   │            │
│        │                │          │                   │    │       │
│        │  GET /stream/   │          │                   │    │ SSE   │
│   SSE ◄┤ ──────────────> │  SSE     │ <─── Queue ◄──── │    │ push  │
│   连接  │ <──────────────  │  生成器   │                   │            │
│        │  event: delta   │          │                   │            │
│        │  event: final   │          │                   │            │
└────────┘                └──────────┘                   └────────────┘
  两次请求。POST 立即返回 task_id，GET 建立 SSE 长连接。

为什么不用一次请求搞定？
- POST 需要立即返回 task_id，让前端知道去哪里建 SSE 连接
- SSE 连接必须是 GET（浏览器 EventSource API 的限制）
- 分开后职责更清晰: POST 负责提交任务，GET 负责接收结果
```

---

## Phase 13: 图编排更新

### 13.1 更新 knowledge/processor/query_pipeline/graph.py

将 `answer_output` 接入图中，并更新路由逻辑。

```python
"""
查询流程编排（完整版 — 含答案生成）

图结构:
    item_name_confirm → [router]
        ├─ answer set → answer_output → END  (拦截/反问，跳过检索)
        └─ no answer  → vector_search  ─┐
                      → hyde_search     ─┤ → rrf_fusion → rerank → answer_output → END
                      → web_mcp_search  ─┘

answer_output 是管线的唯一出口:
- 拦截场景: 直接推送预设答案 + 写入 MongoDB
- 正常场景: 组装提示词 + LLM 生成答案 + 写入 MongoDB + SSE 推送
"""

import logging

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from knowledge.processor.query_pipeline.query_base import QueryBaseNode
from knowledge.processor.query_pipeline.nodes.answer_output import AnswerOutputNode
from knowledge.processor.query_pipeline.nodes.hyde_search import HyDeSearchNode
from knowledge.processor.query_pipeline.nodes.item_name_confirm import (
    ItemNameConfirmNode,
)
from knowledge.processor.query_pipeline.nodes.rerank import RerankerNode
from knowledge.processor.query_pipeline.nodes.rrf_fusion import RrfNode
from knowledge.processor.query_pipeline.nodes.vector_search import VectorSearchNode
from knowledge.processor.query_pipeline.nodes.web_mcp_search import WebMcpSearchNode
from knowledge.processor.query_pipeline.state import QueryGraphState

logger = logging.getLogger(__name__)


def _safe_node(node: QueryBaseNode):
    """容错包装 — 并行节点异常时返回空结果而非中断管线

    只用于三路并行检索节点。item_name_confirm 和 answer_output
    不包装，因为它们的失败是致命的。
    """
    def wrapper(state: QueryGraphState) -> dict:
        try:
            return node(state)
        except Exception as e:
            logger.warning(f"{node.name} 并行执行失败，降级为空结果: {e}")
            return {}
    return wrapper


def _query_router(state: QueryGraphState) -> list[str]:
    """商品名确认后的路由 — 条件 fan-out

    返回值:
    - ["answer_output"]: 拦截/反问（已有预设 answer）→ 跳过检索，直接生成
    - ["vector_search", "hyde_search", "web_mcp_search"]: 确认成功 → 三路并行检索
    """
    if state.get("answer"):
        return ["answer_output"]
    return ["vector_search", "hyde_search", "web_mcp_search"]


def build_query_graph() -> CompiledStateGraph:
    """构建并编译查询流程图"""
    wf = StateGraph(QueryGraphState)

    # ── 注册节点 ──
    wf.add_node("item_name_confirm", ItemNameConfirmNode())
    wf.add_node("vector_search", _safe_node(VectorSearchNode()))
    wf.add_node("hyde_search", _safe_node(HyDeSearchNode()))
    wf.add_node("web_mcp_search", _safe_node(WebMcpSearchNode()))
    wf.add_node("rrf_fusion", RrfNode())
    wf.add_node("rerank", RerankerNode())
    wf.add_node("answer_output", AnswerOutputNode())

    # ── 入口 ──
    wf.set_entry_point("item_name_confirm")

    # ── 条件 fan-out ──
    # 拦截 → ["answer_output"] 直接到答案生成
    # 通过 → ["vector_search", "hyde_search", "web_mcp_search"] 三路并行
    wf.add_conditional_edges("item_name_confirm", _query_router)

    # ── fan-in: 三路完成 → rrf_fusion ──
    wf.add_edge("vector_search", "rrf_fusion")
    wf.add_edge("hyde_search", "rrf_fusion")
    wf.add_edge("web_mcp_search", "rrf_fusion")

    # ── 线性: 融合 → 重排 → 答案生成 → 结束 ──
    wf.add_edge("rrf_fusion", "rerank")
    wf.add_edge("rerank", "answer_output")
    wf.add_edge("answer_output", END)

    return wf.compile()
```

### Insight

路由策略的变化 — 从 `[END]` 到 `["answer_output"]`:

前置文档中，拦截场景路由到 `[END]` 直接结束。这在只关心检索结果时是对的——但现在需要：
1. 写入 MongoDB 历史（用户问了问题，即使被拦截也要记录）
2. 推送 SSE FINAL 事件（通知前端流程结束）
3. 推送 SSE progress 事件（显示"生成答案"已完成）

如果路由到 `[END]`，这些都不会发生。所以拦截场景也要经过 `answer_output` — 只是跳过 LLM 生成，直接推送预设答案。

`answer_output` 节点通过 `state.get("answer")` 检测预设答案，走不同的处理分支。这是经典的 **单一出口** 设计模式。

---

## Phase 14: 前端 chat.html

### 14.1 创建前端目录和文件

```bash
mkdir -p knowledge/front
```

### 14.2 创建 knowledge/front/chat.html

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>掌柜智库 - 知识问答</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; height: 100vh; display: flex; flex-direction: column; }
        h1 { text-align: center; color: #333; margin-bottom: 10px; font-size: 1.5em; }

        /* 聊天区域 */
        .chat-area { flex: 1; overflow-y: auto; padding: 10px; background: white; border-radius: 8px; margin-bottom: 10px; }
        .message { margin: 10px 0; padding: 10px 14px; border-radius: 12px; max-width: 80%; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
        .message.user { background: #007bff; color: white; margin-left: auto; }
        .message.assistant { background: #e9ecef; color: #333; }

        /* 进度条 */
        .progress-bar { font-size: 0.85em; color: #666; padding: 4px 0; }
        .progress-bar .done { color: #28a745; }
        .progress-bar .running { color: #fd7e14; }

        /* 输入区域 */
        .input-area { display: flex; gap: 8px; }
        .input-area input { flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 1em; }
        .input-area button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; }
        .input-area button:disabled { background: #999; cursor: not-allowed; }

        /* 控制区域 */
        .controls { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; font-size: 0.9em; }
        .controls label { color: #666; }
    </style>
</head>
<body>
<div class="container">
    <h1>掌柜智库</h1>

    <div class="controls">
        <label><input type="checkbox" id="streamToggle" checked> 流式模式</label>
        <button onclick="clearHistory()" style="margin-left:auto; padding:4px 12px; font-size:0.85em; background:#dc3545; color:white; border:none; border-radius:4px; cursor:pointer;">清除历史</button>
    </div>

    <div class="chat-area" id="chatArea"></div>

    <div class="input-area">
        <input type="text" id="queryInput" placeholder="请输入您的问题..." onkeydown="if(event.key==='Enter')sendQuery()">
        <button id="sendBtn" onclick="sendQuery()">发送</button>
    </div>
</div>

<script>
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 配置
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const API_BASE = '';  // 同源部署，无需前缀

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Session ID 管理
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 页面加载时生成一次，同一标签页所有对话共享
let sessionId = localStorage.getItem('kb_session_id');
if (!sessionId) {
    sessionId = 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('kb_session_id', sessionId);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DOM 引用
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const chatArea = document.getElementById('chatArea');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const streamToggle = document.getElementById('streamToggle');

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 工具函数
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = text;
    chatArea.appendChild(div);
    scrollToBottom();
    return div;
}

function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

function renderProgress(container, doneList, runningList, status) {
    // 查找或创建进度条元素
    let bar = container.querySelector('.progress-bar');
    if (!bar) {
        bar = document.createElement('div');
        bar.className = 'progress-bar';
        container.insertBefore(bar, container.firstChild);
    }

    let html = '';
    if (doneList && doneList.length > 0) {
        html += '<span class="done">✓ ' + doneList.join(' → ') + '</span>';
    }
    if (runningList && runningList.length > 0) {
        html += ' <span class="running">⟳ ' + runningList.join(', ') + '</span>';
    }
    if (status === 'completed') {
        html += ' <span class="done">✓ 完成</span>';
    }
    bar.innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 发送查询
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function sendQuery() {
    const query = queryInput.value.trim();
    if (!query) return;

    // 禁用输入
    sendBtn.disabled = true;
    queryInput.value = '';

    // 显示用户消息
    addMessage('user', query);

    const isStream = streamToggle.checked;

    try {
        const resp = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                query: query,
                session_id: sessionId,
                is_stream: isStream,
            }),
        });

        const data = await resp.json();

        if (!isStream) {
            // ── 非流式: 直接显示答案 ──
            addMessage('assistant', data.answer || '(无回答)');
            sendBtn.disabled = false;
        } else {
            // ── 流式: 用 task_id 建立 SSE 连接 ──
            handleStream(data.task_id);
        }
    } catch (err) {
        addMessage('assistant', '请求失败: ' + err.message);
        sendBtn.disabled = false;
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SSE 流式处理
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function handleStream(taskId) {
    // 创建助手消息容器（先显示空的，后续逐字填充）
    const botMsg = addMessage('assistant', '');
    let rawText = '';

    // 建立 SSE 连接
    const es = new EventSource(`${API_BASE}/stream/${taskId}`);

    // progress 事件: 更新进度条
    es.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data || '{}');
        renderProgress(botMsg, d.done_list, d.running_list, d.status);
        // 兜底: 任务完成时启用发送按钮
        if (d && d.status === 'completed') {
            sendBtn.disabled = false;
        }
    });

    // delta 事件: 逐字渲染答案（打字机效果）
    es.addEventListener('delta', (e) => {
        const d = JSON.parse(e.data || '{}');
        if (d.delta) {
            rawText += d.delta;
            botMsg.textContent = rawText;
            scrollToBottom();
        }
    });

    // final 事件: 渲染完整答案 + 关闭连接
    es.addEventListener('final', (e) => {
        const d = JSON.parse(e.data || '{}');
        // 如果 FINAL 携带完整答案（预设答案场景），用它覆盖
        if (d.answer) {
            botMsg.textContent = d.answer;
        }
        es.close();
        sendBtn.disabled = false;
    });

    // 错误处理
    es.onerror = () => {
        es.close();
        if (!rawText) {
            botMsg.textContent = '连接中断';
        }
        sendBtn.disabled = false;
    };
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 清除历史
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function clearHistory() {
    try {
        await fetch(`${API_BASE}/history/${sessionId}`, {method: 'DELETE'});
        chatArea.innerHTML = '';
        // 生成新的 session_id
        sessionId = 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem('kb_session_id', sessionId);
    } catch (err) {
        alert('清除历史失败: ' + err.message);
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 页面加载时恢复历史
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function loadHistory() {
    try {
        const resp = await fetch(`${API_BASE}/history/${sessionId}?limit=50`);
        const data = await resp.json();
        if (data.items && data.items.length > 0) {
            for (const item of data.items) {
                addMessage(item.role, item.text);
            }
        }
    } catch (err) {
        console.warn('加载历史失败:', err);
    }
}

loadHistory();
</script>
</body>
</html>
```

### Insight

前端的几个设计要点:

1. **session_id 生命周期**: `localStorage` 持久化，同一浏览器标签页的所有对话共用。关闭标签页后重新打开，session_id 不变 → 历史记录可以恢复。点击"清除历史"时生成新的 session_id → 干净的新会话。

2. **为什么需要两次请求（POST + GET）？**
   - POST `/query` 提交任务 → 立即返回 `task_id`（毫秒级）
   - GET `/stream/{task_id}` 建立 SSE 长连接 → 持续接收 delta/final 事件
   - 浏览器 `EventSource` API 只支持 GET 请求，无法通过 SSE 传递 POST body

3. **progress 事件的"兜底"机制**: `if (d.status === 'completed') sendBtn.disabled = false` — 即使 final 事件丢失（网络抖动），progress(completed) 也能解锁发送按钮。双重保障避免按钮永远禁用。

4. **loadHistory 的时机**: 页面加载时立即调用，从 MongoDB 恢复历史对话。这让用户刷新页面后看到之前的对话记录。

---

## Phase 15: 端到端验证

### 15.1 语法检查

```bash
cd /home/ccr/dev/LearningProject/shopkeeper_brain/knowledge

# 新文件语法检查
uv run python -m py_compile knowledge/util/task_util.py
uv run python -m py_compile knowledge/util/sse_util.py
uv run python -m py_compile knowledge/util/mongo_history_util.py
uv run python -m py_compile knowledge/processor/query_pipeline/query_base.py
uv run python -m py_compile knowledge/processor/query_pipeline/nodes/answer_output.py
uv run python -m py_compile knowledge/schema/query_schema.py
uv run python -m py_compile knowledge/services/query_service.py
uv run python -m py_compile knowledge/core/deps.py
uv run python -m py_compile knowledge/core/paths.py
uv run python -m py_compile knowledge/api/query_router.py

# 已修改文件语法检查
uv run python -m py_compile knowledge/core/config.py
uv run python -m py_compile knowledge/processor/query_pipeline/state.py
uv run python -m py_compile knowledge/prompts/query_prompt.py
```

### 15.2 单元验证

```bash
# 验证 task_util
uv run python -c "
from knowledge.util.task_util import *
tid = 'test'
update_task_status(tid, TASK_STATUS_PROCESSING)
add_running_task(tid, 'answer_output')
print(get_running_task_list(tid))  # ['生成答案']
add_done_task(tid, 'answer_output')
print(get_done_task_list(tid))     # ['生成答案']
set_task_result(tid, 'answer', '测试')
print(get_task_result(tid, 'answer'))  # '测试'
clear_task(tid)
print('task_util OK')
"

# 验证 schema
uv run python -c "
from knowledge.schema.query_schema import QueryRequest, QueryResponse, StreamSubmitResponse
req = QueryRequest(query='测试', is_stream=True)
print(f'query={req.query}, stream={req.is_stream}')
print('schema OK')
"
```

### 15.3 启动服务

```bash
cd /home/ccr/dev/LearningProject/shopkeeper_brain/knowledge
uv run python -m knowledge.api.query_router
```

服务启动后访问 `http://localhost:8001/chat.html` 测试聊天界面。

### 15.4 API 测试

```bash
# 非流式查询
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "万用表怎么测电压？", "session_id": "test_sess", "is_stream": false}'

# 流式查询（提交）
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "万用表怎么测电压？", "session_id": "test_sess", "is_stream": true}'
# 返回 {"task_id": "xxx", ...}

# 流式查询（SSE 连接）
curl -N http://localhost:8001/stream/<task_id>

# 查看历史
curl http://localhost:8001/history/test_sess

# 清除历史
curl -X DELETE http://localhost:8001/history/test_sess
```

---

## 常见问题与排查

### 问题 1: 流式模式下按钮一直禁用

**症状**: 答案生成完了，但发送按钮一直灰色不可点击。

**原因**: `FINAL` 事件和 `progress(completed)` 都没到达前端。可能是 `answer_output` 抛异常且 `query_service` 的状态更新也未执行。

**排查**: 检查后端日志是否有 `查询流程执行失败` 的错误。

### 问题 2: 并行节点报 INVALID_CONCURRENT_GRAPH_UPDATE

**症状**: `At key 'session_id': Can receive only one value per step.`

**原因**: 并行节点的 `process` 方法返回了 `return state`（整个 state），多个节点同时写 `session_id` 导致冲突。

**修复**: 并行节点只返回自己修改的字段：

```python
# 错误
return state

# 正确
return {"embedding_chunks": results}
```

### 问题 3: MongoDB 连接失败

**症状**: `pymongo.errors.ServerSelectionTimeoutError`

**原因**: MongoDB 未启动或 `mongo_url` 配置错误。

**修复**: 确保 MongoDB 服务运行中，且 `.env` 中 `MONGO_URL` 正确。

### 问题 4: SSE 队列不存在

**症状**: 流式模式下前端无任何事件到达。

**原因**: `create_sse_queue(task_id)` 未在 `BackgroundTasks.add_task` 之前调用。

**修复**: 确保路由层中 `create_sse_queue` 在 `background_tasks.add_task` 之前执行。

---

## 总结

### 新增文件清单

| 文件 | 行数(约) | 用途 |
|------|---------|------|
| `util/task_util.py` | ~95 | 任务状态管理 |
| `util/sse_util.py` | ~100 | SSE 队列 + 生成器 |
| `util/mongo_history_util.py` | ~115 | MongoDB 历史读写 |
| `processor/query_pipeline/query_base.py` | ~75 | 查询侧 BaseNode |
| `processor/query_pipeline/nodes/answer_output.py` | ~225 | 答案生成节点 |
| `schema/query_schema.py` | ~40 | Pydantic 模型 |
| `services/query_service.py` | ~80 | 查询业务服务 |
| `core/deps.py` | ~12 | 依赖注入 |
| `core/paths.py` | ~10 | 路径工具 |
| `api/query_router.py` | ~120 | FastAPI 路由（完整版） |
| `front/chat.html` | ~200 | 前端聊天页面 |
| **合计** | **~1072** | |

### 修改文件清单

| 文件 | 改动 |
|------|------|
| `core/config.py` | 新增 MongoDB + 答案生成配置字段 |
| `processor/query_pipeline/state.py` | 新增 task_id / is_stream / prompt 字段 |
| `prompts/query_prompt.py` | 新增 ANSWER_PROMPT |
| `processor/query_pipeline/graph.py` | 完整版（含 answer_output + 路由更新） |
| `processor/query_pipeline/nodes/item_name_confirm.py` | 接入 MongoDB 历史 + 继承 QueryBaseNode |

### 推荐的操作顺序

```
Phase 7   → config + state + prompt 扩展（验证配置加载）
Phase 8   → task_util + sse_util + mongo_history_util（单元测试）
Phase 9   → QueryBaseNode（验证继承正确）
Phase 10  → answer_output（核心节点，需要前面所有工具就绪）
Phase 11  → item_name_confirm 改造（接入 MongoDB 历史）
Phase 12  → schema + service + deps + paths + router（Web 层完整）
Phase 13  → graph.py 更新（接入 answer_output）
Phase 14  → chat.html（前端页面）
Phase 15  → 端到端验证
```

> 每完成一个 Phase，用 `python -m py_compile` 验证语法。遇到问题就停下来排查，不要跳到下一步。

### 核心设计要点回顾

1. **单一出口**: `answer_output` 是管线的唯一出口，无论拦截还是正常生成都经过它 → 统一处理 MongoDB 写入、SSE 推送、答案返回
2. **SSE 三层解耦**: `task_util`（状态）+ `sse_util`（推送）+ `QueryBaseNode`（协调）→ 任何一层可以独立替换
3. **session_id / task_id 分离**: session 跟随浏览器标签页，task 跟随单次提问 → 互不干扰
4. **字符预算级联**: 检索文档优先占用预算，剩余给历史对话 → 保证答案质量
5. **容错降级**: MongoDB 写入失败不中断查询、Web 搜索失败不影响本地检索、历史加载失败返回空列表
