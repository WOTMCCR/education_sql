# Iteration 04 Goal: 聊天接入与可视化联调

## Pre-flight

本轮 pre-flight 的核心目标：**证明 Iteration 03 交付的 NL2SQL 是 LLM 驱动的，而非规则脚本伪装。** 使用只读 reviewer subagent（当前可用角色优先用 `explorer`）执行以下全部检查。任一项不通过则本轮不得开始。

### P1: LLM 真实性验证（最高优先级）

- [ ] **代码审计**：review `education_brain/knowledge/analytics/agent/nodes/` 下的 `expand_search_keywords`、`structure_intent`、`filter_table`、`filter_metric`、`generate_sql`、`correct_sql` 节点，确认每个节点内部存在对 `knowledge.core.llm.chat_completion_text` 或等价 OpenAI SDK 调用的真实调用路径，而不是 `if analysisType == "trend": sql = f"SELECT..."` 或关键词匹配分支。
- [ ] **Prompt 文件存在**：`education_brain/knowledge/analytics/agent/prompts/` 下至少存在 `expand_keywords`、`structure_intent`、`generate_sql` 三个 prompt 模板文件。
- [ ] **Schema 校验**：`StructuredIntent` 和 `SqlPlan` 的 Pydantic model 存在且被 LLM 输出解析流程引用。
- [ ] **Smoke 真实调用**：执行以下命令，检查返回的 `trace.stages` 中至少 `expand_search_keywords`、`structure_intent`、`generate_sql` 三个节点记录了 LLM 调用（存在 `llm_usage` 或 `durationMs > 200ms` 等 LLM 调用特征）：
  ```bash
  cd education_brain
  curl -s -X POST http://localhost:8000/analytics/query \
    -H 'Content-Type: application/json' \
    -d '{"question": "本月总收入是多少？"}' | python3 -m json.tool
  ```
- [ ] **反面验证**：临时将 `OPENAI_API_KEY` 设为无效值或清空，重新请求，确认返回 `error.code = "LLM_UNAVAILABLE"`，而不是静默走规则 fallback 返回正确结果。

### P2: Pipeline 功能验证

- [ ] `SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh` 通过。
- [ ] Core cases 100% 通过：本月总收入 / 30天趋势 / 校区排名 / 朝阳校区过滤 / 退款金额。
- [ ] Safety cases 100% 通过：SQL 注入 / 多语句输入被拦截，`execute_sql=skipped`。
- [ ] `POST /analytics/query` 返回完整 `DataQaResult`，`visual.columns[].key` 与 `visual.rows[]` 对齐。

### P3: 前端健康

- [ ] 前端 `npm run build` 通过。
- [ ] 前端 mock 模式下，stat/line/bar/table/error 五类问数结果均可渲染。

Pre-flight 结果输出后，等待用户确认是否继续。发现问题时报告，不自行修复。

## Goal

删除旧 RAG 代码，重建干净的显式 mode 聊天路由，把 LLM NL2SQL 问数能力接入聊天体验，完成前后端真实联调：

1. 删除旧文档 RAG 全部代码（intent_classifier、document_search、course_search、question_search、ingest、processor、旧 stream/RAG 分支），聊天路由不再依赖意图分类器。
2. 后端 `/chat/query` 只接受 `mode=data_qa`，问数结果以 `data_qa_result` block 进入聊天历史。
3. 前端从 mock 数据切换到真实后端，图表和调试面板使用真实 `DataQaResult` 渲染。
4. 刷新页面后问数历史可完整恢复。

## Current P0 Integration Gap

当前后端尚不能支撑前后端真实联调，本轮必须修复：

- `ChatRequest` 只有 `query/session_id`，缺少 `mode`。
- `ChatResponse` / `ChatMessage` 缺少 `mode` 和 `blocks`。
- `/chat/query` 当前先走 `classify_intent`，依赖旧 RAG 服务（Milvus/MongoDB 文档搜索/课程搜索/题库搜索），这些服务已不属于教育问数主线。
- `GET /chat/history` 当前未投影 `mode/blocks`，问数结果刷新后无法恢复为图表。

本轮先删除旧 RAG 代码，再重建只支持显式 `mode=data_qa` 的干净聊天路由。旧 `knowledge`、course、question、document RAG 不再作为兼容路径保留。

## References

- 前端功能与联调清单：[frontend-functionality.md](frontend-functionality.md)
- 需求和设计：[requirements-and-plan.md](requirements-and-plan.md)
- 长期标准：[../../standard/insight.md](../../standard/insight.md)
- API 契约：[../../api-contract.md](../../api-contract.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)

## Tasks

### Stage 0：删除旧 RAG 代码

