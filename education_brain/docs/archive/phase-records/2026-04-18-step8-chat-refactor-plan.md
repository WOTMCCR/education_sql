# Step 8 Chat / Search Refactor Plan

> 状态：阶段性实现记录
>
> 本文档描述 Step 8 时期的重构计划，保留作历史背景说明；当前接口联调请以 `docs/api-reference.md` 为准。

> 当前阶段目标：保留聊天统一入口，但把"搜索类请求"和"回答类请求"彻底分层，避免搜索请求误入长上下文 LLM 回答链。

## 1. 背景

当前 Step 8 已具备以下能力：

- `/search/courses`：课程结构化查询
- `/search/questions`：题目结构化查询
- `/search/documents`：文档向量检索
- `/chat/query`：统一问答入口
- LangGraph 查询管线：`query_rewrite -> vector_search / hyde_search -> rrf_fusion -> rerank -> answer_generate`

但实际联调暴露出几个问题：

1. 搜索类请求会被当成"需要回答"的请求处理，导致：
   - token 过长
   - 本地 Ollama 超时
   - 降级回退体验差
2. `course_intro` / `question_search` 当前只是最小可用实现：
   - `_handle_course` 把整句用户输入 `re.escape(query)` 做正则，命中率极低
   - `_handle_question` 同样是整句匹配题干，无法处理自然语言
   - 两者都没有复用 `/search/*` 的查询逻辑
3. `knowledge_qa` 依赖本地 LLM，当前存在：
   - 冷启动慢
   - 超时波动大
   - 熔断后本轮后续节点直接跳过
4. `/chat/history` 当前有可用性问题（见 §6 Phase E 具体说明）

### 1.1 当前已就位的部分

以下能力**不需要重构**，只需保持复用：

- `document_search.py`：已是独立 service，被 `/search/documents` 和 `_handle_doc_search` 共同复用
- `intent_classifier.py`：规则 + LLM fallback 结构合理，需扩展但不需重写
- `query_pipeline/*`：LangGraph 管线只服务 `knowledge_qa`，不存在误入问题

## 2. 产品定位

系统应分为三层能力：

### 2.1 传统查询层

给前端查询页使用，强调稳定、快速、可筛选：

- `/search/courses`
- `/search/questions`
- `/search/documents`

### 2.2 聊天统一入口层

给聊天窗口使用，用户可以自然提问，但后端不必对所有请求都使用 LLM：

- 先做意图识别 + 槽位提取（一步完成）
- 再决定是返回"结构化结果"还是"LLM 回答"

### 2.3 RAG 问答层

只处理真正需要生成式回答的问题：

- 对比
- 解释
- 总结
- 推荐
- 为什么
- 怎么选

## 3. 目标行为

### 3.1 搜索类请求

当意图识别为以下类型时：

- `course_intro`
- `question_search`
- `doc_search`

处理方式：

- 直接复用后端查询 service
- 返回结构化结果给前端
- 不再进入 `answer_generate`
- 不再为这些请求消耗大模型回答 token

### 3.2 回答类请求

当意图识别为：

- `knowledge_qa`

处理方式：

- 进入 LangGraph 查询管线
- 允许 query rewrite / retrieval / answer generate
- 支持后续 SSE 流式输出

## 4. 后端职责边界

### 4.1 `/search/*`

职责：

- 面向"页面型查询"
- 返回结构化、稳定、可分页/可筛选的数据

### 4.2 `/chat/query`

职责：

- 面向"聊天型入口"
- 做意图识别 + 结果编排
- 不负责重复实现三套查询逻辑

### 4.3 查询 service

职责：

- 承担真实查询逻辑
- 被 `/search/*` 与 `/chat/query` 共同复用

## 5. 核心设计决策

### 5.1 意图分类与槽位提取一体化

当前 `classify_intent` 只返回意图字符串。但 chat 路由拿到意图后，还需要从自然语言中**提取查询关键词**才能调用 service。

例如：

- "有哪些 Python 相关课程" → 意图 `course_intro`，关键词 `Python`
- "有没有数据类型的选择题" → 意图 `question_search`，关键词 `数据类型`，题型 `选择题`

如果意图分类和关键词提取分两步做，正则逻辑会重复且容易不一致。

**决策**：`classify_intent` 改为返回结构化结果，一步完成意图 + 槽位：

