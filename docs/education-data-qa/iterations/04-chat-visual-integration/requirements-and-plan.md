# Iteration 04：聊天接入与可视化联调

## 背景

Iteration 03 完成后，`POST /analytics/query` 已能通过 LLM 驱动的 NL2SQL 返回完整 `DataQaResult`。前端已完成 mock 版数据问数体验：模式开关、stat/line/bar/table 图表、SQL/口径/trace 折叠面板、错误态渲染。

当前缺失的是两者之间的桥接，且旧 RAG 代码仍在占据主路由：

1. `/chat/query` 强依赖 `classify_intent` 和旧 RAG 服务（document_search、course_search、question_search），这些与教育问数无关。
2. `ChatResponse` / `ChatMessage` 没有 `mode` 和 `blocks` 字段。
3. 问数结果无法保存到聊天历史，刷新后丢失。
4. 前端仍使用 mock 数据，未切换到真实后端。

本轮先删除旧 RAG 全部代码（intent_classifier、Milvus/MinIO 文档搜索、课程搜索、题库搜索、文档导入、processor、旧 stream/RAG 分支），再重建干净的 `mode=data_qa` 聊天路由，最后完成前后端联调。

本轮的工作量集中在旧代码清理、后端聊天层重建和前后端联调，不涉及 NL2SQL pipeline 或前端组件的新开发。

## 目标

1. 删除旧文档 RAG 全部代码，聊天路由不再依赖意图分类器和旧搜索服务。
2. 后端 `/chat/query` 只支持 `mode=data_qa`，调用已有 `run_data_qa` 并以 block 结构返回。
3. 聊天历史持久化完整 `DataQaResult`，刷新后可恢复。
4. 前端关闭 mock 后，真实后端数据驱动图表和调试面板。

## 范围

本轮覆盖：

- 删除旧 RAG 代码（intent_classifier、document_search、course_search、question_search、ingest、processor、旧 stream/RAG 分支及相关测试）。
- `ChatRequest` / `ChatResponse` / `ChatMessage` 模型扩展。
- `/chat/query mode=data_qa` 路由重建。
- 聊天历史持久化 mode + blocks。
- 前端 mock→真实切换。
- 端到端联调验证。
- Bundle 和回归检查。

本轮不覆盖：

- NL2SQL pipeline 修改（Iter 03 已完成）。
- 前端图表组件新开发（已完成）。
- meta_qa 模式（Iter 05）。
- 流式问数。
- 新指标或新图表类型。

## 关键设计

### 1. 删除旧 RAG，重建干净路由

旧代码删除后，`/chat/query` 直接调用 `run_data_qa`：

```python
# 删除 classify_intent、document_search、course_search、question_search
# 删除 chat_sync.py（旧意图路由分发）
# 删除 processor/ 整个目录
# 删除 ingest.py、search.py 路由

# 新路由只支持显式 data_qa
if mode == "data_qa":
    result = run_data_qa(query)
    # 包装为 ChatResponse + blocks
else:
    # 返回 400，不做静默降级
```

### 2. blocks 结构

data_qa 模式的 `ChatResponse.blocks` 必须包含：

```json
[
  { "type": "markdown", "content": "<answer 文本>" },
  { "type": "data_qa_result", "data": "<完整 DataQaResult>" }
]
```

- `blocks[].data` 必须是完整 `DataQaResult` 对象，不是字符串。
- 错误态也使用同样的 block 结构，`DataQaResult.error` 非空。

### 3. 历史持久化

问数 assistant 消息写入聊天历史时，必须保留：

| 字段 | 要求 |
|------|------|
| `mode` | `"data_qa"` |
| `result_type` | `"data_qa_result"` |
| `blocks` | 含完整 `DataQaResult`，包括 `visual`、`explain`、`trace`、`error` |
| `answer` | 文本摘要，兼容旧前端 |

禁止：

- 只保存 `answer` 文本，丢弃 `blocks`。
- 把 `DataQaResult` 序列化为字符串存储。
- 历史回放时从 `answer` 反推图表数据。

### 4. 前端不改业务逻辑

前端图表组件（`DataQaResultView`）已完成，本轮只做数据源切换：

- `useMock=false` 时走真实接口。
- `DataQaResultView` 消费 `DataQaResult`，不改渲染逻辑。
- 前端不重新排序、聚合、计算、推断业务语义。

## 实施计划

### Task 0：删除旧 RAG 代码

