# 教育问数 Smoke Test 指标

本文件定义教育问数系统每个迭代完成后的真实请求级验收。目标不是检查文件、函数或参数是否存在，而是用 `curl` 发送请求，验证服务能按当前迭代目标真实跑通。

## 总原则

- 每个迭代都必须提供可重复执行的 smoke test。
- smoke test 以 HTTP 请求为主，入口统一放在 `education_brain/knowledge/tests/smoke_test_data_qa.sh`。
- 测试可以按阶段执行：
  - `SMOKE_STAGE=meta`：只验证元数据构建和召回。
  - `SMOKE_STAGE=pipeline`：验证自然语言到 SQL 到结果结构。
  - `SMOKE_STAGE=llm`：验证完整 LLM NL2SQL 的泛化能力和安全边界。
  - `SMOKE_STAGE=chat`：验证聊天入口、历史和 block 保存。
  - `SMOKE_STAGE=visual`：验证图表协议和渲染所需数据。
  - `SMOKE_STAGE=e2e`：验证真实 MySQL、Qdrant、Elasticsearch、Embedding、LLM、API、聊天历史全流程。
  - `SMOKE_STAGE=bootstrap`：验证数据生成、MySQL 初始化、meta/metric 构建和 meta smoke 的完整准备链路；仅用于 CI/CD、发布前或手动完整准备验证。
  - `SMOKE_STAGE=meta_qa`：验证数据说明/口径问答、meta citations 和历史回放。
  - `SMOKE_STAGE=all`：按顺序执行已实现且适合本地回归的阶段；它是跨迭代集成检查，不等同于单个迭代的验收入口，也不包含 `bootstrap`。
- 失败要能定位到阶段：MySQL、Qdrant、Elasticsearch、Embedding、LLM、SQL 校验、SQL 执行、聊天持久化、图表协议。
- 允许对重依赖做显式跳过，但跳过必须有原因，不能把依赖失败伪装成通过。
- 聊天联调类 smoke 必须快速失败，不能因为误走旧 RAG 路径而卡住数分钟。
- 单元测试可以使用 fixture 隔离管道行为，但 `SMOKE_STAGE=e2e` 和 `SMOKE_STAGE=all` 必须走真实服务依赖，不能 mock MySQL/Qdrant/ES/Embedding/LLM。

## 服务级契约

为了让迭代 01 也能用 `curl` 验收，后端需要提供最小诊断接口。推荐接口如下：

| 迭代 | 接口 | 用途 |
|---|---|---|
| 01 | `GET /analytics/health` | 检查 MySQL meta、Qdrant、Elasticsearch、Embedding 依赖和 meta 行数 |
| 01 | `GET /analytics/meta/metrics?q=收入&limit=5` | 验证指标召回 |
| 01 | `GET /analytics/meta/columns?q=实付金额&limit=5` | 验证字段召回 |
| 01 | `GET /analytics/meta/values?q=<真实校区名>&limit=5` | 验证维度取值召回 |
| 02 | `POST /analytics/query` | 直接验证 NL2SQL pipeline，不经过聊天 UI |
| 03 | `POST /analytics/query` | 验证 LLM 主导的意图结构化、候选过滤、SQL 生成和纠错 |
| 04 | `POST /chat/query` with `mode=data_qa` | 验证问数接入同一聊天入口 |
| 04 | `GET /chat/history?session_id=...` | 验证问数结果进入同一聊天历史 |
| 04 | `POST /analytics/query` / `POST /chat/query` | 验证 `visual`、SQL、trace、错误态协议完整 |
| 04 | `SMOKE_STAGE=e2e` | 验证从真实依赖到聊天历史回放的完整闭环 |
| 05A | `generate.main` + `build_meta.py` | 验证数据准备从文档导入切换为数据生成和 meta/metric 构建 |
| 05B | `POST /chat/query` with `mode=meta_qa` | 验证指标口径、字段、表关系和可问范围说明 |

如果最终接口命名调整，必须同步更新本文件和 `smoke_test_data_qa.sh`。

## Iteration 01：元数据系统

必跑指标：

- `/analytics/health` 返回 `status` 为 `healthy` 或 `degraded`，并包含 `mysql_meta`、`qdrant`、`elasticsearch`、`embedding`、`counts`。
- `counts.tables > 0`、`counts.columns > 0`、`counts.metrics >= 10`、`counts.joins > 0`、`counts.dimensions > 0`。
- 搜索 `收入` 时，`/analytics/meta/metrics` 至少召回 `paid_revenue`。
- 搜索 `实付金额` 时，`/analytics/meta/columns` 至少召回 `order.paid_amount`。
- 搜索一个真实校区或课程名时，`/analytics/meta/values` 返回命中的 `field`、`value` 和 `score`。
- 表和字段物理信息要求全量覆盖 `edu-data` 当前业务表；metric、dimension、column_metric 不要求穷举所有可能组合，只覆盖当前问数范围。

示例请求：

