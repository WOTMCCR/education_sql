# Iteration 04 Frontend Functionality: 数据问数可视化与联调准备

日期：2026-05-18

本文档固定 Iteration 04 前端功能目标、当前 mock 实现状态、后端联调要求和验收方式。后续真实后端接入时，以 `../../api-contract.md` 的 `DataQaResult` 为数据源，以本文档作为前端行为验收标准。

## 1. 当前前端基线

当前前端已完成 mock 版数据问数体验，目标是让 UI、图表、错误态和调试面板先稳定，再等待 Iteration 02/03 后端真实接口接入。

已实现文件：

```text
education_brain_front/src/app/types/data-qa.ts
education_brain_front/src/app/mock/data-qa.ts
education_brain_front/src/app/components/data-qa-result.tsx
education_brain_front/src/app/api/chat.ts
education_brain_front/src/app/mock/chat.ts
education_brain_front/src/app/pages/chat-page.tsx
education_brain_front/src/app/components/layout.tsx
education_brain_front/src/app/routes.tsx
education_brain_front/src/app/App.tsx
education_brain_front/vite.config.ts
```

当前 mock 覆盖：

| 场景 | 问题示例 | visual.type | 目的 |
|---|---|---|---|
| 单指标 | 本月总收入是多少？ | `stat` | 验证指标卡、货币格式 |
| 趋势 | 最近30天收入趋势如何？ | `line` | 验证折线图、日期 x 轴、多行表格 |
| 排名 | 哪个校区收入最高？ | `bar` | 验证柱状图、排序结果、维度表格 |
| 明细 | 查看本月新报名学员明细 | `table` | 验证明细表、横向滚动 |
| 错误 | 本月总收入是多少？; DROP TABLE order; | `table` + `error` | 验证错误态、warnings、跳过执行 trace |

当前前端入口：

- 普通问答：保留 `/chat/query/stream` + SSE。
- 数据问数：显式切换到 `mode=data_qa` 后，mock 下同步返回 `data_qa_result` block；真实联调时走 `POST /chat/query` with `mode=data_qa`。
- 当前不实现流式问数。

## 2. 用户可见功能

### 2.1 模式切换

聊天输入区提供显式模式切换：

```text
[普通问答] [数据问数]
```

要求：

- 默认是普通问答。
- 切到数据问数后，输入 placeholder 使用问数示例，例如“最近30天收入趋势如何？”。
- 数据问数请求必须携带 `mode=data_qa`。
- 不做自动意图识别，不根据用户文本猜测是否问数。

### 2.2 问数结果消息

数据问数 assistant 消息渲染为 `DataQaResultView`，而不是普通 markdown 文本。

消息数据来源：

```ts
type ChatBlock =
  | { type: 'markdown'; content: string }
  | { type: 'data_qa_result'; data: DataQaResult }
```

前端渲染规则：

- 只要 assistant message 中存在 `blocks[].type === "data_qa_result"`，就用 `DataQaResultView` 渲染。
- `blocks[].data` 必须是完整 `DataQaResult`。
- `answer` 可作为摘要展示，但不能替代 `DataQaResult`。
- 普通知识问答消息仍使用 markdown 渲染。

### 2.3 图表和表格

前端只根据 `DataQaResult.visual` 渲染：

```ts
visual.type
visual.title
visual.columns
visual.rows
visual.x
visual.y
```

要求：

- `stat`：展示首行的主要数值列，支持 `currency` / `percent` / `number` 格式。
- `line`：使用 `visual.x` 作为 x 轴，`visual.y` 作为序列；同时保留数据表格。
- `bar`：使用 `visual.x` 作为维度，`visual.y` 作为指标；同时保留数据表格。
- `table`：仅展示表格，列顺序使用 `visual.columns`。
- 表格必须横向滚动，不能撑破聊天容器。
- 图表不能在前端重新排序、重新聚合、重新推断指标含义。

### 2.4 SQL / 口径 / Trace 面板

每个问数结果都必须展示默认折叠的辅助面板：

```text
SQL / 口径 / Trace
```

面板展开后展示：

- `queryId`
- SQL
- 指标 ID、名称、公式、描述、单位
- 使用表、字段、join、assumptions
- trace stage 名称、状态、耗时、错误/跳过说明

要求：

- SQL 面板默认折叠。
- SQL 内容允许横向/纵向滚动，不能遮挡输入区。
- trace 中 `ok` / `error` / `skipped` 要有可区分状态。
- 即使问数失败，也必须展示 trace。

### 2.5 错误和警告

错误态仍然使用 `DataQaResult` 渲染，不退化为普通文本。

要求：

- `error` 存在时展示错误 banner，包含 `code`、`stage`、`message`。
- `warnings` 非空时展示 warning 列表。
- `visual.rows` 为空时展示空状态，不渲染空白区域。
- SQL 注入、多语句、SQL 校验失败、召回失败、join path 缺失、空结果都要能恢复为可读 UI。
- 失败消息进入聊天历史后，刷新页面仍能恢复完整错误态。

## 3. 后端联调契约

### 3.1 POST /analytics/query

Iteration 02 完成后，前端可直接用该接口开发和调试图表组件。

Request:

```json
{
  "question": "最近30天收入趋势如何？",
  "session_id": "session_web_001"
}
```

Response:

```ts
DataQaResult
```

前端对该接口的最低要求：

- HTTP 200 时响应体必须是完整 `DataQaResult`。
- 业务失败也返回 `DataQaResult.error`，不要只返回 FastAPI `detail` 字符串。
- `visual.columns[].key` 必须能在每一行 `visual.rows[]` 中找到。
- `trace.rowCount` 必须与结果集行数语义一致；失败时为 0。