**删除范围：**

| 文件/目录 | 说明 |
|---|---|
| `knowledge/api/routes/ingest.py` | 文档导入路由 |
| `knowledge/api/routes/search.py` | 旧搜索路由 |
| `knowledge/service/intent_classifier.py` | 三分类意图识别 |
| `knowledge/service/document_search.py` | Milvus 文档搜索 |
| `knowledge/service/course_search.py` | MongoDB 课程搜索 |
| `knowledge/service/question_search.py` | MongoDB 题库搜索 |
| `knowledge/service/chat_sync.py` | 旧意图路由分发 |
| `knowledge/service/chat_formatter.py` | 旧格式化 |
| `knowledge/service/chat_stream.py` | 旧流式 RAG 路由框架 |
| `knowledge/processor/` | 整个目录（chunker、docx、milvus_store、image_uploader 等） |
| 旧 RAG 相关测试 | test_document_pipeline、test_document_search、test_chunker、test_docx_converter、test_milvus_store、test_ingest_routes、test_intent_classifier、test_course_search、test_question_search、test_hyde_search、test_rerank、test_embedder、test_catalog_parser、test_question_parser、旧 stream/RAG 测试 |

**保留：**

| 文件 | 原因 |
|---|---|
| `knowledge/service/chat_history.py` | data_qa 和后续 meta_qa 聊天历史持久化 |
| `knowledge/core/clients.py` 中的 `get_mongo_db` | 聊天历史依赖 |

**同步修改：**

- `knowledge/api/app.py`：移除 `ingest_router`、`search_router` 注册。
- `knowledge/api/routes/chat.py`：移除 `/chat/query/stream` 和 `/chat/stream/{task_id}` 旧 RAG/SSE 入口；未来如需要流式问数，另起基于 `data_qa/meta_qa` 的设计。
- 清理 `knowledge/core/clients.py` 中仅服务旧 RAG 的 client（如 `get_milvus`），保留 `get_mongo_db`、`get_openai`、`get_async_openai`。
- 应用启动路径不得再 import `chat_sync`、`intent_classifier`、`knowledge.processor`。

**验收：**

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/python -c "from knowledge.api.app import app; print('OK')"
SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
```

### Task 1：ChatRequest / ChatResponse / ChatMessage 模型扩展

**文件：**

- `education_brain/knowledge/models/chat.py`
- `education_brain/knowledge/api/routes/chat.py`

**工作：**

- `ChatRequest` 增加必填 `mode: Literal["data_qa"]`。
- `ChatResponse` 增加 `mode: str` 和 `blocks: list[dict] | None = None`。
- `ChatMessage` 增加 `mode: str` 和 `blocks: list[dict] | None = None`。

**验收：**

- 传 `mode=data_qa` 时 FastAPI 能正确解析。
- 不传 mode 或传未知 mode 返回 400。
- 不保留 `knowledge` 默认模式，不做旧问答兼容分支。

### Task 2：data_qa 路由分发

**文件：**

- `education_brain/knowledge/api/routes/chat.py`

**工作：**

- `POST /chat/query` 重写：删除旧 `classify_intent` 调用，直接调用 `run_data_qa(query)`。
- 将 `DataQaResult` 包装为 `ChatResponse`：
  - `result_type = "data_qa_result"`
  - `mode = "data_qa"`
  - `answer = data_qa_result["answer"]`
  - `blocks = [{"type": "markdown", ...}, {"type": "data_qa_result", "data": data_qa_result}]`
- 问数失败时仍返回 HTTP 200 + 结构化 `DataQaResult.error`，不抛 HTTP 500。

**验收：**

```bash
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "本月总收入是多少？", "mode": "data_qa", "session_id": "test_iter04"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['result_type']=='data_qa_result'; assert d['blocks'][1]['type']=='data_qa_result'; print('OK')"
```

### Task 3：聊天历史持久化

**文件：**

- `education_brain/knowledge/service/chat_history.py`

**工作：**

- `save_message` 写入 `mode` 和 `blocks`。
- `get_recent_messages` 读取时恢复完整 `blocks`。

**验收：**

```bash
# 发送问数请求
curl -s -X POST http://localhost:8000/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "本月总收入是多少？", "mode": "data_qa", "session_id": "test_history"}'

