# 教育问数 API 契约 v0.1

日期：2026-05-18

本文档用于先行固定教育问数前后端契约，便于前端在 Iteration 02/03 后端完成前使用 mock 数据开发。

## 1. 设计原则

- `POST /analytics/query` 是问数能力的最小稳定接口，直接返回 `DataQaResult`。
- 聊天接入只是在 `ChatResponse` / `ChatMessage` 中包一层 block，不改变 `DataQaResult` 内部结构。
- 前端图表只根据 `visual.type`、`visual.columns`、`visual.rows`、`visual.x`、`visual.y` 渲染，不重新推断业务语义。
- SQL、指标口径、trace、warnings、error 都是调试和教学信息，必须完整保留到聊天历史。
- 本版暂不定义流式问数。`mode=data_qa` 使用同步返回；现有 `/chat/query/stream` 继续服务普通知识问答。

## 2. 公共类型

### 2.1 DataQaResult

```ts
type DataQaResult = {
  queryId: string
  mode: 'data_qa'
  question: string
  answer: string
  intent: DataQaIntent
  visual: DataQaVisual
  explain: DataQaExplain
  trace: DataQaTrace
  warnings: string[]
  error?: DataQaError
}
```

### 2.2 DataQaIntent

```ts
type DataQaIntent = {
  analysisType: 'single_metric' | 'trend' | 'ranking' | 'comparison' | 'detail'
  metrics: string[]
  dimensions: string[]
  filters: Array<{
    field: string
    op: 'eq' | 'ne' | 'in' | 'not_in' | 'gt' | 'gte' | 'lt' | 'lte' | 'between' | 'is_null' | 'is_not_null' | string
    value: unknown
    label?: string
  }>
  timeRange?: {
    start: string      // ISO date: YYYY-MM-DD
    end: string        // ISO date: YYYY-MM-DD
    grain?: 'day' | 'week' | 'month'
    label?: string
  }
  sort?: Array<{ field: string; direction: 'asc' | 'desc' }>
  limit?: number
}
```

### 2.3 DataQaVisual

```ts
type DataQaVisual = {
  type: 'stat' | 'line' | 'bar' | 'table'
  title: string
  columns: Array<{
    key: string
    label: string
    type: 'string' | 'number' | 'date' | 'percent' | 'currency'
    unit?: string
    precision?: number
  }>
  rows: Array<Record<string, unknown>>
  x?: string
  y?: string[]
}
```

规则：

- `visual.columns[].key` 必须能在每个 `visual.rows[]` 中找到。
- `stat` 也使用 `columns + rows`，通常只有 1 行。
- `line` 必须提供 `x` 和 `y`。
- `bar` 推荐提供 `x` 和 `y`，用于排名图。
- `table` 可以不提供 `x` / `y`。

### 2.4 DataQaExplain

```ts
type DataQaExplain = {
  sql: string
  metrics: Array<{
    id: string
    name: string
    formula: string
    description: string
    unit?: string
  }>
  tables: string[]
  columns: string[]
  joins: string[]
  assumptions: string[]
}
```

### 2.5 DataQaTrace

```ts
type DataQaTrace = {
  stages: Array<{
    name:
      | 'extract_keywords'
      | 'recall_column'
      | 'recall_metric'
      | 'recall_value'
      | 'merge_retrieved_info'
      | 'filter_table'
      | 'filter_metric'
      | 'add_extra_context'
      | 'generate_sql'
      | 'validate_sql'
      | 'correct_sql'
      | 'execute_sql'
      | string
    status: 'ok' | 'error' | 'skipped'
    durationMs?: number
    message?: string
  }>
  rowCount: number
  durationMs: number
}
```

### 2.6 DataQaError

```ts
type DataQaError = {
  stage: string
  code:
    | 'RECALL_EMPTY'
    | 'JOIN_PATH_NOT_FOUND'
    | 'LLM_UNAVAILABLE'
    | 'SQL_UNSAFE'
    | 'SQL_VALIDATE_FAILED'
    | 'SQL_EXECUTE_FAILED'
    | 'EMPTY_RESULT'
    | string
  message: string
}
```