```bash
curl -sf "http://localhost:8000/analytics/health"
curl -sfG "http://localhost:8000/analytics/meta/metrics" --data-urlencode "q=收入" --data-urlencode "limit=5"
curl -sfG "http://localhost:8000/analytics/meta/columns" --data-urlencode "q=实付金额" --data-urlencode "limit=5"
curl -sfG "http://localhost:8000/analytics/meta/values" --data-urlencode "q=徐汇校区" --data-urlencode "limit=5"
```

## Iteration 02：问数 Pipeline

必跑指标：

- `POST /analytics/query` 问“本月总收入是多少？”，返回 `mode=data_qa`、`intent.analysisType=single_metric`、`metrics` 包含 `paid_revenue`、`visual.type=stat`、`explain.sql` 非空、`trace.rowCount >= 1`。
- 问“最近30天收入趋势如何？”，返回 `analysisType=trend`、`visual.type=line`，行数大于 1，日期列存在。
- 问“哪个校区收入最高？”，返回 `analysisType=ranking`、`visual.type=bar`，结果有排序字段和 `limit`。
- 所有成功请求都要返回 `explain.metrics`、`explain.tables`、`explain.joins`、`trace.stages`。
- 发送包含 SQL 注入或多语句的自然语言请求时，不能执行危险 SQL，必须返回结构化错误或安全降级。

示例请求：

```bash
curl -sf -X POST "http://localhost:8000/analytics/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"本月总收入是多少？","session_id":"smoke-pipeline"}'
```

## Iteration 03：完整 LLM NL2SQL

验收边界：

- Iteration 03 只验收显式问数入口 `/analytics/query` 和 `SMOKE_STAGE=llm`。
- 不要求 MongoDB、`/chat/query`、聊天历史、前端真实联调通过；这些属于 Iteration 04。
- 不依赖普通聊天意图识别自动进入 NL2SQL。后续聊天接入必须使用显式 `mode=data_qa` 或等价强 trigger。

必跑指标：

- `SMOKE_STAGE=llm` 必须区分 core、extended、safety 三类 case，并输出每条 case 的问题、SQL、visual.type、error 和失败原因。
- Core cases 100% 通过：
  - 本月总收入是多少？
  - 最近30天收入趋势如何？
  - 哪个校区收入最高？
  - 朝阳校区本月收入是多少？
  - 最近30天各校区收入趋势如何？
  - 本月报名人数最多的课程系列是什么？
  - 本月退款金额是多少？如果缺少 `refund_amount` metric，则必须返回明确结构化口径缺失错误。
- Extended cases 第一版通过率 >= 70%，失败必须是可解释的结构化错误，不能是空响应或未捕获异常。
- Safety cases 100% 通过：SQL 注入、多语句、注释绕过、危险函数、文件写入类请求均不能执行，`trace.execute_sql` 必须为 `skipped`。
- LLM 生成 SQL 只能引用候选 context 中的表、字段、指标和 join path。
- LLM 输出必须经过结构化解析；解析失败返回 `LLM_OUTPUT_INVALID` 或等价结构化错误。
- `EXPLAIN` 失败时最多触发一次 LLM 纠错；纠错失败返回 `SQL_VALIDATE_FAILED`，不得执行。
- LLM 不可用时返回 `LLM_UNAVAILABLE` 或明确 fallback 标记，不能伪装成 LLM 成功。

## Iteration 04：聊天接入与旧 RAG 删除

必跑指标：

- 旧 RAG 已删除：`/ingest`、`/search`、`/chat/query/stream` 旧入口不再注册；应用启动不 import `intent_classifier`、`chat_sync`、`knowledge.processor`。
- `POST /chat/query` 不带 `mode`、`mode=knowledge` 或未知 `mode` 时返回 400。
- 数据问数：`POST /chat/query` 带 `mode=data_qa` 时返回 `result_type=data_qa_result`。
- `mode=data_qa` 请求必须在 `CHAT_TIMEOUT` 内返回；超时通常表示后端没有识别显式 mode，或仍残留旧 RAG 依赖。
- 返回体必须明确包含 `mode=data_qa`、`intent=data_qa`、`result_type=data_qa_result`，避免前端收到非问数响应后误渲染。
- assistant 回复包含 `blocks`，其中至少有一个 `{ "type": "data_qa_result" }`。
- `blocks[].data` 必须是完整 `DataQaResult` 对象，不允许是字符串、摘要文本或缺字段对象。
- 同一个 `session_id` 下，用户消息和问数 assistant 消息都能从 `/chat/history` 取回。
- 历史中的问数 assistant 消息必须保留 `mode=data_qa`、`blocks`、`answer`、`visual`、`explain.sql`、`explain.metrics`、`trace.stages`、`warnings` 和 `error`。
- `SMOKE_STAGE=e2e` 必须通过：`/analytics/health` 为 `healthy`，真实聊天入口返回完整 `DataQaResult` block，trace 中可见真实 LLM 节点，SQL 执行成功，历史回放保留完整 block。

示例请求：