```python
@dataclass
class IntentResult:
    intent: str                    # course_intro / question_search / doc_search / knowledge_qa
    slots: dict[str, str]          # {"keyword": "Python"} / {"keyword": "数据类型", "question_type": "选择题"}
    confidence: str                # "rule" / "llm"
```

规则层：正则命中时顺带用 **捕获组** 或 **停用词剔除** 提取关键词。
LLM 层：prompt 改为要求结构化输出（JSON），一次返回意图 + slots。

### 5.2 sync → async 迁移策略

当前 `chat_query` 是同步 `def`。Phase F 的 SSE 要求 `async def` + `StreamingResponse`。

**决策**：Phase A 开始就把 chat 路由改为 `async def`。理由：

- FastAPI 同步路由在线程池执行，async 路由在事件循环执行，两者行为不同
- 如果 Phase A-D 都基于 sync 写，Phase F 要整体改签名和调用方式，返工量大
- MongoDB 操作（pymongo）是同步的，在 async 路由中用 `asyncio.to_thread` 包装即可

### 5.3 前端兼容策略

Phase D 会改变 `ChatResponse` 的结构（新增 `result_type`、`items` 等字段），这是 **breaking change**。

**决策**：采用**渐进式扩展**，不做路由版本化：

- 保留 `answer` 字段（搜索类也填充摘要文本）
- 新增 `result_type` 和 `items` 字段
- 前端根据 `result_type` 存在与否做渐进适配
- 旧前端不读 `result_type`，仍然能拿到 `answer` 文本

## 6. 目标文件结构

### 6.1 保留（不变或小改）

- `knowledge/api/routes/chat.py`
- `knowledge/service/intent_classifier.py`
- `knowledge/service/document_search.py`
- `knowledge/processor/query_pipeline/*`

### 6.2 新增

- `knowledge/service/course_search.py`
- `knowledge/service/question_search.py`
- `knowledge/service/chat_formatter.py`
- `knowledge/models/intent.py` — IntentResult 数据模型
- `knowledge/tests/test_course_search.py`
- `knowledge/tests/test_question_search.py`
- `knowledge/tests/test_chat_formatter.py`
- `knowledge/tests/test_chat_routes.py` — 路由级集成测试（命名与现有 `test_ingest_routes.py` 一致）
- `knowledge/tests/test_chat_history.py`

## 7. 重构阶段

### Phase A：意图分类升级 + 聊天入口编排化

目标：

- `classify_intent` 返回 `IntentResult`（意图 + 槽位）
- `/chat/query` 不再内联查询逻辑，只做编排
- 路由签名改为 `async def`，为后续 SSE 做准备

改动点：

- `knowledge/models/intent.py`（新增）
- `knowledge/service/intent_classifier.py`
- `knowledge/api/routes/chat.py`
- `knowledge/prompt/query_prompt.py`（LLM prompt 改为要求结构化输出）

具体要求：

1. `classify_intent(query)` → `IntentResult`

   规则层改造：
   - 正则命中时，用停用词剔除或捕获组提取关键词填入 `slots`
   - 增加基础英文规则覆盖（`course`、`question`、`install`、`compare` 等）

   LLM 层改造：
   - prompt 要求返回 JSON：`{"intent": "...", "slots": {"keyword": "...", ...}}`
   - 解析失败时 fallback 到 `knowledge_qa` + 空 slots

2. `chat_query` 编排化：
   - `doc_search` 分支：**已正确委托** `document_search.search_documents()`，保持不变
   - `course_intro` 分支：暂时保留内联实现，但改用 `IntentResult.slots["keyword"]` 替代整句匹配
   - `question_search` 分支：同上，用 slots 替代整句匹配
   - `knowledge_qa` 分支：不变

完成标准：

- `classify_intent` 返回 `IntentResult`，包含提取的 slots
- "有哪些 Python 相关课程" → `IntentResult(intent="course_intro", slots={"keyword": "Python"})`
- "有没有数据类型的选择题" → `IntentResult(intent="question_search", slots={"keyword": "数据类型", "question_type": "选择题"})`
- 路由签名已改为 `async def`
- 只有 `knowledge_qa` 会进入 LangGraph，其他三类请求绝不调用 `answer_generate`

### Phase B：抽出课程 + 题目查询 service

> 原计划 Phase B/C 合并。两者模式完全一致（抽 service → 改 search route → 改 chat route），拆成两个 Phase 增加上下文切换开销。

目标：

- 把课程和题目查询从 route 中抽离为独立 service
- `/search/courses`、`/search/questions`、`/chat/query` 复用同一套 service
- 参考已有的 `document_search.py` 作为 service 模板