错误返回仍然使用 `DataQaResult`。此时：

- `answer` 是面向用户的失败说明。
- `visual.type` 通常为 `table`，`rows` 可为空。
- `error` 必须存在。
- `trace.stages` 必须标记失败阶段，未执行阶段标记 `skipped`。

## 3. 问数接口

### 3.1 POST /analytics/query

直接执行自然语言问数，不经过聊天历史。

Request:

```json
{
  "question": "本月总收入是多少？",
  "session_id": "session_web_001"
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `question` | string | 是 | 用户自然语言问题 |
| `session_id` | string | 否 | 用于 trace / 调试关联；不负责聊天历史持久化 |

Response: `DataQaResult`

### 3.2 成功示例：stat

```json
{
  "queryId": "dq_20260518_0001",
  "mode": "data_qa",
  "question": "本月总收入是多少？",
  "answer": "本月总收入为 128,560.00 元。",
  "intent": {
    "analysisType": "single_metric",
    "metrics": ["paid_revenue"],
    "dimensions": [],
    "filters": [],
    "timeRange": {
      "start": "2026-05-01",
      "end": "2026-05-18",
      "grain": "day",
      "label": "本月"
    }
  },
  "visual": {
    "type": "stat",
    "title": "本月总收入",
    "columns": [
      { "key": "metric", "label": "指标", "type": "string" },
      { "key": "value", "label": "金额", "type": "currency", "unit": "yuan", "precision": 2 }
    ],
    "rows": [
      { "metric": "收入金额", "value": 128560.0 }
    ]
  },
  "explain": {
    "sql": "SELECT SUM(`order`.paid_amount) AS paid_revenue FROM `order` WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') AND `order`.paid_at >= '2026-05-01' AND `order`.paid_at < '2026-05-19'",
    "metrics": [
      {
        "id": "paid_revenue",
        "name": "收入金额",
        "formula": "SUM(order.paid_amount)",
        "description": "已支付成功订单的实收金额总和",
        "unit": "yuan"
      }
    ],
    "tables": ["order"],
    "columns": ["order.paid_amount", "order.order_status", "order.paid_at"],
    "joins": [],
    "assumptions": ["未指定校区或课程时统计全部订单。"]
  },
  "trace": {
    "stages": [
      { "name": "extract_keywords", "status": "ok", "durationMs": 8 },
      { "name": "recall_metric", "status": "ok", "durationMs": 42 },
      { "name": "recall_column", "status": "ok", "durationMs": 40 },
      { "name": "recall_value", "status": "ok", "durationMs": 15 },
      { "name": "merge_retrieved_info", "status": "ok", "durationMs": 9 },
      { "name": "generate_sql", "status": "ok", "durationMs": 920 },
      { "name": "validate_sql", "status": "ok", "durationMs": 14 },
      { "name": "execute_sql", "status": "ok", "durationMs": 18 }
    ],
    "rowCount": 1,
    "durationMs": 1066
  },
  "warnings": []
}
```

### 3.3 成功示例：line

```json
{
  "queryId": "dq_20260518_0002",
  "mode": "data_qa",
  "question": "最近30天收入趋势如何？",
  "answer": "最近 30 天收入整体呈波动上升趋势。",
  "intent": {
    "analysisType": "trend",
    "metrics": ["paid_revenue"],
    "dimensions": ["paid_date"],
    "filters": [],
    "timeRange": {
      "start": "2026-04-19",
      "end": "2026-05-18",
      "grain": "day",
      "label": "最近30天"
    },
    "sort": [{ "field": "paid_date", "direction": "asc" }]
  },
  "visual": {
    "type": "line",
    "title": "最近30天收入趋势",
    "columns": [
      { "key": "paid_date", "label": "日期", "type": "date" },
      { "key": "paid_revenue", "label": "收入金额", "type": "currency", "unit": "yuan", "precision": 2 }
    ],
    "rows": [
      { "paid_date": "2026-04-19", "paid_revenue": 3200.0 },
      { "paid_date": "2026-04-20", "paid_revenue": 4280.0 },
      { "paid_date": "2026-04-21", "paid_revenue": 3860.0 },
      { "paid_date": "2026-04-22", "paid_revenue": 5120.0 }
    ],
    "x": "paid_date",
    "y": ["paid_revenue"]
  },
  "explain": {
    "sql": "SELECT DATE(`order`.paid_at) AS paid_date, SUM(`order`.paid_amount) AS paid_revenue FROM `order` WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') AND `order`.paid_at >= '2026-04-19' AND `order`.paid_at < '2026-05-19' GROUP BY DATE(`order`.paid_at) ORDER BY paid_date ASC",
    "metrics": [
      {
        "id": "paid_revenue",
        "name": "收入金额",
        "formula": "SUM(order.paid_amount)",
        "description": "已支付成功订单的实收金额总和",
        "unit": "yuan"
      }
    ],
    "tables": ["order"],
    "columns": ["order.paid_amount", "order.order_status", "order.paid_at"],
    "joins": [],
    "assumptions": []
  },
  "trace": {
    "stages": [
      { "name": "extract_keywords", "status": "ok", "durationMs": 7 },
      { "name": "recall_metric", "status": "ok", "durationMs": 39 },
      { "name": "generate_sql", "status": "ok", "durationMs": 980 },
      { "name": "validate_sql", "status": "ok", "durationMs": 13 },
      { "name": "execute_sql", "status": "ok", "durationMs": 22 }
    ],
    "rowCount": 30,
    "durationMs": 1120
  },
  "warnings": []
}
```

### 3.4 成功示例：bar

```json
{
  "queryId": "dq_20260518_0003",
  "mode": "data_qa",
  "question": "哪个校区收入最高？",
  "answer": "收入最高的校区是朝阳校区，收入为 56,300.00 元。",
  "intent": {
    "analysisType": "ranking",
    "metrics": ["paid_revenue"],
    "dimensions": ["campus"],
    "filters": [],
    "sort": [{ "field": "paid_revenue", "direction": "desc" }],
    "limit": 10
  },
  "visual": {
    "type": "bar",
    "title": "校区收入排名",
    "columns": [
      { "key": "campus_name", "label": "校区", "type": "string" },
      { "key": "paid_revenue", "label": "收入金额", "type": "currency", "unit": "yuan", "precision": 2 }
    ],
    "rows": [
      { "campus_name": "朝阳校区", "paid_revenue": 56300.0 },
      { "campus_name": "海淀校区", "paid_revenue": 42180.0 },
      { "campus_name": "浦东校区", "paid_revenue": 30120.0 }
    ],
    "x": "campus_name",
    "y": ["paid_revenue"]
  },
  "explain": {
    "sql": "SELECT org_campus.campus_name, SUM(`order`.paid_amount) AS paid_revenue FROM `order` JOIN order_item ON order_item.order_id = `order`.id JOIN series_cohort ON series_cohort.id = order_item.cohort_id JOIN org_campus ON org_campus.id = series_cohort.campus_id WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') GROUP BY org_campus.campus_name ORDER BY paid_revenue DESC LIMIT 10",
    "metrics": [
      {
        "id": "paid_revenue",
        "name": "收入金额",
        "formula": "SUM(order.paid_amount)",
        "description": "已支付成功订单的实收金额总和",
        "unit": "yuan"
      }
    ],
    "tables": ["order", "order_item", "series_cohort", "org_campus"],
    "columns": ["order.paid_amount", "order.order_status", "order_item.cohort_id", "series_cohort.campus_id", "org_campus.campus_name"],
    "joins": [
      "order.id = order_item.order_id",
      "order_item.cohort_id = series_cohort.id",
      "series_cohort.campus_id = org_campus.id"
    ],
    "assumptions": ["未指定时间范围时统计全部可用订单数据。"]
  },
  "trace": {
    "stages": [
      { "name": "extract_keywords", "status": "ok", "durationMs": 7 },
      { "name": "recall_metric", "status": "ok", "durationMs": 41 },
      { "name": "merge_retrieved_info", "status": "ok", "durationMs": 18 },
      { "name": "generate_sql", "status": "ok", "durationMs": 1010 },
      { "name": "validate_sql", "status": "ok", "durationMs": 15 },
      { "name": "execute_sql", "status": "ok", "durationMs": 24 }
    ],
    "rowCount": 3,
    "durationMs": 1198
  },
  "warnings": []
}
```

### 3.5 错误示例

```json
{
  "queryId": "dq_20260518_0004",
  "mode": "data_qa",
  "question": "本月总收入是多少？; DROP TABLE order;",
  "answer": "这个问题包含不安全的 SQL 片段，系统已停止执行。",
  "intent": {
    "analysisType": "single_metric",
    "metrics": ["paid_revenue"],
    "dimensions": [],
    "filters": []
  },
  "visual": {
    "type": "table",
    "title": "问数失败",
    "columns": [
      { "key": "message", "label": "说明", "type": "string" }
    ],
    "rows": [
      { "message": "请求包含不安全 SQL 片段，未执行查询。" }
    ]
  },
  "explain": {
    "sql": "",
    "metrics": [],
    "tables": [],
    "columns": [],
    "joins": [],
    "assumptions": []
  },
  "trace": {
    "stages": [
      { "name": "extract_keywords", "status": "ok", "durationMs": 5 },
      { "name": "generate_sql", "status": "skipped", "message": "unsafe input" },
      { "name": "validate_sql", "status": "skipped" },
      { "name": "execute_sql", "status": "skipped" }
    ],
    "rowCount": 0,
    "durationMs": 6
  },
  "warnings": ["已拦截疑似 SQL 注入输入。"],
  "error": {
    "stage": "input_guard",
    "code": "SQL_UNSAFE",
    "message": "输入包含危险 SQL 片段。"
  }
}
```

## 4. 聊天接入接口

### 4.1 POST /chat/query

普通知识问答保持现有行为。数据问数模式增加 `mode=data_qa`。

Request:

```json
{
  "query": "本月总收入是多少？",
  "mode": "data_qa",
  "session_id": "session_web_001"
}
```

字段：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---:|---|---|
| `query` | string | 是 | - | 用户输入 |
| `mode` | `'knowledge' \| 'data_qa'` | 否 | `knowledge` | 显式模式开关 |
| `session_id` | string | 否 | 后端生成 | 聊天会话 ID |

Response:

```ts
type ChatResponse = {
  task_id: string
  intent: string
  result_type: 'answer' | 'search_result' | 'data_qa_result' | string
  mode?: 'knowledge' | 'data_qa'
  items: unknown[]
  summary: string
  answer: string
  citations: unknown[]
  blocks?: ChatBlock[]
}