**Task 0: 清除旧文档 RAG 全部代码** `[subagent: single]`
- 删除范围：
  - `knowledge/api/routes/ingest.py` — 文档导入路由
  - `knowledge/api/routes/search.py` — 旧搜索路由
  - `knowledge/service/intent_classifier.py` — 三分类意图识别
  - `knowledge/service/document_search.py` — Milvus 文档搜索
  - `knowledge/service/course_search.py` — MongoDB 课程搜索
  - `knowledge/service/question_search.py` — MongoDB 题库搜索
  - `knowledge/service/chat_sync.py` — 旧意图路由分发（course/question/knowledge 分支）
  - `knowledge/service/chat_stream.py` — 旧流式 RAG 路由框架；如未来需要流式问数，重新基于 `data_qa/meta_qa` 设计，不保留旧 RAG 依赖
  - `knowledge/service/chat_formatter.py` — 旧格式化（如果仅服务于旧 RAG）
  - `knowledge/processor/` — 整个目录（chunker、docx_converter、milvus_store、image_uploader、document_store、catalog_parser、catalog_store、question_parser、question_store、embedder）
  - `knowledge/api/app.py` 中移除 `ingest_router` 和 `search_router` 的注册
  - 旧 RAG 相关测试文件（test_document_pipeline、test_document_search、test_chunker、test_docx_converter、test_milvus_store、test_ingest_routes、test_intent_classifier、test_course_search、test_question_search、test_hyde_search、test_rerank、test_embedder、test_catalog_parser、test_question_parser）
- 保留：
  - `knowledge/service/chat_history.py` — MongoDB 聊天历史（data_qa 和后续 meta_qa 都需要）
  - `knowledge/core/clients.py` 中的 `get_mongo_db` — 聊天历史依赖
- 验收：
  - `PYTHONPATH=. knowledge/.venv/bin/python -c "from knowledge.api.app import app; print('OK')"` 启动不报错。
  - `/chat/query` 不再依赖 `classify_intent`。
  - `/chat/query/stream` 不再注册旧 RAG/SSE 路由，或已被删除；应用启动时不得 import `chat_sync`、`intent_classifier`、`knowledge.processor`。
  - `SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh` 通过（问数管道不受影响）。

### Stage A：后端聊天扩展

**Task 1: ChatRequest / ChatResponse / ChatMessage 模型扩展** `[subagent: single]`
- 文件范围：`education_brain/knowledge/models/chat.py`、`education_brain/knowledge/api/routes/chat.py`
- 交付：
  - `ChatRequest` 增加必填 `mode: Literal["data_qa"]`（本轮只支持 data_qa，Iteration 05B 扩展 meta_qa）
  - `ChatResponse` 增加 `mode: str` 和 `blocks: list[dict] | None`
  - `ChatMessage` 增加 `mode: str` 和 `blocks: list[dict] | None`
- 约束：不传 mode 或传未知 mode 时返回 400，不做默认模式或静默降级。
- 验收：`POST /chat/query {"query": "本月总收入是多少？", "mode": "data_qa"}` 能正确解析。

**Task 2: data_qa 路由分发** `[subagent: single]`
- 文件范围：`education_brain/knowledge/api/routes/chat.py`
- 交付：`/chat/query` 重写为直接调用 `run_data_qa(query)`，将 `DataQaResult` 包装为 `ChatResponse` + `blocks`。不再经过旧 intent_classifier。
- 约束：
  - `result_type` 必须为 `"data_qa_result"`
  - `blocks` 至少包含一个 `{ "type": "data_qa_result", "data": <完整DataQaResult> }`
  - 问数失败也必须返回结构化 `DataQaResult.error`，不能只返回 HTTP 500
- 验收：`POST /chat/query {"query": "本月总收入是多少？", "mode": "data_qa"}` 返回 `result_type=data_qa_result` 和完整 blocks。

**Task 3: 聊天历史持久化** `[subagent: single]`
- 文件范围：`education_brain/knowledge/service/chat_history.py`
- 交付：
  - user message 持久化 `mode` 字段
  - assistant message 持久化 `mode`、`result_type`、`blocks`（含完整 `DataQaResult`）
  - `GET /chat/history` 返回的问数消息包含完整 `blocks`，不只是 `answer` 文本
- 验收：发送问数请求后，`GET /chat/history` 能恢复完整 `DataQaResult`，包括 `visual`、`explain.sql`、`trace`、`error`。

### Stage B：前端联调

**Task 4: mock→真实接口切换** `[subagent: single]`
- 文件范围：`education_brain_front/src/app/api/chat.ts`
- 交付：
  - `useMock=false` 时，`mode=data_qa` 走 `POST /chat/query` 真实接口
  - `DataQaResultView` 不改业务逻辑，只消费真实 `DataQaResult`
- 约束：前端不重新推断业务语义，不重新排序、聚合、计算；数据完全来自后端 `visual` 字段。
- 验收：关闭 mock 后，stat/line/bar/table/error 五类结果均来自真实后端响应。

