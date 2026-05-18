# Step 9 — SSE 流式输出收束版计划

> 状态：阶段性实现计划 / 已落地背景记录
>
> 当前 SSE 联调应以 `docs/api-reference.md` 中的接口与事件协议为准；本文档主要保留设计取舍和实现背景。

> 目标不是重新设计整个聊天系统，而是在已完成的 Step 1–8 基础上，为 `knowledge` 增加一条可工作的 SSE 流式路径，并尽量复用现有意图路由、LangGraph 检索链路和历史存储逻辑。

## 1. 结论先行

Step 9 采用如下收束方案：

1. 保留现有 `POST /chat/query` 完全不变，继续作为同步接口。
2. 新增 `POST /chat/query/stream`，这是一个**统一流式提交入口**，所有意图都可以提交。
3. `POST /chat/query/stream` 内部仍然执行意图分类；只有 `knowledge` 会走 token 级流式输出，搜索类意图快速处理后直接通过 SSE `done` 返回完整结果。
4. 新增或保留 `GET /chat/stream/{task_id}`，通过 SSE 消费流式事件。
5. 流式路径复用现有 LangGraph 的检索阶段，只在答案生成阶段切换为流式实现。
6. 当前版本支持 `thinking` 事件，优先适配本地 `deepseek-r1` + Ollama 场景。
7. 当前版本**不承诺**断线重连、不承诺多实例共享、不引入 Redis 等分布式事件队列。

这是一版偏工程现实的 Step 9，而不是对原始 `PLAN.md` 的字面追平。

## 2. 为什么要这样收束

Step 8 之后，项目已经有一套可工作的同步聊天接口和查询管线：

- `knowledge/api/routes/chat.py` 已经完成四类意图路由。
- `knowledge/processor/query_pipeline/graph.py` 已经完成 `query_rewrite -> vector_search/hyde_search -> rrf_fusion -> rerank -> answer_generate`。
- `knowledge/core/llm.py` 已经具备同步调用包装、超时和 Ollama fallback。
- `knowledge/service/chat_history.py` 已经具备对话历史保存与读取。

因此 Step 9 的合理目标不是“重构聊天架构”，而是“给 `knowledge` 补一条流式输出能力”。

如果继续沿用旧版计划里的做法，会出现几个问题：

1. 让 `POST /chat/query` 同时返回 `ChatResponse` 和 `{task_id, status}` 两种结构，会破坏现有接口契约。
2. 在流式路径里手写一套 `rewrite -> search -> rerank`，会和已有 LangGraph 逐步漂移。
3. 在当前单进程内存队列模型下承诺“断线重连”和“多实例就绪”，承诺本身就不真实。
4. 用同步生成器 + `to_thread(list(...))` 伪装流式，最终还是会退化为阻塞式全量输出。

所以 Step 9 必须先收束，再实现。

## 3. 当前版本的明确范围

### 3.1 本阶段要做

- 为 `knowledge` 提供标准 SSE 流式输出。
- 在生成前推送 `status` 事件，降低用户等待时的空白感。
- 在本地 `deepseek-r1` 场景下推送 `thinking` 事件。
- 在最终完成时推送 `done` 事件，携带完整 answer 作为真相源。
- 在流式完成后保存 assistant 消息到 `chat_history`。
- 保持现有同步 `/chat/query` 行为不回归。

### 3.2 本阶段不做

- 不做 WebSocket。
- 不做断线重连保证。
- 不做多实例共享任务状态。
- 不做 Redis / MQ 事件总线。
- 不做“流式路径里把搜索类结果伪装成 token 流”。
- 不做前端页面开发，验收以 `curl -N` 和测试脚本为主。

## 4. API 方案

### 4.1 保留同步入口

```
POST /chat/query
```

职责不变：

- 分类意图
- 搜索类请求直接返回 `ChatResponse`
- `knowledge` 继续走同步 LangGraph 完整链路

Step 9 不改变这个端点的响应模型，也不改变它的兼容语义。

### 4.2 新增流式提交入口

```
POST /chat/query/stream
```

这是一个新的统一流式提交端点，所有意图都从这里进入。

请求体：

