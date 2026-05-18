# Iteration 01：环境与元数据系统

## 目标

建立教育问数系统的第一条可运行基础链路：本地依赖环境可一键启动，`edu-data` 业务数据可初始化，元数据可从 README/YAML/DDL 构建到 MySQL meta 表、Qdrant 和 Elasticsearch，并能通过 HTTP smoke test 真实召回。

## 范围

- 新增项目内 Docker 环境配置，覆盖 MySQL、Elasticsearch + IK、Kibana、Qdrant、Embedding 服务。
- 配置后端问数依赖项：MySQL、Qdrant、Elasticsearch、Embedding API。
- 跑通 `edu-data` 的数据库初始化和前期数据生成。
- 创建 `data_ge/edu-data/meta/education_meta.yaml`。
- 在 `data_ge/edu-data/sql/edu.sql` 中添加 6 张 meta 表：
  - `meta_table_info`
  - `meta_column_info`
  - `meta_metric_info`
  - `meta_column_metric`
  - `meta_join_info`
  - `meta_dimension_info`
- 实现 `education_brain/knowledge/analytics/build_meta.py`。
- 构建 Qdrant collection：
  - `edu_column_info`
  - `edu_metric_info`
- 构建 ES 维度取值索引。
- 优先参考 `/home/ccr/local-docker/nl2sql-env` 的 MySQL、Qdrant、Elasticsearch、Embedding 环境。
- 暴露 Iteration 01 所需的 `/analytics/health` 和 `/analytics/meta/*` 诊断/召回接口。

## 环境收束

本迭代需要把运行环境沉淀在当前项目，而不是依赖外部目录的手工状态。

### 项目内新增环境目录

推荐目录：

```text
infra/education-data-qa/
  README.md
  docker-compose.yaml
  .env.example
  mysql/
    README.md
  elasticsearch/
    Dockerfile
    plugins/
      elasticsearch-analysis-ik-8.19.10.zip
  volumes/
    .gitignore
```

说明：

- `docker-compose.yaml` 参考 `/home/ccr/local-docker/nl2sql-env/docker-compose.yaml`。
- ES 镜像继续基于 `elasticsearch:8.19.10`，安装 `elasticsearch-analysis-ik-8.19.10.zip`。
- Qdrant 使用 `qdrant/qdrant:v1.16`。
- Embedding 使用 `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`。
- BGE 模型文件体积较大，不提交到仓库；通过环境变量挂载本机模型目录。
- `volumes/` 只保留 `.gitignore`，运行数据不纳入 Git。

### 服务与端口

| 服务 | 镜像/来源 | 默认端口 | 作用 |
|---|---|---:|---|
| MySQL | `mysql:8.0` | 3306 | 存放 `edu` 业务库和 `meta_*` 表 |
| Elasticsearch | 本地 Dockerfile + IK | 9200 | 维度取值召回 |
| Kibana | `kibana:8.19.10` | 5601 | 调试 ES 索引 |
| Qdrant | `qdrant/qdrant:v1.16` | 6333 / 6334 | 字段和指标向量召回 |
| Embedding | TEI CPU 1.9 | 8081 | 中文 embedding 服务 |

### MySQL 口径

- 第一版继续使用同一个 MySQL 数据库 `edu`，业务表和 `meta_*` 表都在这个库内。
- 账号密码优先兼容 `data_ge/edu-data/.env`：`root / 123321`，避免先改动数据生成脚本。
- 后续可单独新增只读账号给 SQL 执行器；本迭代不实现 SQL 执行器，因此不是阻塞项。

### Python 依赖

本迭代需要在 `education_brain/knowledge/pyproject.toml` 增加问数构建和检索依赖：

- `pymysql` 或 `sqlalchemy`：MySQL meta 读写。
- `qdrant-client`：Qdrant collection 构建和检索。
- `elasticsearch`：ES index 构建和检索。
- `pyyaml`：读取 `education_meta.yaml`。
- `jieba`：关键词提取预留；Iteration 01 可只用于召回接口，不实现完整 pipeline。

如果 `data_ge/edu-data` 已经具备的依赖只服务数据生成，不要让后端跨项目 import 它的内部模块；后端只依赖 MySQL 中的数据和 YAML。

## 数据系统构建收束

本迭代的“前期数据系统构建”包含 4 层：

1. **业务数据层**：通过 `data_ge/edu-data/init_db.py` 和 `generate.main` 初始化 `edu` 业务库。
2. **元配置层**：编写 `data_ge/edu-data/meta/education_meta.yaml`，表字段以 README 为整理入口，DDL 做校验。
3. **MySQL meta 层**：将 YAML 解析结果写入 6 张 `meta_*` 表。
4. **检索索引层**：将字段/指标写入 Qdrant，将维度取值写入 ES。

本迭代不生成 SQL、不执行业务查询、不做聊天接入。

## 数据来源规则

- 表、字段、枚举、约束、中文释义初稿以 `data_ge/edu-data/README.md` 的结构化提取为主。
- 真实 MySQL / `data_ge/edu-data/sql/edu.sql` 用于验证字段存在、类型一致性、外键关系和缺漏项。
- `role`、`description`、`alias` 允许人工补充或校正。

## Meta 覆盖策略

6 张 `meta_*` 表都需要建立，但每张表的覆盖范围不同：