**Task 5: 历史回放验证** `[subagent: single]`
- 交付：刷新页面后，`GET /chat/history` 返回的问数 assistant 消息仍渲染为图表和折叠面板，而不是退化成普通 markdown 文本。
- 验收：
  - 刷新后 `data_qa_result` block 仍展示为 `DataQaResultView`
  - SQL / 口径 / trace 可展开
  - 错误态可恢复

### Stage C：验证与打包

**Task 6: 端到端联调验证** `[subagent: single]`
- 交付：首批联调问题覆盖五类结果：

  | 问题 | 期望 |
  |---|---|
  | 本月总收入是多少？ | `stat` 指标卡 |
  | 最近30天收入趋势如何？ | `line` 折线图 |
  | 哪个校区收入最高？ | `bar` 柱状图 |
  | 查看本月新报名学员明细 | `table` 明细表 |
  | 本月总收入是多少？; DROP TABLE order; | 错误态 + `SQL_UNSAFE` |

- 验收：每类结果在浏览器中可见、可交互、可展开 SQL/trace。
- 真实依赖全流程 smoke 必须通过：
  ```bash
  cd education_brain
  SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
  ```
  该阶段必须走真实 MySQL、Qdrant、Elasticsearch、Embedding、LLM、API 和聊天历史，不能使用 fixture 或 mock。

**Task 7: Bundle 与回归检查** `[subagent: single]`
- 交付：
  - `npm run build` 无 `chunk larger than 500 kB` 警告
  - Recharts / DataQaResultView 保持按需加载
  - 旧 RAG 代码已删除，不影响问数管道
- 验收：
  ```bash
  cd education_brain_front && npm run build
  cd education_brain && SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
  ```

## Validation

后端验证：

```bash
cd education_brain
SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
```

前端验证：

```bash
cd education_brain_front
npm run build
```

浏览器验证（真实后端）：

五类问数结果在聊天页真实渲染：stat 指标卡、line 折线图、bar 柱状图、table 明细表、error 错误态。刷新后历史可恢复。

必须通过的断言：

- 旧 RAG 代码（intent_classifier、document_search、course_search、question_search、ingest、processor）已删除。
- `/chat/query` 不传 mode 或传未知 mode 返回 400。
- `/chat/query/stream` 旧知识问答入口已删除或取消注册，应用启动不再 import 旧 RAG 模块。
- `mode=data_qa` 返回 `result_type=data_qa_result` 和完整 `blocks`。
- `blocks[].data` 是完整 `DataQaResult` 对象，不是摘要字符串。
- `visual.columns[].key` 与 `visual.rows[]` 对齐。
- 聊天历史可恢复问数 assistant 消息，包含 mode + blocks + SQL + trace。
- 问数失败也保存为 assistant 消息，包含结构化 `error`。
- 前端图表数据完全来自后端 `DataQaResult.visual`，不在前端重新计算。
- `SMOKE_STAGE=llm` 中 trace 显示真实 LLM 调用（非规则 fallback）。
- `SMOKE_STAGE=e2e` 中 `/analytics/health` 为 `healthy`，真实聊天入口、LLM trace、SQL 执行、visual block、历史回放闭环通过。
- `npm run build` 无大 chunk 警告。

## Review

使用只读 reviewer subagent（当前可用角色优先用 `explorer`）review：

- 旧 RAG 代码是否已完全删除，无残留 import 或死代码。
- `/chat/query` 路由是否干净，只支持 `mode=data_qa`，不经过旧 intent_classifier。
- `/chat/query/stream` 是否不再保留旧 RAG 路径；如果未来需要流式能力，只能作为新的 `data_qa/meta_qa` 设计进入后续迭代。
- 聊天历史中的 `data_qa_result` 是否保存完整结构（不是只保存渲染文本）。
- 前端是否只根据 `block.type` 和 `visual.type` 渲染，不硬编码业务逻辑。
- 图表数据是否完全来自后端 `DataQaResult.visual`，前端不重新排序、聚合或推断。
- 联调时后端返回的 `DataQaResult` 是否经过真实 LLM 生成，trace 中是否可见 LLM 调用记录。
- code splitting 是否仍隔离 Recharts / DataQaResultView。

## Guardrails

本轮不做：

- 流式问数。
- 续费/复购等未定义口径的指标。
- 数据导出。
- 图表钻取、双轴图、组合图。
- meta_qa 模式（属于 Iteration 05）。

遇到以下情况必须 stop/ask：

- 后端返回的 `DataQaResult` 与 `api-contract.md` 定义不一致，导致前端必须写兼容分支。
- 图表库选型影响包体积或与现有前端框架冲突。
- 联调时发现 `visual.columns[].key` 与 `visual.rows[]` 不对齐。
- 联调时发现 LLM 节点的 trace 缺失或 token usage 未记录（可能意味着 Iter 03 退化为规则）。