改动点：

- 新增 `knowledge/service/course_search.py`
- 新增 `knowledge/service/question_search.py`
- 修改 `knowledge/api/routes/search.py`
- 修改 `knowledge/api/routes/chat.py`

`course_search.py` 最低能力：

- 接受 `keyword`、`audience`、`goal` 参数
- keyword 走归一化后的正则匹配（同当前 search route 逻辑）
- 支持分页
- chat 调用时：用 `IntentResult.slots["keyword"]` 作为 keyword，不分页

`question_search.py` 最低能力：

- 接受 `keyword`、`bank_code`、`question_type` 参数
- 支持从 slots 中获取归一化的题型
- 支持分页
- chat 调用时：用 slots 中的 keyword + question_type

完成标准：

- `search.py` 中 `search_courses` 和 `search_questions` 不再内联 MongoDB 查询
- `chat.py` 中 `_handle_course` 和 `_handle_question` 调用 service 而非直接操作 DB
- 新增 `test_course_search.py` 和 `test_question_search.py` 通过

### Phase C：统一聊天返回结构

目标：

- 搜索类结果与问答类结果在协议层明确区分
- 兼容现有前端（渐进式扩展，见 §5.3）

返回结构：

```python
class ChatResponse(BaseModel):
    task_id: str
    intent: str
    result_type: str                          # "search_result" | "answer"
    # 搜索类结果
    items: list[dict] = []                    # 结构化条目
    summary: str = ""                         # 摘要文本
    # 问答类结果
    answer: str = ""                          # LLM 生成回答（搜索类也填充摘要，保证前端向下兼容）
    citations: list[dict] = []
```

兼容保证：

- `answer` 字段始终有值：搜索类填摘要，问答类填 LLM 回答
- 旧前端只读 `answer` + `citations` 仍然可用
- 新前端根据 `result_type` 区分渲染方式

改动点：

- 新增 `knowledge/service/chat_formatter.py`
- 修改 `knowledge/api/routes/chat.py`
- 修改 `knowledge/models/chat.py`

完成标准：

- 搜索类返回 `result_type="search_result"` + `items` + `summary` + `answer`(=summary)
- 问答类返回 `result_type="answer"` + `answer` + `citations`
- 新增 `test_chat_formatter.py` 通过

### Phase D：收紧 `knowledge_qa` 管线

目标：

- 保证只有真正需要回答的问题才消耗 LLM
- 继续降低本地 Ollama 不稳定对整体体验的影响

具体措施：

1. `HyDE` 继续保留可关闭能力
2. 进一步限制 `answer_generate` 的上下文大小（当前 `max_context_chars=12000`，评估是否需下调）
3. 保留超时和熔断，但仅影响 `knowledge_qa`
4. 如果后续需要，可把 `rewrite` / `hyde` / `answer` 的模型拆开配置

改动点：

- `knowledge/core/config.py`
- `knowledge/core/llm.py`
- `knowledge/processor/query_pipeline/nodes/*`

### Phase E：修复历史会话

目标：

- `/chat/history` 能正确返回完整的对话信息

当前具体问题：

1. `get_recent_messages` 只投影 `role`、`content`、`intent`，丢失了 `citations`、`task_id`、`created_at`
2. 前端无法通过 `/chat/history` 获取时间戳（无法展示消息时间）
3. 前端无法通过 `/chat/history` 获取引用来源（无法展示引用卡片）
4. Phase C 新增的 `result_type`、`items`、`summary` 也需要被保存和回查

改动点：

- `knowledge/service/chat_history.py`
- `knowledge/api/routes/chat.py`
- `knowledge/models/chat.py`（ChatMessage 模型可能需要扩展）

完成标准：

- `save_message` 保存完整的 ChatMessage（含 result_type、items 等新字段）
- `get_recent_messages` 返回完整字段（至少包含 role、content、intent、citations、created_at）
- 显式传入 `session_id` 后，`/chat/query` 产生的消息能被 `/chat/history` 完整查回
- 新增 `test_chat_history.py` 通过

### Phase F：完成 SSE

前提：

- 搜索类请求已经不再走 LLM 回答链
- `knowledge_qa` 逻辑可用
- chat 路由已经是 `async def`（Phase A 完成）

目标：

- 让前端能看到"处理中间阶段"
- 不再依赖用户盲等

建议事件：