| meta 表 | 覆盖策略 |
|---|---|
| `meta_table_info` | 全量覆盖 `edu-data` 当前所有业务表。以 `README.md` 为整理入口，以真实 DDL 校验表存在和物理名称。 |
| `meta_column_info` | 全量覆盖所有业务表字段，包括字段类型、是否枚举、中文释义、业务角色和可检索别名。 |
| `meta_metric_info` | 不全量穷举所有可能指标，只覆盖当前问数设计需要的指标；第一版至少覆盖 `standard/insight.md` 中列出的首批指标。 |
| `meta_column_metric` | 只为已定义 metric 维护相关字段映射，不要求每个字段都绑定 metric。 |
| `meta_join_info` | 覆盖首批指标所需的核心 join 路径，并尽量纳入 README / DDL 可验证的外键关系；无法从物理外键推断的业务路径必须人工维护。 |
| `meta_dimension_info` | 覆盖首批指标允许分析的维度，例如日期、月份、校区、课程体系、班级、渠道；不把所有字段都当维度。 |

因此，“全量”只适用于表和字段物理信息。指标、指标字段映射、维度和 join 路径按当前问数范围建设，但不能遗漏收入、报名、学习行为、工单这几条后续 pipeline 会依赖的主链路。

## 接口契约

Iteration 01 需要先固定诊断和召回接口，后续 smoke test 与 pipeline 都以此为准。

### `GET /analytics/health`

返回顶层字段：

```json
{
  "status": "healthy",
  "mysql_meta": {"status": "ok"},
  "qdrant": {"status": "ok"},
  "elasticsearch": {"status": "ok"},
  "embedding": {"status": "ok"},
  "counts": {
    "tables": 66,
    "columns": 0,
    "metrics": 14,
    "joins": 0,
    "dimensions": 0
  }
}
```

- `status` 可为 `healthy` / `degraded` / `unhealthy`。
- 依赖对象至少包含 `status`，失败时补充 `error` 和 `hint`。
- `counts.columns` 等具体数字以实际构建结果为准，示例中的 `0` 不是目标值。

### `GET /analytics/meta/metrics`

每个 item 至少包含：

```json
{"id": "paid_revenue", "name": "收入金额", "score": 0.83}
```

### `GET /analytics/meta/columns`

每个 item 至少包含：

```json
{"id": "order.paid_amount", "full_name": "order.paid_amount", "table_name": "order", "column_name": "paid_amount", "score": 0.81}
```

### `GET /analytics/meta/values`

每个 item 至少包含：

```json
{"field": "org_campus.campus_name", "value": "徐汇校区", "score": 0.76}
```

## 构建脚本契约

`education_brain/knowledge/analytics/build_meta.py` 的第一版 CLI 约定：

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
```

- 默认读取 `data_ge/edu-data/meta/education_meta.yaml`。
- `--recreate` 表示重建 Qdrant collection 和 ES index，并重写 MySQL meta 表。
- Qdrant collection 固定为 `edu_column_info`、`edu_metric_info`。
- ES 维度取值 index 名称固定为 `edu_dimension_values`。
- 重复执行必须幂等：配置删除后，MySQL/Qdrant/ES 中对应旧数据也不能残留。
- 构建日志必须输出表、字段、指标、join、维度、Qdrant points、ES docs 的数量。

## 预期执行顺序

```bash
# 1. 启动依赖环境
cd infra/education-data-qa
docker compose up -d

# 2. 初始化业务库和生成数据
cd ../../data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

# 3. 构建问数 meta 和检索索引
cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate

# 4. 启动后端并跑 smoke
PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

具体命令可在实现时微调，但最终必须在 `infra/education-data-qa/README.md` 中保持同步。

## 验收标准

- Docker 环境配置在当前仓库内，能启动 MySQL、ES、Kibana、Qdrant、Embedding。
- `edu-data` 业务库能初始化并生成 smoke 规模数据。
- `build_meta.py` 可完成三阶段构建：MySQL meta 表、Qdrant、ES。
- meta 表包含全量表字段物理信息，以及当前设计范围内的 metrics、joins、dimensions。
- 必须通过 `docs/education-data-qa/testing/smoke-test-metrics.md` 中的 Iteration 01 smoke 指标。
- 必须能执行：
  ```bash
  cd education_brain
  SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
  ```
- 搜索“收入”能通过 HTTP smoke 在 Qdrant `edu_metric_info` 中召回 `paid_revenue`。
- 搜索“收入”或“实付金额”能通过 HTTP smoke 在 Qdrant `edu_column_info` 中召回 `order.paid_amount`。
- 搜索一个真实校区或课程名能通过 HTTP smoke 在 ES 中召回对应维度字段。

## 注意事项

- 第一轮不做业务视图或宽表。
- 第一轮不做 SQL 生成、`EXPLAIN`、SQL 执行器、LangGraph pipeline、聊天接入和前端图表。
- 构建脚本放在 `education_brain`，但 YAML 和 meta DDL 归属 `edu-data`。
- Qdrant point ID 使用 `uuid5`，构建时采用先删后建，保证配置删除能生效。
- `order` 是 MySQL 保留字。meta 中可以使用逻辑 ID `order.paid_amount`，但后续生成 SQL 时必须转义物理表名，例如 `` `order` ``。
- `/analytics/health` 是问数专属健康检查，不复用现有 `/health` 的 MongoDB / Milvus / MinIO 结果，避免把 RAG 依赖和问数依赖混在一起。
