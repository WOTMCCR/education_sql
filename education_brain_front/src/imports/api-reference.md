# Education Brain — API 接口文档

> Base URL: `http://<host>:8000`
>
> 本文档覆盖前后端联调所需的全部接口。基于 commit `5ec2deb`（2026-04-19）验证通过。

---

## 目录

1. [通用约定](#1-通用约定)
2. [聊天接口 /chat](#2-聊天接口)
   - 2.1 [POST /chat/query — 同步问答](#21-post-chatquery)
   - 2.2 [POST /chat/query/stream — 流式提交](#22-post-chatquerystream)
   - 2.3 [GET /chat/stream/{task_id} — SSE 消费](#23-get-chatstreamtask_id)
   - 2.4 [GET /chat/history — 历史查询](#24-get-chathistory)
3. [搜索接口 /search](#3-搜索接口)
   - 3.1 [GET /search/courses](#31-get-searchcourses)
   - 3.2 [GET /search/questions](#32-get-searchquestions)
   - 3.3 [GET /search/documents](#33-get-searchdocuments)
4. [健康检查](#4-健康检查)
5. [SSE 事件协议详解](#5-sse-事件协议详解)
6. [前端集成建议](#6-前端集成建议)

---

## 1. 通用约定

| 项目 | 说明 |
|------|------|
| Content-Type | 请求：`application/json`，响应：`application/json`（SSE 除外） |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601，如 `2026-04-19T08:30:00Z` |
| 错误响应 | `{"detail": "错误描述"}` + 对应 HTTP 状态码 |

### 意图类型（intent）

后端对用户查询自动分类为三种意图，前端根据 `intent` 字段决定渲染方式：

| intent | 含义 | 后端处理路径 | 前端渲染建议 |
|--------|------|-------------|-------------|
| `course_intro` | 课程查询 | MongoDB 结构化检索 | 课程卡片列表 |
| `question_search` | 题目查询 | MongoDB 结构化检索 | 题目列表 |
| `knowledge` | 知识问答（默认） | 向量检索 + LLM 生成 | Markdown 文本 + 引用 |

### 响应类型（result_type）

| result_type | 含义 | 关联字段 |
|-------------|------|---------|
| `search_result` | 结构化搜索结果 | `items` 为结果列表，`summary`/`answer` 为摘要文本 |
| `answer` | LLM 生成的知识回答 | `answer` 为回答正文，`citations` 为引用来源 |

---

## 2. 聊天接口

### 2.1 POST /chat/query

**同步问答入口。** 后端自动做意图分类 + 路由，返回完整结果。适合不需要流式体验的场景。

#### 请求

```
POST /chat/query
Content-Type: application/json
```

```json
{
  "query": "有哪些 Python 相关课程",
  "session_id": "abc123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 用户问题文本 |
| `session_id` | string | 否 | 会话 ID，用于多轮对话和历史查询。为空时后端自动生成 |

#### 响应 — ChatResponse

```json
{
  "task_id": "a1b2c3d4e5f67890",
  "intent": "course_intro",
  "result_type": "search_result",
  "items": [
    {
      "series_code": "python-101",
      "title": "Python 基础入门课",
      "description": "零基础学 Python",
      "match_level": "title",
      "modules": [...],
      "audience": ["在校生", "零基础"],
      "related_documents": [...]
    }
  ],
  "summary": "以下是 Python 相关课程：\n\n**Python 基础入门课**\n  零基础学 Python",
  "answer": "以下是 Python 相关课程：\n\n**Python 基础入门课**\n  零基础学 Python",
  "citations": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务唯一标识（16 位 hex） |
| `intent` | string | 意图分类：`course_intro` / `question_search` / `knowledge` |
| `result_type` | string | 结果类型：`search_result` / `answer` |
| `items` | array | 搜索结果列表（仅 `search_result` 时有内容） |
| `summary` | string | 搜索结果摘要（仅 `search_result` 时有内容） |
| `answer` | string | **统一回答字段**。搜索类意图 = summary 的副本；知识类意图 = LLM 生成的回答 |
| `citations` | array | 引用来源列表（仅 `knowledge` 意图时有内容） |

> **前端简化提示：** `answer` 字段始终有值，可作为统一展示字段。需要差异化渲染时再看 `result_type` 和 `items`。

#### 响应示例 — knowledge 意图

```json
{
  "task_id": "f8e7d6c5b4a39012",
  "intent": "knowledge",
  "result_type": "answer",
  "items": [],
  "summary": "",
  "answer": "排序算法各有适用场景。快速排序平均时间复杂度 O(n log n)...[来源: 算法讲义 > 排序章节]",
  "citations": [
    {
      "index": 1,
      "chunk_id": "abc123",
      "doc_id": "def456",
      "doc_title": "算法讲义",
      "source_file": "算法与数据结构.docx",
      "section_path": ["第三章", "排序算法"],
      "series_code": "algo-101",
      "project_name": ""
    }
  ]
}
```

#### 注意事项

- `knowledge` 意图走 LLM pipeline，响应时间可能为几十秒，慢模型下可超过 1 分钟，无固定 SLA
- 建议前端不要对同步接口设硬超时，或**优先使用流式接口**避免长等待

---

### 2.2 POST /chat/query/stream

**流式提交入口。** 提交查询后立即返回 `task_id`，前端用此 ID 建立 SSE 连接消费结果。

#### 请求

```
POST /chat/query/stream
Content-Type: application/json
```

```json
{
  "query": "什么是反向传播算法？",
  "session_id": "abc123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 用户问题文本 |
| `session_id` | string | 否 | 会话 ID。为空时后端自动生成 |

#### 响应 — StreamSubmitResponse

```json
{
  "task_id": "a1b2c3d4e5f67890",
  "intent": "knowledge",
  "status": "processing"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID，用于后续 SSE 连接 |
| `intent` | string | 后端识别的意图 |
| `status` | string | 固定为 `"processing"` |

#### 前端处理流程

```
1. POST /chat/query/stream → 拿到 task_id + intent
2. GET  /chat/stream/{task_id} → 建立 SSE 连接
3. 监听 SSE 事件，渲染 UI
4. 收到 done 或 error 事件后关闭连接
```

---

### 2.3 GET /chat/stream/{task_id}

**SSE 事件流。** 前端通过此接口实时接收后端处理进度和结果。

```
GET /chat/stream/{task_id}
Accept: text/event-stream
```

#### 响应格式

标准 SSE（Server-Sent Events），`Content-Type: text/event-stream`。

每条消息格式：
```
event: <event_type>
data: <json_payload>

```

#### SSE 事件类型

详见 [第 5 节 SSE 事件协议详解](#5-sse-事件协议详解)。

#### 错误情况

| 场景 | 行为 |
|------|------|
| `task_id` 不存在 | HTTP 404，`{"detail": "task_id 不存在或已过期"}` |
| 任务已完成超过 TTL（5 分钟） | HTTP 404（队列已清理） |

---

### 2.4 GET /chat/history

**查询历史消息。**

```
GET /chat/history?session_id=abc123&limit=20
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `session_id` | string | 是 | — | 会话 ID |
| `limit` | int | 否 | 20 | 返回条数，1-100 |

#### 响应

```json
{
  "session_id": "abc123",
  "messages": [
    {
      "session_id": "abc123",
      "task_id": "a1b2c3d4e5f67890",
      "role": "user",
      "content": "有哪些 Python 相关课程",
      "result_type": "",
      "items": [],
      "summary": "",
      "answer": "有哪些 Python 相关课程",
      "citations": [],
      "intent": "course_intro",
      "created_at": "2026-04-19T08:30:00Z"
    },
    {
      "session_id": "abc123",
      "task_id": "a1b2c3d4e5f67890",
      "role": "assistant",
      "content": "以下是 Python 相关课程：...",
      "result_type": "search_result",
      "items": [{"title": "Python 基础", "series_code": "python-101"}],
      "summary": "以下是 Python 相关课程：...",
      "answer": "以下是 Python 相关课程：...",
      "citations": [],
      "intent": "course_intro",
      "created_at": "2026-04-19T08:30:01Z"
    }
  ]
}
```

#### 消息字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | string | `"user"` 或 `"assistant"` |
| `content` | string | 消息内容（user 为原文，assistant 为回答文本） |
| `result_type` | string | assistant 消息的结果类型 |
| `items` | array | assistant 消息的搜索结果 |
| `summary` | string | assistant 消息的搜索摘要 |
| `answer` | string | assistant 消息的统一回答文本 |
| `citations` | array | assistant 消息的引用来源 |
| `intent` | string | 该轮对话的意图 |
| `created_at` | string | ISO 8601 时间戳 |

#### 注意事项

- 消息按 `created_at` 升序排列（最早的在前）
- 角色**通常**交替 `user → assistant`，但流式任务失败时后端不保存 assistant 消息，可能出现连续 user 消息。前端渲染历史时不要假设严格交替
- 不存在的 `session_id` 返回空列表，不报错

---

## 3. 搜索接口

直接检索接口，不经过意图分类，适合前端独立的搜索页面使用。

### 3.1 GET /search/courses

**课程查询。**

```
GET /search/courses?keyword=Python&audience=在校生&page=1&size=20
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `keyword` | string | 否 | `""` | 关键词，匹配名称/描述/分类/模块 |
| `audience` | string | 否 | `""` | 适合人群筛选 |
| `goal` | string | 否 | `""` | 学习目标筛选 |
| `page` | int | 否 | 1 | 页码（≥1） |
| `size` | int | 否 | 20 | 每页条数（1-100） |

#### 响应

```json
{
  "total": 2,
  "page": 1,
  "size": 20,
  "items": [
    {
      "series_code": "python-101",
      "title": "Python 基础入门课",
      "description": "零基础学 Python...",
      "category": "编程基础",
      "audience": ["在校生", "零基础"],
      "goals": ["掌握 Python 基础语法"],
      "match_level": "title",
      "matched_modules": [],
      "modules": [
        {
          "module_code": "python-101-m01",
          "title": "Python 环境搭建",
          "description": "安装 Python 和 IDE"
        }
      ],
      "related_documents": [
        {
          "doc_id": "abc123",
          "doc_title": "Python 基础讲义",
          "source_file": "Python基础入门.docx"
        }
      ]
    }
  ]
}
```

#### 课程条目字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `series_code` | string | 课程系列唯一编码 |
| `title` | string | 课程名称 |
| `description` | string | 课程描述 |
| `category` | string | 分类 |
| `audience` | array | 适合人群列表 |
| `goals` | array | 学习目标列表 |
| `match_level` | string | 匹配级别：`title` / `description` / `category` / `module` |
| `matched_modules` | array | 当 match_level 为 `module` 时，匹配的模块名称列表 |
| `modules` | array | 课程下属模块列表 |
| `related_documents` | array | 关联文档列表 |

> **`match_level` 说明：** 当关键词直接匹配课程标题/描述/分类时，`match_level` 为 `title`/`description`/`category`。当关键词仅匹配子模块时，`match_level` 为 `module`，前端可据此展示"包含相关模块"的提示。

---

### 3.2 GET /search/questions

**题目检索。**

```
GET /search/questions?keyword=数据类型&question_type=选择题&page=1&size=20
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `keyword` | string | 否 | `""` | 关键词，匹配题干 |
| `bank_code` | string | 否 | `""` | 题库编码 |
| `question_type` | string | 否 | `""` | 题型过滤：`单选题` / `多选题` / `判断题` / `编程题` / `简答题` / `填空题` |
| `page` | int | 否 | 1 | 页码（≥1） |
| `size` | int | 否 | 20 | 每页条数（1-100） |

#### 响应

```json
{
  "total": 15,
  "page": 1,
  "size": 20,
  "items": [
    {
      "question_id": "q001",
      "bank_code": "python-basic",
      "question_type": "单选题",
      "stem": "以下哪个不是 Python 内置数据类型？",
      "options": [
        {"label": "A", "text": "int"},
        {"label": "B", "text": "float"},
        {"label": "C", "text": "array"},
        {"label": "D", "text": "str"}
      ],
      "answer": "C",
      "explanation": "Python 内置数据类型包括 int、float、str 等，array 需要导入 array 模块。"
    }
  ]
}
```

---

### 3.3 GET /search/documents

**文档向量检索。** 走 Milvus 混合检索路径。

```
GET /search/documents?query=PyTorch&doc_type=course_doc&limit=5
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `query` | string | 是 | — | 搜索文本。空字符串时直接返回 `{"total": 0, "items": []}`（不含 `query`/`doc_type` 字段） |
| `doc_type` | string | 否 | `""` | 文档类型过滤：`course_doc` / `project_doc` / 空=全部 |
| `limit` | int | 否 | 5 | 返回数量（1-20） |

#### 响应

```json
{
  "total": 3,
  "query": "PyTorch",
  "doc_type": "course_doc",
  "items": [
    {
      "chunk_id": "abc123",
      "doc_id": "def456",
      "doc_title": "深度学习框架讲义",
      "source_file": "深度学习框架.docx",
      "chunk_text": "PyTorch 是一个开源的深度学习框架...",
      "section_path": ["第二章", "PyTorch 基础"],
      "distance": 0.234,
      "series_code": "dl-201",
      "project_name": ""
    }
  ]
}
```

---

## 4. 健康检查

```
GET /health
```

#### 响应

```json
{
  "status": "healthy",
  "components": {
    "mongodb": "ok",
    "milvus": "ok",
    "minio": "ok"
  }
}
```

| `status` 值 | 含义 |
|-------------|------|
| `healthy` | 所有组件正常 |
| `degraded` | 部分组件异常（仍可提供部分功能） |

---

## 5. SSE 事件协议详解

通过 `GET /chat/stream/{task_id}` 接收的 SSE 事件。

### 5.1 事件类型总览

| event | 说明 | 出现场景 | data 结构 |
|-------|------|---------|----------|
| `status` | 处理阶段状态更新 | 所有意图 | `{"phase": "...", "message": "..."}` |
| `thinking` | LLM 思考过程（可选） | `knowledge` 意图 | `{"text": "..."}` |
| `token` | LLM 生成的正文 token（不保证一定有） | `knowledge` 意图 | `{"text": "..."}` |
| `citation` | 引用来源列表 | `knowledge` 意图 | `{"citations": [...]}` |
| `done` | 任务完成，携带完整结果 | 所有意图 | 完整 ChatResponse |
| `error` | 任务失败 | 异常时 | `{"message": "..."}` |

### 5.2 搜索类意图的事件序列

```
course_intro / question_search:

  event: status
  data: {"phase": "searching", "message": "正在检索结果..."}

  event: done
  data: { 完整 ChatResponse }
```

搜索类意图**不产生** `token` 事件，直接通过 `done` 返回完整结果。

### 5.3 knowledge 意图的事件序列

```
knowledge:

  event: status
  data: {"phase": "rewriting", "message": "正在改写查询..."}

  event: status
  data: {"phase": "searching", "message": "正在检索相关文档..."}

  event: status
  data: {"phase": "generating", "message": "正在生成回答..."}

  event: thinking        ← 可选，取决于模型
  data: {"text": "让我思考一下..."}

  event: token           ← 逐 token 推送（不保证一定有）
  data: {"text": "排"}
  event: token
  data: {"text": "序"}
  event: token
  data: {"text": "算法"}

  event: citation        ← 有引用时推送
  data: {"citations": [{...}, {...}]}

  event: done
  data: { 完整 ChatResponse }
```

### 5.4 done 事件 data 结构

`done` 事件的 `data` 与同步接口的 `ChatResponse` 结构一致：

```json
{
  "task_id": "a1b2c3d4e5f67890",
  "intent": "knowledge",
  "result_type": "answer",
  "items": [],
  "summary": "",
  "answer": "排序算法各有适用场景...",
  "citations": [...]
}
```

> **重要：`done.answer` 是最终真值。** `token` 事件是增量优化（用于打字机效果），但不保证一定出现。当模型只产出 thinking、未产出正文 token、或检索结果为空时，后端会在 `done.answer` 放兜底文本。前端最终展示必须以 `done.answer` 为准，不能仅依赖 token 拼接。

### 5.5 心跳

SSE 连接空闲 15 秒时发送心跳：

```
:keepalive
```

前端应忽略以 `:` 开头的行（SSE 规范中的注释行）。

### 5.6 error 事件

```
event: error
data: {"message": "答案生成失败: ..."}
```

收到 `error` 后应关闭 SSE 连接。

---

## 6. 前端集成建议

### 6.1 推荐使用流式接口

对于聊天场景，推荐使用流式接口（2.2 + 2.3）而非同步接口（2.1）：

- 用户能立即看到"正在处理"的反馈
- `knowledge` 意图可以逐 token 渲染，体验更好
- 搜索类意图通过 SSE 也能快速返回完整结果

### 6.2 渲染策略

```
收到 submit 响应后，根据 intent 决定初始 UI：

if intent == "course_intro":
    显示"正在搜索课程..."
    等待 done → 渲染课程卡片列表

if intent == "question_search":
    显示"正在搜索题目..."
    等待 done → 渲染题目列表

if intent == "knowledge":
    显示"正在思考..."
    收到 status(generating) → 准备文本区域
    收到 token → 实时追加文本
    收到 citation → 渲染引用来源
    收到 done → 结束流式渲染
```

### 6.3 answer 字段兼容

`answer` 字段在所有意图类型下都有值：
- 搜索类 = `summary` 的副本
- 知识类 = LLM 生成的完整回答

如果前端只想做最简实现，可以统一展示 `answer` 字段为 Markdown。

### 6.4 session_id 管理

- 前端负责生成和维护 `session_id`
- 同一会话使用同一个 `session_id`，后端通过它关联多轮对话
- 新开对话时生成新的 `session_id`
- 建议格式：UUID 或时间戳前缀的随机串

### 6.5 SSE 连接示例（JavaScript）

```javascript
// 1. 提交查询
const submitRes = await fetch('/chat/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, session_id }),
});
const { task_id, intent } = await submitRes.json();

// 2. 建立 SSE 连接
const eventSource = new EventSource(`/chat/stream/${task_id}`);

eventSource.addEventListener('status', (e) => {
  const { phase, message } = JSON.parse(e.data);
  updateStatusUI(message);
});

eventSource.addEventListener('token', (e) => {
  const { text } = JSON.parse(e.data);
  appendToAnswer(text);
});

eventSource.addEventListener('citation', (e) => {
  const { citations } = JSON.parse(e.data);
  renderCitations(citations);
});

eventSource.addEventListener('done', (e) => {
  const result = JSON.parse(e.data);
  finalizeAnswer(result);
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  // SSE 规范的 error 事件（连接断开等）
  if (eventSource.readyState === EventSource.CLOSED) return;
  // 后端推送的 error 事件
  try {
    const { message } = JSON.parse(e.data);
    showError(message);
  } catch {
    showError('连接中断');
  }
  eventSource.close();
});
```

### 6.6 CORS 配置

后端已支持 CORS 配置（通过 `.env` 文件）：

```env
CORS_ALLOW_ORIGINS=["http://localhost:3000","http://localhost:5173"]
CORS_ALLOW_CREDENTIALS=true
```

联调前请确认后端 `.env` 中已添加前端开发服务器地址。
