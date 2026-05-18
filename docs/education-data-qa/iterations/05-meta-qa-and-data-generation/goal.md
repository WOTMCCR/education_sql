# Iteration 05 Goal: 数据生成标准化与 Meta QA

> Status: superseded by `../05a-rag-freeze-and-bootstrap/` and `../05b-meta-qa/`.
> 本文件保留为整包设计参考；正式执行以 05A（旧 RAG 清理收束与数据准备标准化）→ 05B（Meta QA）为准。

## Pre-flight

本轮 pre-flight 的核心目标：确认 Iteration 04 已经把 `data_qa` 接入聊天壳，旧 RAG 代码已删除，真实依赖链路可用。任一项不通过则本轮不得开始。

- [ ] `SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh` 通过，证明真实 MySQL、Qdrant、Elasticsearch、Embedding、LLM、API 和聊天历史闭环可用。
- [ ] `GET /chat/history` 已能返回 `mode` 和 `blocks` 字段；这是 Iteration 04 的交付物，也是 `meta_qa` 历史回放的前置条件。
- [ ] 旧 RAG 代码已在 Iteration 04 删除：`knowledge/processor/` 不存在，`knowledge/service/intent_classifier.py` 不存在，`knowledge/api/routes/ingest.py` 不存在。
- [ ] 当前 `data_ge/edu-data` 能执行数据生成：`uv run -m generate.main --profile smoke`。
- [ ] 当前 meta 构建能执行：`cd education_brain && PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate`。
- [ ] `/analytics/health` 返回 `healthy`，且 counts 中 tables、columns、metrics、joins、dimensions 都大于 0。

Pre-flight 结果输出后，等待用户确认是否继续。

## Goal

标准化数据准备流程，新增 Meta QA 问答模式：

1. 固定数据准备入口：`generate` 生成业务数据 → `build_meta` 构建 meta/metric/Qdrant/ES 索引。
2. 新增 `mode=meta_qa`，回答指标口径、表字段、维度、join path、可问范围等问题，不生成 SQL、不执行 SQL。
3. 前端新增”数据说明”模式，与”数据问数”并列为两个主入口。

## References

- 长期标准：[../../standard/insight.md](../../standard/insight.md)
- API 契约：[../../api-contract.md](../../api-contract.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)
- 数据生成项目：`data_ge/edu-data/`
- Meta 配置：`data_ge/edu-data/meta/education_meta.yaml`
- Meta 构建脚本：`education_brain/knowledge/analytics/build_meta.py`
- 现有 meta 召回：`education_brain/knowledge/analytics/search.py`

## Tasks

### Stage A：数据生成与 Meta 构建入口

**Task 1: 数据生成流程标准化** `[subagent: single]`
- 文件范围：`data_ge/edu-data/`、`docs/env-setup.md`、教育问数文档。
- 交付：
  - 固定本轮数据准备命令：
    ```bash
    cd data_ge/edu-data
    uv run init_db.py
    uv run -m generate.main --profile smoke
    ```
  - 明确 `smoke` / 后续更大 profile 的用途、预期数据规模、可重复执行语义。
  - 失败时输出具体缺失依赖或 SQL 初始化问题。
- 验收：生成后的 MySQL 业务表有真实行数，能支撑收入、趋势、排名、明细和口径问题。

**Task 2: meta/metric 构建流程标准化** `[subagent: single]`
- 文件范围：`data_ge/edu-data/meta/education_meta.yaml`、`education_brain/knowledge/analytics/build_meta.py`、`docs/education-data-qa/testing/smoke-test-metrics.md`。
- 交付：
  - 固定 meta 构建命令：
    ```bash
    cd education_brain
    PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
      --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
    ```
  - 构建输出覆盖：
    - MySQL `meta_table_info` / `meta_column_info` / `meta_metric_info` / `meta_column_metric` / `meta_join_info` / `meta_dimension_info`
    - Qdrant `edu_column_info` / `edu_metric_info`
    - Elasticsearch 维度取值索引
  - 增加或确认 smoke：`SMOKE_STAGE=meta` 可验证 counts 和召回。
- 验收：`/analytics/health` 为 `healthy`，且 `paid_revenue`、关键字段、真实校区/课程取值可召回。

### Stage B：Meta QA 后端

**Task 3: 新增 meta_qa 模式与响应契约** `[subagent: single]`
- 文件范围：`docs/education-data-qa/api-contract.md`、`education_brain/knowledge/models/chat.py`、`education_brain/knowledge/api/routes/chat.py`。
- 交付：
  - `ChatRequest.mode` 扩展为 `Literal["data_qa", "meta_qa"]`。
  - 未知 mode 返回 400，不得静默降级。
  - `ChatResponse.result_type = "meta_answer"`。
  - blocks 支持：
    ```ts
    type MetaCitation = {
      kind: 'metric' | 'column' | 'table' | 'dimension' | 'join' | 'value'
      id: string
      name: string
      source?: string
    }

    type ChatBlock =
      | { type: 'markdown'; content: string }
      | { type: 'data_qa_result'; data: DataQaResult }
      | { type: 'meta_citations'; data: MetaCitation[] }
    ```
  - `meta_qa` 不生成 SQL、不执行 SQL。