### 3.2 POST /chat/query mode=data_qa

Iteration 03 完成后，聊天页通过该接口接入真实问数。

Request:

```json
{
  "query": "哪个校区收入最高？",
  "mode": "data_qa",
  "session_id": "session_web_001"
}
```

Response:

```json
{
  "task_id": "chat_task_001",
  "intent": "data_qa",
  "result_type": "data_qa_result",
  "mode": "data_qa",
  "items": [],
  "summary": "收入最高的校区是朝阳校区，收入为 56,300.00 元。",
  "answer": "收入最高的校区是朝阳校区，收入为 56,300.00 元。",
  "citations": [],
  "blocks": [
    { "type": "markdown", "content": "收入最高的校区是朝阳校区，收入为 56,300.00 元。" },
    { "type": "data_qa_result", "data": "完整 DataQaResult 对象" }
  ]
}
```

真实响应中 `blocks[1].data` 必须是对象，不是字符串。

### 3.3 GET /chat/history

聊天历史必须完整返回问数消息，不能丢字段。

assistant 历史消息最低字段：

```ts
{
  role: 'assistant'
  mode: 'data_qa'
  result_type: 'data_qa_result'
  answer: string
  blocks: Array<{ type: 'data_qa_result'; data: DataQaResult }>
  created_at: string
}
```

必须保留：

- `DataQaResult.visual`
- `DataQaResult.explain.sql`
- `DataQaResult.explain.metrics`
- `DataQaResult.trace`
- `DataQaResult.warnings`
- `DataQaResult.error`

## 4. 前端实现边界

前端负责：

- 模式切换。
- 根据 block 类型选择渲染器。
- 根据 `visual.type` 分派 stat / line / bar / table。
- 根据 `visual.columns` 格式化数值、日期、货币、百分比。
- 展示 SQL / 口径 / trace / warnings / error。
- 处理移动端布局、横向滚动和折叠面板。

前端不负责：

- 指标口径计算。
- SQL 生成、校验、纠错或执行。
- join path 推导。
- 趋势排序、排名排序、聚合计算。
- 把普通问答自动升级为问数。
- 从 `answer` 文本反推图表数据。

## 5. 联调检查清单

### 5.1 后端响应形状

每个真实问数响应先检查：

- [ ] 顶层 `mode === "data_qa"`
- [ ] `queryId` 非空
- [ ] `answer` 非空
- [ ] `intent.analysisType` 合法
- [ ] `visual.type` 合法
- [ ] `visual.columns` 非空
- [ ] `visual.rows` 存在，允许为空数组
- [ ] `visual.columns[].key` 与 `visual.rows[]` 对齐
- [ ] `explain.sql` 成功时非空
- [ ] `explain.metrics` 成功时非空
- [ ] `trace.stages` 非空
- [ ] `trace.rowCount` 是数字
- [ ] 错误时 `error.code`、`error.stage`、`error.message` 非空

### 5.2 首批联调问题

必须联调：

| 问题 | 期望 |
|---|---|
| 本月总收入是多少？ | `analysisType=single_metric`, `visual.type=stat` |
| 最近30天收入趋势如何？ | `analysisType=trend`, `visual.type=line`, 多行结果 |
| 哪个校区收入最高？ | `analysisType=ranking`, `visual.type=bar`, 已排序 |
| 查看本月新报名学员明细 | `analysisType=detail`, `visual.type=table` |
| 本月总收入是多少？; DROP TABLE order; | `error.code=SQL_UNSAFE`, `execute_sql=skipped` |

### 5.3 历史回放

必须验证：

- [ ] 发送 `mode=data_qa` 后，用户消息和 assistant 消息都进入历史。
- [ ] 刷新页面后，问数 assistant 消息仍展示为图表，而不是普通 markdown。
- [ ] SQL / 口径 / trace 能展开。
- [ ] 错误态能从历史恢复。

## 6. 验收命令

后端：

```bash
cd education_brain
SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=all ./knowledge/tests/smoke_test_data_qa.sh
```

前端：

```bash
cd education_brain_front
npm run build
npm test
```

浏览器验证：

```bash
cd education_brain_front
VITE_USE_MOCK=true npm run dev -- --host 127.0.0.1 --port 5173
npx playwright test artifacts/verification/2026-05-18/data-qa-frontend-mock/round-01/data-qa-ui.spec.js --reporter=line
```

说明：

- mock 浏览器验证用于证明前端视觉和交互能力。
- 真实联调完成后，应新增或改造 Playwright 用例，使其使用真实后端返回的 `DataQaResult`。
- 截图证据默认放在 `artifacts/verification/<date>/data-qa-frontend-*/round-*/`。

## 7. 性能与打包要求

当前前端已做基础 code splitting：

- 路由页面使用 `React.lazy`。
- `DataQaResultView` 动态加载，避免 Recharts 进入聊天页主 chunk。
- Vite 拆分 `vendor-react`、`vendor-charts`、`vendor-radix`、通用 `vendor`。

后续要求：

- 不要把图表库直接静态 import 到聊天页主模块。
- 新增重型图表库前必须先评估 bundle 体积和现有 `recharts` 是否足够。
- `npm run build` 不应出现 `chunk larger than 500 kB` 警告；如出现，需说明原因或继续拆分。

## 8. 当前已知限制

- 当前数据问数前端仍使用 mock 数据，真实 `/analytics/query` 和 `/chat/query mode=data_qa` 尚未完全接入。
- 当前不支持流式问数。
- 当前图表只覆盖 stat / line / bar / table，不覆盖组合图、双轴图、导出、钻取。
- 移动端当前隐藏全局侧边栏和会话侧边栏，优先保证问数结果可读；后续如需要移动端导航，可单独设计抽屉菜单。
