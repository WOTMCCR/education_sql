# Iteration 05A Goal: 旧 RAG 清理收束与数据生成入口标准化

## Pre-flight

本轮是 Iteration 04 删除旧 RAG 后的收束和数据准备标准化，不开发 `meta_qa` 新功能。任一项不通过则先记录现状，不尝试恢复旧文档 RAG。

- [ ] Iteration 04 的 `SMOKE_STAGE=e2e` 已通过，证明 `data_qa` 前后端联调闭环可用。
- [ ] `GET /chat/history` 已能返回 `mode`、`result_type` 和 `blocks`。
- [ ] 旧 RAG 已删除：`knowledge/processor/`、`knowledge/service/intent_classifier.py`、`knowledge/api/routes/ingest.py`、`knowledge/api/routes/search.py`、旧 `/chat/query/stream` 路由均不存在或不再注册。
- [ ] 当前 `data_ge/edu-data` 可执行：
  ```bash
  cd data_ge/edu-data
  uv run init_db.py
  uv run -m generate.main --profile smoke
  ```
- [ ] 当前 meta 构建可执行：
  ```bash
  cd education_brain
  PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
    --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
  ```

## Goal

把当前问数系统的数据准备入口固定为“业务数据生成 + meta/metric 构建”，并确认旧“文档导入 RAG”已经从代码和验收中清除：

1. 确认旧文档 RAG 主链路已删除，doc chunk / MinIO / Milvus / Mongo document store 不再是教育问数路径。
2. 标准化 `init_db -> generate -> build_meta` 数据准备流程。
3. 明确 MongoDB 只用于聊天历史和可选 session summary。
4. 新增或确认 `SMOKE_STAGE=bootstrap`，但不纳入本地默认 `SMOKE_STAGE=all`。

## Tasks

**Task 1: 旧 RAG 删除收束检查** `[subagent: single]`

- 文件范围：`education_brain/knowledge/api/app.py`、`education_brain/knowledge/api/routes/chat.py`、`education_brain/knowledge/service/`、`education_brain/knowledge/processor/`、旧 RAG 相关 README、教育问数文档。
- 交付：
  - 确认旧路径已删除：doc parse/chunk/image upload/MinIO/Milvus/Mongo document store、旧 document/course/question search、旧 intent_classifier、旧 stream RAG。
  - 文档明确这些能力不是教育问数系统交付范围，不保留旧 API。
  - 开发入口不再要求启动 Milvus/MinIO 才能完成 `data_qa` 或后续 `meta_qa`；MongoDB 仅用于聊天历史。
- 验收：问数主线文档不再把旧文档导入作为前置条件，应用启动不 import `knowledge.processor`、`intent_classifier`、`chat_sync`。

**Task 2: 标准化数据生成命令** `[subagent: single]`

- 文件范围：`data_ge/edu-data/README.md`、`docs/env-setup.md`、教育问数 README。
- 交付：
  - 固定 smoke 数据准备命令：
    ```bash
    cd data_ge/edu-data
    uv run init_db.py
    uv run -m generate.main --profile smoke
    ```
  - 说明 `smoke` profile 的数据规模、可重复执行语义、失败排查方式。
- 验收：生成后的 MySQL 业务表有真实行数，可支撑收入、趋势、排名、明细问题。

**Task 3: 标准化 meta/metric 构建命令** `[subagent: single]`

- 文件范围：`data_ge/edu-data/meta/education_meta.yaml`、`education_brain/knowledge/analytics/build_meta.py`、smoke 文档。
- 交付：
  - 固定 meta 构建命令：
    ```bash
    cd education_brain
    PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
      --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
    ```
  - 明确构建输出：
    - MySQL `meta_table_info` / `meta_column_info` / `meta_metric_info` / `meta_column_metric` / `meta_join_info` / `meta_dimension_info`
    - Qdrant `edu_column_info` / `edu_metric_info`
    - Elasticsearch 维度取值索引
- 验收：`/analytics/health` 为 `healthy`，关键 metric、column、dimension value 可召回。

**Task 4: bootstrap smoke** `[subagent: single]`

- 文件范围：`education_brain/knowledge/tests/smoke_test_data_qa.sh`、`docs/education-data-qa/testing/smoke-test-metrics.md`。
- 交付：
  - 新增或确认 `SMOKE_STAGE=bootstrap`。
  - `bootstrap` 验证 `init_db -> generate -> build_meta -> SMOKE_STAGE=meta`。
  - `bootstrap` 只用于 CI/CD、发布前或手动完整准备验证，不纳入本地默认 `SMOKE_STAGE=all`。
- 验收：
  ```bash
  cd education_brain
  SMOKE_STAGE=bootstrap ./knowledge/tests/smoke_test_data_qa.sh
  ```

## Validation

```bash
cd data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
  --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

发布前或 CI/CD 手动执行：

```bash
cd education_brain
SMOKE_STAGE=bootstrap ./knowledge/tests/smoke_test_data_qa.sh
```

## Guardrails

- 本轮不实现 `meta_qa`。
- 本轮不迁移 Milvus 到 Qdrant。
- 本轮不恢复旧课程文档上传问答能力。
- 如果发现 Iteration 04 删除旧 RAG 后仍有残留 import 或路由注册，本轮必须修正文档和 smoke 口径，不能把残留标记为可接受状态通过。
