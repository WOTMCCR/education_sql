# Iteration 01 Development Plan

**Goal:** 建立教育问数的本地运行环境和元数据构建闭环，最终通过 `SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh`。

**Acceptance criteria:**

- 项目内存在可启动的 MySQL、Elasticsearch + IK、Kibana、Qdrant、Embedding Docker 环境。
- `edu-data` 的业务库可初始化并生成 smoke 数据。
- 6 张 `meta_*` 表可创建并写入元数据。
- Qdrant 可召回 `paid_revenue` 和 `order.paid_amount`。
- Elasticsearch 可召回真实校区或课程维度取值。
- `/analytics/health` 和 `/analytics/meta/*` 能通过 HTTP smoke 验证。

**Primary files/systems:**

- `infra/education-data-qa/docker-compose.yaml`
- `infra/education-data-qa/elasticsearch/Dockerfile`
- `data_ge/edu-data/meta/education_meta.yaml`
- `data_ge/edu-data/sql/edu.sql`
- `education_brain/knowledge/pyproject.toml`
- `education_brain/knowledge/core/config.py`
- `education_brain/knowledge/core/clients.py`
- `education_brain/knowledge/analytics/`
- `education_brain/knowledge/api/routes/analytics.py`
- `education_brain/knowledge/tests/smoke_test_data_qa.sh`

**Validation:**

```bash
cd infra/education-data-qa
docker compose up -d

cd ../../data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

## Task 1: Project-local Docker Environment

**Addresses:** 环境依赖可启动、服务端口稳定、后续 smoke 可重复执行。

**Files:** `infra/education-data-qa/*`

**Work:**

- 从 `/home/ccr/local-docker/nl2sql-env` 迁移 compose 结构，但改成教育问数专用命名。
- 保留 MySQL 8.0、Elasticsearch 8.19.10 + IK、Kibana、Qdrant v1.16、TEI CPU embedding。
- BGE 模型通过 `.env` 指向本机目录，不提交模型权重。
- `volumes/` 运行数据不进入 Git。

**Validation:** `docker compose ps` 显示所有服务 running；如果 compose 配置了 healthcheck，则要求 healthy；同时用 `curl` / `mysqladmin ping` 验证 ES、Qdrant、Embedding、MySQL 探针可访问。

**Stop/ask if:** 本机 3306、9200、6333、8081 端口已有不可替换服务。

## Task 2: Backend Dependency Configuration

**Addresses:** 后端能连接 MySQL、Qdrant、ES、Embedding。

**Files:** `education_brain/knowledge/pyproject.toml`, `education_brain/knowledge/core/config.py`, `education_brain/knowledge/core/clients.py`, `education_brain/knowledge/.env.example`

**Work:**

- 添加 `ANALYTICS_MYSQL_*`、`ANALYTICS_QDRANT_*`、`ANALYTICS_ES_*`、`ANALYTICS_EMBEDDING_*` 配置。
- 新增 client factory 和 probe 方法，不污染现有 MongoDB/Milvus/MinIO `/health`。
- 添加必要 Python 依赖：`pymysql` / `sqlalchemy`、`qdrant-client`、`elasticsearch`、`pyyaml`、`jieba`。

**Validation:** 通过一个轻量脚本或 `/analytics/health` 验证四类依赖可诊断。

**Stop/ask if:** 依赖安装与现有 `knowledge` 环境版本冲突。

## Task 3: Business Data Initialization

**Addresses:** meta 构建有真实业务数据可读。

**Files:** `data_ge/edu-data/init_db.py`, `data_ge/edu-data/generate/*`, `data_ge/edu-data/sql/edu.sql`

**Work:**

- 使用现有 `edu-data` 初始化方式建立 `edu` 库。
- 使用 `--profile smoke` 生成可用于召回的校区、课程、订单、报名、学习行为数据。
- 不改数据生成业务逻辑，除非发现首批 metric 必需字段缺失或明显错误。

**Validation:** `uv run init_db.py` 和 `uv run -m generate.main --profile smoke` 成功。

**Stop/ask if:** 生成数据与首批指标字段不匹配，需要改业务数据模型。

## Task 4: Meta YAML And DDL

**Addresses:** 6 张 meta 表和第一版指标/维度/join 定义。

**Files:** `data_ge/edu-data/meta/education_meta.yaml`, `data_ge/edu-data/sql/edu.sql`

**Work:**

- `meta_table_info` / `meta_column_info` 全量覆盖业务表和字段。
- `meta_metric_info` 至少覆盖首批指标。
- `meta_join_info` 覆盖收入、报名、学习行为、工单的核心路径。
- `meta_dimension_info` 覆盖日期、月份、校区、课程体系、班级、渠道等可分析维度。
- 在 `edu.sql` 末尾追加 6 张 `meta_*` 表 DDL。

**Validation:** MySQL 中可查询 6 张 meta 表，行数符合 smoke 断言。

**Stop/ask if:** README 与 DDL 对同一字段描述冲突且会影响指标口径。

## Task 5: Meta Build Script

**Addresses:** YAML 到 MySQL/Qdrant/ES 的幂等构建。

**Files:** `education_brain/knowledge/analytics/build_meta.py`, `education_brain/knowledge/analytics/*`

**Work:**

- 读取 YAML，校验字段、metric、join、dimension 引用关系。
- 写入 MySQL meta 表。
- 重建 Qdrant `edu_column_info`、`edu_metric_info`。
- 重建 ES `edu_dimension_values`。
- 使用稳定 ID，重复执行不产生重复数据。

**Validation:** `PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate` 成功并输出 counts。

**Stop/ask if:** embedding 服务不可用且无法完成向量构建。

## Task 6: Analytics Diagnostic APIs

**Addresses:** 通过真实 HTTP 请求验收元数据系统。

**Files:** `education_brain/knowledge/api/routes/analytics.py`, `education_brain/knowledge/api/app.py`

**Work:**

- 新增 `/analytics/health`。
- 新增 `/analytics/meta/metrics`。
- 新增 `/analytics/meta/columns`。
- 新增 `/analytics/meta/values`。
- 返回结构与 `requirements-and-plan.md` 保持一致。

**Validation:** `SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh` 通过。

**Stop/ask if:** 接口返回结构需要调整，必须同步 smoke 和文档。

## Explicit Non-goals

- 不实现 NL2SQL LangGraph pipeline。
- 不生成 SQL、不 `EXPLAIN`、不执行分析 SQL。
- 不接入 `/chat/query mode=data_qa`。
- 不做前端图表。
- 不新增宽表或视图。