```json
{
  "query": "什么是教学设计的 ADDIE 模型？",
  "session_id": "sse-test-001"
}
```

提交成功响应：

```json
{
  "task_id": "abc123def456",
  "intent": "knowledge",
  "status": "processing"
}
```

这里返回的是“任务已接受”，不是最终答案。前端随后通过 `GET /chat/stream/{task_id}` 消费结果。

### 4.3 SSE 消费端点

```
GET /chat/stream/{task_id}
```

职责：

- 根据 `task_id` 找到对应任务队列
- 将队列中的事件转成标准 SSE 文本流
- 在 `done` 或 `error` 后结束连接

如果 `task_id` 不存在或已被清理，返回 `404`。

## 5. SSE 事件协议

### 5.1 事件类型

当前版本定义以下事件：

```text
event: status
data: {"phase": "rewriting", "message": "正在改写查询..."}

event: status
data: {"phase": "searching", "message": "正在检索相关文档..."}

event: status
data: {"phase": "generating", "message": "正在生成回答..."}

event: thinking
data: {"text": "用户在问 ADDIE 模型，需要先聚焦教学设计框架..."}

event: token
data: {"text": "ADDIE"}

event: token
data: {"text": "模型是"}

event: citation
data: {"citations": [{"index": 1, "doc_title": "...", "chunk_id": "..."}]}

event: done
data: {"task_id": "abc123", "intent": "knowledge", "answer": "ADDIE 模型是一种系统化教学设计框架..."}

event: error
data: {"message": "答案生成失败", "fallback_answer": "（答案生成暂时不可用，以下是检索到的相关内容）..."}
```

### 5.2 事件语义

- `status`：提示当前所处阶段，只用于进度可视化。
- `thinking`：模型推理过程中的思考片段，不计入最终 answer。
- `token`：最终回答正文的增量输出，前端只拼接这个。
- `citation`：一次性推送引用信息，通常在正文生成后发送。
- `done`：最终完整结果对象。对 `knowledge` 来说其中的 `answer` 是最终答案；对搜索类意图来说其中包含 `result_type/items/summary/answer/citations` 等完整结果。
- `error`：后台执行失败，必要时附带可展示的降级回答。

### 5.3 `thinking` 事件的范围

当前版本明确支持 `thinking`，因为本地主要运行的是 `deepseek-r1`。

但它的保证范围要写清楚：

1. 当底层流式 delta 中能稳定拿到 reasoning/thinking 字段时，发送 `thinking`。
2. 当模型不支持 reasoning 字段，或者当前回退链路无法拿到该字段时，不发送 `thinking`，只发送 `token`。
3. 不把 `<think>...</think>` 的原始文本解析作为主方案；优先使用结构化字段。

也就是说，`thinking` 是本版本支持的能力，但它仍然受具体模型和具体 API 返回格式约束。

## 6. 后端架构

### 6.1 总体流程

```text
前端
  ├─ POST /chat/query/stream
  │    └─ 返回 {task_id, status:"processing"}
  └─ GET /chat/stream/{task_id}
       └─ 持续接收 SSE 事件

后端
  ├─ 分类意图
  ├─ 非 knowledge -> 快速执行搜索类处理
  ├─ knowledge -> 创建任务队列
  ├─ 后台运行检索图，得到 final_chunks
  ├─ 调用 answer_generate_stream 逐片段产出事件
  ├─ 发送 citation / done
  └─ 保存 assistant 消息
```

### 6.2 任务状态模型

当前版本使用**单进程内存队列**：

```python
_task_queues: dict[str, asyncio.Queue]
_task_done_times: dict[str, float]
```

设计原则：

1. 简单优先，满足当前本地开发环境。
2. 不对外承诺断线恢复。
3. 不对外承诺跨 worker / 跨实例可见。
4. 可以保留一个短 TTL 用于清理未消费或已完成任务，但这个 TTL 只是清理策略，不是“重连能力”的产品承诺。

### 6.3 为什么当前不承诺重连

`asyncio.Queue` 的消费语义是单消费者、消费即移除。  
在不引入事件日志或持久化任务存储的前提下，无法真实支撑“断线后从剩余位置继续拉取”的承诺。

