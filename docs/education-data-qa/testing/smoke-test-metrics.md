# 教育问数 Smoke Test 指标

本文件定义教育问数系统每个迭代完成后的真实请求级验收。目标不是检查文件、函数或参数是否存在，而是用 `curl` 发送请求，验证服务能按当前迭代目标真实跑通。

## 总原则

- 每个迭代都必须提供可重复执行的 smoke test。
- smoke test 以 HTTP 请求为主，入口统一放在 `education_brain/knowledge/tests/smoke_test_data_qa.sh`。
- 测试可以按阶段执行：
  - `SMOKE_STAGE=meta`：只验证元数据构建和召回。
  - `SMOKE_STAGE=pipeline`：验证自然语言到 SQL 到结果结构。
  - `SMOKE_STAGE=chat`：验证聊天入口、历史和 block 保存。
  - `SMOKE_STAGE=visual`：验证图表协议和渲染所需数据。
  - `SMOKE_STAGE=all`：按顺序执行全部可用阶段。
- 失败要能定位到阶段：MySQL、Qdrant、Elasticsearch、Embedding、LLM、SQL 校验、SQL 执行、聊天持久化、图表协议。
- 允许对重依赖做显式跳过，但跳过必须有原因，不能把依赖失败伪装成通过。

## 服务级契约

为了让迭代 01 也能用 `curl` 验收，后端需要提供最小诊断接口。推荐接口如下：

| 迭代 | 接口 | 用途 |
|---|---|---|
| 01 | `GET /analytics/health` | 检查 MySQL meta、Qdrant、Elasticsearch、Embedding 依赖和 meta 行数 |
| 01 | `GET /analytics/meta/metrics?q=收入&limit=5` | 验证指标召回 |
| 01 | `GET /analytics/meta/columns?q=实付金额&limit=5` | 验证字段召回 |
| 01 | `GET /analytics/meta/values?q=<真实校区名>&limit=5` | 验证维度取值召回 |
| 02 | `POST /analytics/query` | 直接验证 NL2SQL pipeline，不经过聊天 UI |
| 03 | `POST /chat/query` with `mode=data_qa` | 验证问数接入同一聊天入口 |
| 03 | `GET /chat/history?session_id=...` | 验证问数结果进入同一聊天历史 |
| 04 | `POST /analytics/query` / `POST /chat/query` | 验证 `visual`、SQL、trace、错误态协议完整 |

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
curl -sfG "http://localhost:8000/analytics/meta/values" --data-urlencode "q=北京校区" --data-urlencode "limit=5"
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

## Iteration 03：聊天接入

必跑指标：

- 普通问答不受影响：`POST /chat/query` 不带 `mode` 或 `mode=knowledge` 时仍返回现有 RAG/搜索结果。
- 数据问数：`POST /chat/query` 带 `mode=data_qa` 时返回 `result_type=data_qa_result`。
- assistant 回复包含 `blocks`，其中至少有一个 `{ "type": "data_qa_result" }`。
- 同一个 `session_id` 下，用户消息和问数 assistant 消息都能从 `/chat/history` 取回。
- 历史中的问数 assistant 消息必须保留 `mode=data_qa`、`blocks`、`answer` 和可展开 SQL 所需字段。

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
- `visual.columns` 中每一列都能在 `visual.rows` 中找到对应 key。
- SQL、指标口径、trace 默认可折叠展示所需字段齐全。
- 空结果、SQL 校验失败、召回失败都返回 `data_qa_result.error` 或 `warnings`，聊天历史仍保存失败回复。

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
SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=all ./knowledge/tests/smoke_test_data_qa.sh
```

环境变量：

- `BASE`：服务地址，默认 `http://localhost:8000`。
- `SMOKE_STAGE`：执行阶段，默认 `all`。
- `QA_TIMEOUT`：问数请求超时秒数，默认 `180`。
- `SMOKE_VALUE_QUERY`：用于 ES 维度取值召回的真实校区或课程名，默认 `北京校区`。