type ChatBlock =
  | { type: 'markdown'; content: string }
  | { type: 'data_qa_result'; data: DataQaResult }
```

`mode=data_qa` 成功响应示例：

```json
{
  "task_id": "chat_task_001",
  "intent": "data_qa",
  "result_type": "data_qa_result",
  "mode": "data_qa",
  "items": [],
  "summary": "本月总收入为 128,560.00 元。",
  "answer": "本月总收入为 128,560.00 元。",
  "citations": [],
  "blocks": [
    { "type": "markdown", "content": "本月总收入为 128,560.00 元。" },
    {
      "type": "data_qa_result",
      "data": {
        "queryId": "dq_20260518_0001",
        "mode": "data_qa",
        "question": "本月总收入是多少？",
        "answer": "本月总收入为 128,560.00 元。",
        "intent": {
          "analysisType": "single_metric",
          "metrics": ["paid_revenue"],
          "dimensions": [],
          "filters": []
        },
        "visual": {
          "type": "stat",
          "title": "本月总收入",
          "columns": [
            { "key": "metric", "label": "指标", "type": "string" },
            { "key": "value", "label": "金额", "type": "currency", "unit": "yuan", "precision": 2 }
          ],
          "rows": [{ "metric": "收入金额", "value": 128560.0 }]
        },
        "explain": {
          "sql": "SELECT SUM(`order`.paid_amount) AS paid_revenue FROM `order` WHERE `order`.paid_at >= '2026-05-01'",
          "metrics": [
            {
              "id": "paid_revenue",
              "name": "收入金额",
              "formula": "SUM(order.paid_amount)",
              "description": "已支付成功订单的实收金额总和"
            }
          ],
          "tables": ["order"],
          "columns": ["order.paid_amount", "order.paid_at"],
          "joins": [],
          "assumptions": []
        },
        "trace": {
          "stages": [{ "name": "execute_sql", "status": "ok", "durationMs": 18 }],
          "rowCount": 1,
          "durationMs": 1066
        },
        "warnings": []
      }
    }
  ]
}
```

### 4.2 GET /chat/history

Request:

```text
GET /chat/history?session_id=session_web_001&limit=20
```

Response:

```ts
type ChatHistoryResponse = {
  session_id: string
  messages: ChatMessage[]
}