因此文档层面必须诚实：

- 当前版本只保证单次连接消费。
- 如果连接断开，结果是否仍可拿到不作为产品能力承诺。
- 以后如果要支持真正的重连，需要把内存队列升级为可回放事件存储。

## 7. LangGraph 复用策略

### 7.1 原则

流式路径不再手写一套平行的检索编排，而是复用现有 LangGraph 的检索节点和路由规则。

当前已经存在的核心节点：

- `query_rewrite`
- `vector_search`
- `hyde_search`
- `rrf_fusion`
- `rerank`
- `answer_generate`

Step 9 的复用边界是：

- 检索阶段继续用 LangGraph
- 生成阶段切换到 `answer_generate_stream`

### 7.2 收束后的图设计

建议在 `knowledge/processor/query_pipeline/graph.py` 中收敛为两种图：

1. `build_query_graph()`
   同步完整图：

   ```text
   query_rewrite
     -> vector_search / hyde_search
     -> rrf_fusion
     -> rerank
     -> answer_generate
   ```

2. `build_retrieval_graph()`
   流式检索图：

   ```text
   query_rewrite
     -> vector_search / hyde_search
     -> rrf_fusion
     -> rerank
     -> END
   ```

这样做的目的不是让图更复杂，而是避免下面这种坏结果：

- 同步接口修了 `query_rewrite`
- 流式接口忘了同步修改
- 最终两个接口对同一问题给出不同检索结果

### 7.3 为什么不直接用 `graph.stream()`

LangGraph 的 `graph.stream()` 更适合按节点级别观测 state 变化。  
Step 9 需要的是**token 级别**流式输出，这一段必须在答案生成函数内部直接消费底层流式 LLM 响应。

所以 Step 9 的合理拆法是：

- 图负责把状态推进到 `final_chunks`
- 流式答案函数负责把 `final_chunks` 变成 token 事件

## 8. LLM 流式封装

### 8.1 新增 async 流式接口

在 `knowledge/core/llm.py` 中新增流式封装，建议形式如下：

```python
@dataclass
class StreamChunk:
    kind: str   # "thinking" | "content"
    text: str

async def chat_completion_stream(...) -> AsyncGenerator[StreamChunk, None]:
    ...
```

这里要求是 **async generator**，不是同步生成器。

### 8.2 为什么必须改成 async generator

原因很直接：

1. 路由层本身是异步的。
2. SSE 输出天然适合 `async for`。
3. 可以避免 `to_thread(list(generator))` 这种把流式退化为一次性收集的错误写法。
4. 更容易处理取消、超时和逐片段转发。

### 8.3 `thinking` / `content` 识别策略

优先级如下：

1. OpenAI 兼容流式返回中存在结构化 `reasoning` / `thinking` 字段时，映射为 `StreamChunk(kind="thinking")`
2. `delta.content` 映射为 `StreamChunk(kind="content")`
3. Ollama `/api/chat` 原生流式回退中，如存在 `message.thinking`，同样映射为 `thinking`

不把字符串级别的 `<think>` 标签拆分当作主逻辑。

## 9. 答案生成流式化

### 9.1 新增 `answer_generate_stream`

在 `knowledge/processor/query_pipeline/nodes/answer_generate.py` 中新增异步流式函数：

```python
async def answer_generate_stream(
    state: QueryGraphState,
) -> AsyncGenerator[dict, None]:
    ...
```

它不是 LangGraph 节点，而是流式路径专用函数。

### 9.2 责任边界

`answer_generate_stream` 负责：

1. 复用现有 `_build_context()` 的上下文组装逻辑。
2. 调用 `chat_completion_stream()`。
3. 将 `thinking` 映射为 SSE `thinking` 事件。
4. 将 `content` 映射为 SSE `token` 事件。
5. 在正文结束后发送 `citation` 事件。

它不负责：

- 生成 `done`
- 保存历史
- 管理任务队列

这些都应由路由层或后台任务层统一处理。

### 9.3 最终答案拼接位置

完整 answer 的拼接放在后台任务里做，而不是放在 `answer_generate_stream()` 内部。

原因：