- 验收：`POST /chat/query {"query":"实付收入怎么算？","mode":"meta_qa"}` 返回 `result_type=meta_answer` 和 `meta_citations`。

**Task 4: Meta QA 检索与回答管道** `[subagent: single]`
- 文件范围：`education_brain/knowledge/analytics/search.py`、新建 `knowledge/analytics/meta_qa/` 或等价服务模块。
- 交付：
  - 复用 Qdrant metric/column 召回、MySQL meta 表上下文、ES 维度取值搜索。
  - LLM 只负责组织解释和引用，不允许输出 SQL。
  - trace 中必须记录 `meta_qa` 的 LLM 调用节点、prompt/raw/usage 或等价调用证据，避免退化成模板拼接。
  - 支持首批问题：
    - “实付收入怎么算？”
    - “收入相关指标有哪些？”
    - “校区收入排名涉及哪些表？”
    - “paid_revenue 支持哪些维度？”
    - “为什么复购率暂时不能问？”
  - 失败时返回结构化 `META_RECALL_EMPTY` 或 `META_QA_UNAVAILABLE`，不要退化为空回答。
- 验收：首批问题均能返回 markdown 解释和至少一个 meta citation；未定义口径能解释缺失原因。

### Stage C：前端与历史

**Task 5: 前端模式和渲染** `[subagent: single]`
- 文件范围：`education_brain_front/src/app/api/chat.ts`、`education_brain_front/src/app/pages/chat-page.tsx`、types。
- 交付：
  - 产品主入口只展示两个模式：`data_qa` = 数据问数，`meta_qa` = 数据说明。
  - `meta_citations` 渲染为指标/字段/表/维度引用列表。
  - `DataQaResultView` 不被 `meta_qa` 复用，避免语义混淆。
- 验收：同一会话中可先问”本月收入是多少？”，再切到数据说明问”这个指标怎么算？”，历史刷新后两类消息都能恢复。

**Task 6: 聊天历史持久化** `[subagent: single]`
- 文件范围：`education_brain/knowledge/service/chat_history.py`。
- 交付：
  - 持久化 `mode=meta_qa`、`result_type=meta_answer`、`blocks`、`meta_citations`。
  - MongoDB 只承载聊天历史。
- 验收：`GET /chat/history` 能恢复 `meta_qa` block，不需要从 markdown 反推引用。

### Stage D：验证与文档

**Task 7: Smoke 与回归** `[subagent: single]`
- 交付：
  - 新增 `SMOKE_STAGE=bootstrap`：验证 `init_db -> generate -> build_meta -> SMOKE_STAGE=meta` 的数据准备链路，或提供等价脚本。
  - 新增 `SMOKE_STAGE=meta_qa`：验证 meta 问答接口、meta citations、历史回放。
  - `SMOKE_STAGE=meta_qa` 必须验证 trace 中存在 LLM 调用证据；禁用或清空 LLM key 时不能返回正常 `meta_answer`。
  - 保留 `SMOKE_STAGE=e2e` 验证数据问数真实全链路。
- 验收：
  ```bash
  cd education_brain
  SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
  SMOKE_STAGE=meta_qa ./knowledge/tests/smoke_test_data_qa.sh
  SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
  ```

## Validation

数据准备验证：

```bash
cd data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke
```

Meta 构建验证：

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
  --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

Meta QA 验证：

```bash
cd education_brain
SMOKE_STAGE=meta_qa ./knowledge/tests/smoke_test_data_qa.sh
```

前端验证：

```bash
cd education_brain_front
npm run build
```

必须通过的断言：

- 数据准备入口以 `generate` 和 `build_meta` 为中心。
- `meta_qa` 不生成 SQL、不执行 SQL。
- `meta_qa` 回答只能引用已召回的 meta 对象，不能创造不存在的 metric/table/column。
- `meta_qa` 和 `data_qa` 可在同一会话历史中混合回放。

## Review

使用只读 reviewer subagent review：

- `meta_qa` 是否只解释 meta，不偷偷走 SQL 生成。
- 数据生成和 meta 构建命令是否足够清晰、可重复。
- `meta_citations` 是否能追溯到真实 meta 表或 Qdrant payload。

## Guardrails

本轮不做：

- 自动意图识别；继续使用显式模式。
- 用 `meta_qa` 回答真实统计值；统计值必须走 `data_qa`。

遇到以下情况必须 stop/ask：

- `education_meta.yaml` 覆盖不足，导致 `meta_qa` 需要猜指标或字段。
- `generate` 数据与 meta 指标口径不一致。
- MongoDB 历史存储无法保存嵌套 blocks。