# 验证历史恢复
curl -s "http://localhost:8000/chat/history?session_id=test_history&limit=5" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
msgs = [m for m in d['messages'] if m.get('mode') == 'data_qa' and m['role'] == 'assistant']
assert len(msgs) > 0, 'no data_qa assistant message'
blocks = msgs[-1].get('blocks', [])
qa_blocks = [b for b in blocks if b.get('type') == 'data_qa_result']
assert len(qa_blocks) > 0, 'no data_qa_result block'
assert 'visual' in qa_blocks[0]['data'], 'DataQaResult missing visual'
assert 'sql' in qa_blocks[0]['data'].get('explain', {}), 'DataQaResult missing explain.sql'
print('OK')
"
```

### Task 4：前端 mock→真实切换

**文件：**

- `education_brain_front/src/app/api/chat.ts`
- 环境配置（`.env` 或 `vite.config.ts`）

**工作：**

- 确保 `useMock=false` 时 `mode=data_qa` 走 `POST /chat/query` 真实接口。
- 不修改 `DataQaResultView` 组件逻辑。

**验收：**

- 关闭 mock 后，浏览器中发送"本月总收入是多少？"返回真实 stat 指标卡。

### Task 5：历史回放验证

**工作：**

- 发送问数后刷新页面，验证历史恢复。
- 确认 SQL / 口径 / trace 折叠面板内容来自真实后端。
- 错误态从历史恢复后仍渲染为 `DataQaResultView`，不退化成普通 markdown。

**验收：**

- 刷新后 `data_qa_result` block 仍展示为图表和调试面板。
- SQL / 口径 / trace 可展开。
- 错误态可恢复。

### Task 6：端到端联调验证

**工作：**

- 联调五类结果：stat / line / bar / table / error。
- 确认每类结果在浏览器中可见、可交互、可展开 SQL/trace。
- 执行真实依赖全流程 smoke：`SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh`。

**验收：**

- “本月总收入是多少？”渲染为 `stat`。
- “最近30天收入趋势如何？”渲染为 `line`。
- “哪个校区收入最高？”渲染为 `bar`。
- “查看本月新报名学员明细”渲染为 `table`。
- “本月总收入是多少？; DROP TABLE order;”渲染为结构化错误态。
- `SMOKE_STAGE=e2e` 通过，且该阶段走真实 MySQL、Qdrant、Elasticsearch、Embedding、LLM、API 和聊天历史，不使用 fixture 或 mock。

### Task 7：Bundle 与回归

**工作：**

- `npm run build` 通过，无大 chunk 警告。
- Recharts / DataQaResultView 保持按需加载。
- 旧问答/RAG smoke 不再维护；本轮回归以 `SMOKE_STAGE=llm/chat/e2e` 和前端 build 为准。

## 验收标准

- 旧 RAG 代码已完全删除，`app.py` 中无 ingest/search 路由注册。
- 旧 `/chat/query/stream` 和 `/chat/stream/{task_id}` 不再注册，应用启动不再 import 旧 RAG 模块。
- `/chat/query` 不传 mode 或传未知 mode 返回 400。
- `mode=data_qa` 返回 `result_type=data_qa_result` 和完整 `blocks`。
- `blocks[].data` 是完整 `DataQaResult` 对象。
- 聊天历史可恢复问数 assistant 消息，包含 mode + blocks + SQL + trace。
- 问数失败也保存为 assistant 消息，包含结构化 `error`。
- 五类结果在浏览器中使用真实后端数据渲染。
- 刷新后问数图表和错误态可恢复。
- `SMOKE_STAGE=llm` trace 显示真实 LLM 调用。
- `npm run build` 无大 chunk 警告。

## 风险与取舍

- 删除旧 RAG 后不可回退：这是有意取舍，当前产品主线是教育经营数据问数，旧文档 RAG 不属于教育问数系统。
- 聊天历史存储 blocks 增加存储体积：`DataQaResult` 含 `visual.rows` 可能较大，但对学习项目可接受。
- 前端 API 层存在 mock/真实两条路径：保持 `useMock` 开关，方便开发调试，但联调验收必须关闭 mock。

## Stop / Ask

遇到以下情况先停下来对齐：

- 聊天历史存储（MongoDB）不支持嵌套 JSON 字段，需要改存储方案。
- 后端返回的 `DataQaResult` 与 `api-contract.md` 定义有字段差异。
- 联调时 `visual.columns[].key` 与 `visual.rows[]` 不对齐。
- 联调时 trace 中缺少 LLM 调用记录（可能意味着 Iter 03 退化为规则）。