type ChatMessage = {
  session_id?: string
  task_id: string
  role: 'user' | 'assistant'
  content: string
  intent: string
  result_type?: string
  mode?: 'knowledge' | 'data_qa'
  items?: unknown[]
  summary?: string
  answer?: string
  citations?: unknown[]
  blocks?: ChatBlock[]
  created_at: string
}
```

`mode=data_qa` 的 assistant 历史消息必须保留：

- `mode: "data_qa"`
- `result_type: "data_qa_result"`
- `blocks[].type === "data_qa_result"`
- 完整 `DataQaResult.explain.sql`
- 完整 `DataQaResult.explain.metrics`
- 完整 `DataQaResult.trace`
- `warnings` / `error`

## 5. 前端 mock 建议

前端可以先 mock 两层数据：

1. 直接 mock `POST /analytics/query`，用于独立开发图表、表格、SQL 折叠和错误态组件。
2. mock `POST /chat/query mode=data_qa` 和 `GET /chat/history`，用于开发聊天消息中的 block 渲染和刷新回放。

推荐文件组织：

```text
education_brain_front/src/app/types/data-qa.ts
education_brain_front/src/app/mock/data-qa.ts
education_brain_front/src/app/components/data-qa-result.tsx
```

最小前端渲染分层：

| 组件 | 输入 | 责任 |
|---|---|---|
| `DataQaResultView` | `DataQaResult` | 总入口，处理成功/错误/warnings |
| `DataQaVisual` | `DataQaVisual` | 按 `type` 分派 stat/line/bar/table |
| `DataQaTable` | `columns + rows` | 所有类型的兜底表格 |
| `DataQaExplainPanel` | `explain + trace` | SQL、口径、表、join、trace 折叠展示 |

前端不需要等待真实 NL2SQL 完成，可以用本文件 3.2、3.3、3.4、3.5 的 JSON 作为 mock fixture。

## 6. 与当前实现的差异

当前仓库状态：

- 已实现 `/analytics/health`、`/analytics/meta/metrics`、`/analytics/meta/columns`、`/analytics/meta/values`。
- 尚未实现 `POST /analytics/query`。
- 当前 `ChatRequest` 尚未包含 `mode`。
- 当前 `ChatResponse` / `ChatMessage` 尚未包含 `blocks`。
- 当前前端聊天默认使用 `/chat/query/stream` + SSE。

因此本契约是 Iteration 02-04 的目标接口，不表示当前后端已经全部可用。

## 7. 验收对齐

后续 smoke test 应至少覆盖：

- `POST /analytics/query` 三个成功问题：stat、line、bar。
- SQL 注入或多语句输入返回结构化 `error`，且 `execute_sql` 为 `skipped`。
- `POST /chat/query mode=data_qa` 返回 `result_type=data_qa_result` 和 `data_qa_result` block。
- `GET /chat/history` 能恢复完整 `blocks` 和 SQL/口径/trace。
- `visual.columns[].key` 与 `visual.rows[]` 对齐。