1. `done` 事件由任务层统一发出更自然。
2. assistant 历史也要在任务层统一保存。
3. `error` 时也更容易带上已收集的降级文本。

## 10. 路由行为设计

### 10.1 `POST /chat/query/stream`

伪代码：

```python
@router.post("/query/stream")
async def chat_query_stream(req: ChatRequest):
    intent_result = await asyncio.to_thread(classify_intent, req.query)
    task_id = uuid4().hex[:16]
    session_id = req.session_id or uuid4().hex[:16]

    await asyncio.to_thread(save_message, user_message)

    queue = asyncio.Queue()
    _task_queues[task_id] = queue

    asyncio.create_task(_run_stream_pipeline(..., intent_result=intent_result))

    return {
        "task_id": task_id,
        "intent": intent_result.intent,
        "status": "processing",
    }
```

### 10.2 `GET /chat/stream/{task_id}`

职责：

- 读取队列
- 序列化为 SSE 文本
- 在长时间空闲时发送 `:keepalive`
- 在 `done` 或 `error` 后结束

### 10.3 历史保存策略

流式接口的历史保存建议如下：

1. 用户消息：在 `POST /chat/query/stream` 被接受后立即保存。
2. assistant 消息：在后台任务拿到最终 answer 后保存。
3. 如果流式任务在生成中失败，但有可展示的 `fallback_answer`，则把该文本作为 assistant answer 保存。

这样可以保持多轮对话的历史连续性。

## 11. 错误处理

### 11.1 HTTP 层错误

- `task_id` 不存在：`404`

### 11.2 流内错误

后台执行失败时发送：

```text
event: error
data: {"message": "...", "fallback_answer": "..."}
```

处理原则：

1. 如果没有拿到任何可用文本，只返回错误消息。
2. 如果已经有上下文降级文本，附带 `fallback_answer`。
3. 如果已经产生过若干 `token`，仍然以 `error` 结束，不再发送 `done`。

## 12. 前端消费约束

### 12.1 `thinking` 和 `token` 必须分区

前端必须遵守：

- `thinking` 放独立区域或折叠区域
- `token` 才能进入主回答区
- `done.answer` 最终覆盖主回答区

不能把 `thinking` 直接混入回答正文，否则会污染最终回答。

### 12.2 推荐展示策略

- `status`：小字提示当前阶段
- `thinking`：默认折叠，可在调试模式展开
- `token`：实时拼接到回答区
- `citation`：在回答尾部展示来源
- `done`：覆盖回答区，结束加载态
- `error`：显示错误，并展示 `fallback_answer`

## 13. 配置项

建议新增配置：

```env
STREAM_TIMEOUT_SECONDS=180
STREAM_KEEPALIVE_SECONDS=15
```

含义：

- `STREAM_TIMEOUT_SECONDS`：单个流式任务总超时
- `STREAM_KEEPALIVE_SECONDS`：SSE 空闲时的心跳间隔

心跳以注释形式发送：

```text
:keepalive
```

## 14. 文件变更清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `knowledge/core/llm.py` | 修改 | 新增 async `chat_completion_stream()` 与 `StreamChunk` |
| `knowledge/core/config.py` | 修改 | 新增流式超时和心跳配置 |
| `knowledge/models/chat.py` | 修改 | 新增流式提交响应模型，或至少补充对应 schema |
| `knowledge/api/routes/chat.py` | 修改 | 新增 `POST /chat/query/stream` 和 `GET /chat/stream/{task_id}` |
| `knowledge/processor/query_pipeline/graph.py` | 修改 | 新增检索图或共享图构建逻辑 |
| `knowledge/processor/query_pipeline/nodes/answer_generate.py` | 修改 | 新增 `answer_generate_stream()` |
| `knowledge/service/chat_history.py` | 复用 | 流式完成后保存 assistant 历史 |
| `knowledge/tests/smoke_test_api.sh` | 修改 | 增加 SSE 冒烟 |
| `knowledge/tests/test_llm.py` | 修改 | 增加流式 LLM 单测 |
| `knowledge/tests/test_chat_routes.py` | 修改 | 增加流式端点测试 |
| `knowledge/tests/test_answer_generate.py` | 修改 | 增加流式答案生成测试 |