```bash
curl -sf -X POST "http://localhost:8000/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"本月总收入是多少？","mode":"data_qa","session_id":"smoke-chat"}'

curl -sf "http://localhost:8000/chat/history?session_id=smoke-chat&limit=10"
```

## Iteration 04：真实图表与体验打磨

必跑指标：

- `single_metric` 返回 `visual.type=stat`，并提供货币或百分比格式字段。
- `trend` 返回 `visual.type=line`，包含 `x` 和至少一个 `y` 序列。
- `ranking` 返回 `visual.type=bar`，包含排序后的维度和值。
- `bar` 结果应由后端按返回顺序体现排名，前端不再重新排序。
- `visual.columns` 中每一列都能在 `visual.rows` 中找到对应 key。
- SQL、指标口径、trace 默认可折叠展示所需字段齐全。
- 空结果、SQL 校验失败、召回失败都返回 `data_qa_result.error` 或 `warnings`，聊天历史仍保存失败回复。
- SQL 注入或多语句输入仍必须返回可渲染 `DataQaResult`，包含结构化 `error`、`warnings` 和 `trace.execute_sql=skipped`。

## Iteration 05A：旧 RAG 清理收束与 Bootstrap

必跑指标：

- 确认旧 RAG 删除收束：Milvus、MinIO、doc chunking、旧 document/course/question search、旧 intent classifier 均不再是代码启动路径或 smoke 前置依赖。
- `SMOKE_STAGE=bootstrap` 应验证：
  - `data_ge/edu-data/init_db.py` 可初始化业务表和 meta 表 DDL。
  - `uv run -m generate.main --profile smoke` 可生成业务数据。
  - `build_meta.py --recreate` 可写入 MySQL meta 表、Qdrant metric/column collection、ES 维度取值索引。
  - 随后的 `SMOKE_STAGE=meta` 通过。
- `SMOKE_STAGE=bootstrap` 不纳入本地默认 `SMOKE_STAGE=all`，避免每次回归都重建数据和索引；它只在 CI/CD、发布前或手动完整准备验证中执行。
- MongoDB 只作为聊天历史/会话摘要存储；旧文档知识库、Milvus、MinIO、doc chunking 不再是教育问数依赖。

## Iteration 05B：Meta QA

必跑指标：

- `SMOKE_STAGE=meta_qa` 应验证：
  - `POST /chat/query` 带 `mode=meta_qa` 返回 `result_type=meta_answer`。
  - assistant 回复包含 markdown block 和 `meta_citations` block。
  - citations 只能引用真实存在的 metric/table/column/dimension/join/value。
  - citations 的 `source` 必须是 `meta_metric_info`、`meta_column_info`、`meta_table_info`、`meta_dimension_info`、`meta_join_info` 之一。
  - `meta_qa` 不返回 SQL，不执行 SQL，不返回 `DataQaResult.visual`。
  - `GET /chat/history` 能恢复完整 `meta_qa` blocks。
  - trace 中存在 Meta QA LLM 调用证据，例如 `stage=meta_qa_llm`、prompt 名称/hash、输出摘要、usage 或等价字段。
  - 面向前端的 trace 不暴露完整 system prompt 或完整 raw response，只保留 prompt 名称/hash、输入摘要、输出摘要和 usage。
  - 清空或禁用 LLM key 后不能返回正常 `meta_answer`，避免退化成规则模板伪装 LLM。

## 本地执行

推荐命令：

```bash
cd education_brain
uv run uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
```

另一个终端执行：

```bash
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=meta_qa ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=all ./knowledge/tests/smoke_test_data_qa.sh
```

完整数据准备验证单独执行：

```bash
SMOKE_STAGE=bootstrap ./knowledge/tests/smoke_test_data_qa.sh
```

`SMOKE_STAGE=bootstrap` 会重建本地 MySQL 业务数据、MySQL meta 表、Qdrant collection 和 ES 维度取值索引；执行前应确认可以覆盖本地开发数据。

环境变量：

- `BASE`：服务地址，默认 `http://localhost:8000`。
- `SMOKE_STAGE`：执行阶段，默认 `all`。
- `QA_TIMEOUT`：问数请求超时秒数，默认 `180`。
- `CHAT_TIMEOUT`：聊天接入 smoke 超时秒数，默认 `20`。用于快速暴露 `mode=data_qa` 未接入或误路由。
- `E2E_TIMEOUT`：真实全流程聊天请求超时秒数，默认沿用 `QA_TIMEOUT`。用于真实 LLM + 真实依赖的完整闭环验证。
- `SMOKE_VALUE_QUERY`：用于 ES 维度取值召回的真实校区或课程名，默认 `徐汇校区`。

说明：`SMOKE_STAGE=llm` 是 Iteration 03 的显式验收入口。`SMOKE_STAGE=all` 会包含聊天、历史、可视化和后续阶段，只能作为对应阶段完成后的集成回归；不能用它要求 Iteration 03 通过 MongoDB、`/chat/query`、历史回放或前端真实联调。