- `status` — 当前处理阶段（意图识别中 / 检索中 / 生成中）
- `token` — answer_generate 的流式 token
- `citation` — 引用来源
- `done` — 完成信号，附带完整结果
- `error` — 错误信息

技术要求：

- 使用 `StreamingResponse` + `async generator`
- 搜索类请求：直接返回完整结果（无需流式，但仍发 `status` → `done`）
- 问答类请求：`answer_generate` 节点改为流式输出 token

改动点：

- `knowledge/api/routes/chat.py`
- `knowledge/processor/query_pipeline/nodes/answer_generate.py`
- 可能需要新增 SSE 事件序列化工具

## 8. 测试策略

### 8.1 单元测试

需要覆盖：

- `intent_classifier` — IntentResult 返回值、slots 提取、英文输入
- `course_search` — keyword 归一化、空结果、分页
- `question_search` — keyword + 题型组合、空结果、分页
- `chat_formatter` — search_result / answer 两种格式、向下兼容
- `llm` 超时 / 熔断
- `query_graph` 路由

### 8.2 路由测试

需要覆盖：

- `/chat/query` 对不同意图的分发
- `/chat/query` 搜索类返回 `result_type="search_result"`
- `/chat/query` 问答类返回 `result_type="answer"`
- `/chat/history` 会话回查（含 citations、created_at）

### 8.3 真实 curl 手测

#### 课程查询

```bash
curl -s "http://localhost:8000/search/courses?keyword=Python"
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"有哪些 Python 相关课程"}'
# 预期: result_type="search_result", items 非空, answer 为摘要
```

#### 题目查询

```bash
curl -sG "http://localhost:8000/search/questions" \
  --data-urlencode "keyword=数据类型" \
  --data-urlencode "size=3"

curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"有没有数据类型的选择题"}'
# 预期: result_type="search_result", items 中 question_type 为选择题
```

#### 文档检索

```bash
curl -s "http://localhost:8000/search/documents?query=PyTorch&doc_type=course_doc&top_k=3"

curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"怎么安装 PyTorch"}'
# 预期: result_type="search_result", citations 非空
```

#### 知识问答

```bash
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"对比一下几种排序算法的优劣"}'
# 预期: result_type="answer", answer 为 LLM 生成
```

#### 会话历史

```bash
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"怎么安装 PyTorch","session_id":"step8-smoke-001"}'

curl -s "http://localhost:8000/chat/history?session_id=step8-smoke-001&limit=10"
# 预期: messages 包含 citations、created_at 字段
```

#### 英文输入

```bash
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"Python courses"}'
# 预期: 命中 course_intro 而非 fallback 到 knowledge_qa
```

## 9. 当前阶段建议

不要直接进入 SSE。

建议顺序：

1. 先完成 Phase A-C（意图升级 + service 抽离 + 返回结构统一）
2. 再完成 Phase D-E（管线收紧 + 历史修复）
3. 最后做 Phase F（SSE）

原因：

- 如果搜索类请求仍然会误入回答链，SSE 只是把错误行为"可视化"
- 如果 slots 提取不做，service 拿不到关键词，抽离了也没用
- A → B → C 三个 Phase 有数据流依赖，应连续完成

## 10. 完成标准

当以下条件全部满足时，可认为 Step 8 重构完成：

1. `/chat/query` 中：
   - `course_intro` 只返回课程查询结果，使用提取的关键词
   - `question_search` 只返回题目查询结果，使用提取的关键词 + 题型
   - `doc_search` 只返回文档检索结果
   - `knowledge_qa` 才进入 RAG
2. `classify_intent` 返回 `IntentResult`，包含 slots
3. `/search/*` 和 `/chat/query` 复用同一套 service
4. `/chat/history` 可正常回查完整消息（含 citations、created_at）
5. 前端接口向下兼容（`answer` 字段始终有值）
6. 之后再为 `knowledge_qa` 增加 SSE

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 规则层 slots 提取不准 | 搜索无结果 | 先覆盖高频模式，LLM fallback 兜底 |
| LLM 结构化输出解析失败 | 意图识别失败 | JSON 解析异常 fallback 到 knowledge_qa + 空 slots |
| Phase C 改返回结构 | 前端 break | 保留 answer 字段向下兼容 |
| pymongo 在 async 路由中阻塞 | 事件循环卡顿 | 用 `asyncio.to_thread` 包装 DB 调用 |
| SSE 需要 answer_generate 流式化 | 改动范围大 | Phase F 单独处理，不影响前序 Phase |