## 15. 实施阶段

### Phase A — 底层流式 LLM

- 在 `core/llm.py` 增加 async `chat_completion_stream()`
- 统一处理 `thinking` / `content`
- 保留 Ollama 原生 `/api/chat` 流式回退

验收：

- mock 流式响应可以正确区分 `thinking` 与 `content`
- 非 thinking 模型不会报错，只是不产出 `thinking`

### Phase B — 复用 LangGraph 检索图

- 在 `graph.py` 抽出检索阶段共享编排
- 保持同步链路行为不变
- 为流式路径提供“跑到 `final_chunks` 为止”的统一入口

验收：

- 同步 / 流式两条路径在检索结果上使用同一套节点
- 不再手写平行 `rewrite/search/rerank` 流程

### Phase C — 流式答案生成

- 在 `answer_generate.py` 中新增 `answer_generate_stream()`
- 基于 `final_chunks` 输出 `thinking` / `token` / `citation`

验收：

- 给定 mock chunks，可产出正确事件序列
- 不再出现“先收集完整列表再统一发出”的伪流式实现

### Phase D — 路由与任务队列

- 新增 `POST /chat/query/stream`
- 新增 `GET /chat/stream/{task_id}`
- 管理内存任务队列、心跳和完成清理

验收：

- `knowledge` 可正常进入流式路径
- 搜索类意图可正常进入统一流式入口并返回 `done`
- `task_id` 不存在返回 `404`

### Phase E — 测试与验收

- 扩展单元测试
- 扩展 `smoke_test_api.sh`
- 用本地 `deepseek-r1` 手工验证 `thinking` 事件

## 16. 验收场景

### 16.1 正常流式问答

1. `POST /chat/query/stream`
2. 收到 `{task_id, status:"processing"}`
3. `GET /chat/stream/{task_id}`
4. 依次收到 `status -> status -> status -> thinking? -> token* -> citation -> done`

### 16.2 搜索类请求走统一流式入口

请求：

```json
{"query": "有哪些 Python 课程？"}
```

预期：

- `POST /chat/query/stream` 返回 `200`
- 返回体里 `intent` 为搜索类意图，例如 `course_intro`
- 后续 `GET /chat/stream/{task_id}` 直接收到 `done`
- `done.data.result_type == "search_result"`

### 16.3 空检索

预期：

- 有 `status`
- 无 `token`
- 直接 `done`
- `done.answer` 为固定无结果提示

### 16.4 `thinking` 模型场景

前提：`answer_model` 指向 `deepseek-r1`

预期：

- 能收到至少一条 `thinking`
- `thinking` 不会混入 `done.answer`

### 16.5 历史一致性

预期：

- user 消息在任务接受后入库
- assistant 消息在 `done` 后入库
- assistant 的 `answer` 与 `done.answer` 一致

## 17. 明确删掉的旧承诺

以下内容从 Step 9 计划中明确移除，不再作为本阶段目标：

- “断线重连后继续消费剩余事件”
- “多实例部署无需改协议”
- “流式路径手动编排前置节点”
- “`POST /chat/query/stream` 只允许 `knowledge`，其余意图返回 400”
- “通过同步生成器 + `to_thread(list(...))` 实现流式”

这些内容不是绝对做不到，而是对当前项目阶段来说不值得，也不真实。

## 18. 检查清单

- [ ] `POST /chat/query` 行为保持不变
- [ ] 新增 `POST /chat/query/stream`
- [ ] 统一流式入口接受所有意图提交
- [ ] 搜索类意图通过 SSE `done` 返回完整结果，不走 token 流
- [ ] 新增 `GET /chat/stream/{task_id}`
- [ ] LangGraph 检索阶段被同步/流式共同复用
- [ ] `answer_generate_stream()` 为 async generator
- [ ] `thinking` 事件在 `deepseek-r1` 场景下可用
- [ ] `thinking` 不混入最终 answer
- [ ] `done.answer` 可作为前端真相源
- [ ] assistant 历史保存与 `done.answer` 一致
- [ ] `smoke_test_api.sh` 增加 SSE 组
- [ ] 文档中不再出现断线重连和多实例承诺
