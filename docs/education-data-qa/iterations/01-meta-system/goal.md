# Iteration 01 Goal: 环境与元数据系统

## Pre-flight

本迭代是首轮，无上一轮收束验证。执行以下环境检查：

- [ ] 确认 `data_ge/edu-data/sql/edu.sql` 存在且包含业务表 DDL
- [ ] 确认 `data_ge/edu-data/README.md` 存在（字段信息提取来源）
- [ ] 确认 `docs/education-data-qa/standard/insight.md` 存在（设计标准）
- [ ] 确认本机 Docker 可用：`docker compose version`

如果有检查项失败，停下来报告，不要自行绕过。

## Goal

建立教育问数系统的可运行基础链路：本地 Docker 环境一键启动，业务数据可初始化，元数据从 YAML 构建到 MySQL meta 表 / Qdrant / ES，并能通过 HTTP smoke test 真实召回。

## References

- 详细开发计划：[development-plan.md](development-plan.md)
- 需求和设计收束：[requirements-and-plan.md](requirements-and-plan.md)
- 设计标准：[../../standard/insight.md](../../standard/insight.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)

## Tasks

### Stage A1：Docker 环境（先执行）

**Task 1: Docker 环境** `[subagent: single]`
- 文件范围：`infra/education-data-qa/`
- 参考：`/home/ccr/local-docker/nl2sql-env` 的 compose 结构
- 交付：MySQL 8.0 / ES 8.19 + IK / Kibana / Qdrant v1.16 / TEI Embedding 全部可启动
- 验收：`docker compose ps` 全部 running；如果 compose 配置 healthcheck，则要求 healthy；`curl` / `mysqladmin ping` 可访问 MySQL、ES、Qdrant、Embedding 探针
- 详见 development-plan.md Task 1

### Stage A2：后端配置与业务数据（依赖 Stage A1，可并行）

Docker 环境启动后，以下任务互不依赖，可使用 subagent 并行执行。

**Task 2: 后端依赖配置** `[subagent: parallel]`
- 文件范围：`education_brain/knowledge/pyproject.toml`, `core/config.py`, `core/clients.py`
- 交付：ANALYTICS_MYSQL / QDRANT / ES / EMBEDDING 配置项和 client factory
- 验收：probe 脚本或 `/analytics/health` 可诊断四类依赖
- 详见 development-plan.md Task 2

**Task 3: 业务数据初始化** `[subagent: parallel]`
- 文件范围：`data_ge/edu-data/`
- 交付：`uv run init_db.py` + `uv run -m generate.main --profile smoke` 成功
- 验收：MySQL `edu` 库有业务数据，首批指标涉及的表有数据行
- 详见 development-plan.md Task 3

### Stage B：元数据定义（依赖 Stage A）

Stage A 全部完成后执行。

**Task 4: Meta YAML 与 DDL** `[subagent: single]`
- 文件范围：`data_ge/edu-data/meta/education_meta.yaml`, `data_ge/edu-data/sql/edu.sql`
- 数据来源：字段物理信息从 `README.md` 结构化提取，role/description/alias 人工补充
- 交付：6 张 meta 表 DDL + 完整 YAML 配置
- 验收：MySQL 中可查询 6 张 meta 表
- stop/ask：README 与 DDL 对同一字段描述冲突且影响指标口径
- 详见 development-plan.md Task 4

### Stage C：构建与接口（依赖 Stage B）

**Task 5: Meta 构建脚本** `[subagent: single]`
- 文件范围：`education_brain/knowledge/analytics/`
- 交付：`build_meta.py` 完成 YAML → MySQL → Qdrant → ES 三阶段幂等构建
- 验收：`cd education_brain && uv run python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate` 成功并输出 counts
- stop/ask：embedding 服务不可用
- 详见 development-plan.md Task 5

**Task 6: 诊断 API** `[subagent: single]`
- 文件范围：`education_brain/knowledge/api/routes/analytics.py`
- 交付：`/analytics/health`, `/analytics/meta/metrics`, `/analytics/meta/columns`, `/analytics/meta/values`
- 验收：返回结构与 smoke-test-metrics.md 一致
- 详见 development-plan.md Task 6

## Validation

所有 Task 完成后，执行最终验收：

```bash
cd education_brain
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

必须通过的断言：
- `/analytics/health` 返回 healthy 或 degraded，counts.tables > 0, counts.metrics >= 10
- 搜索"收入"召回 `paid_revenue`
- 搜索"实付金额"召回 `order.paid_amount`
- 搜索真实校区名召回对应维度字段

## Review

验收通过后，使用只读 reviewer subagent（当前可用角色优先用 `explorer`）对本轮交付物做独立 review：

- review 范围：本轮新增/修改的所有文件
- 重点检查：
  - meta YAML 与 DDL 的字段一致性
  - build_meta.py 的幂等性（重复执行不产生重复数据）
  - API 返回结构与 smoke-test-metrics.md 的契约一致性
  - 是否引入了超出本轮范围的代码（如 SQL 生成、LangGraph pipeline）
- review 结果输出后，等待用户确认再关闭本轮迭代

## Guardrails

本轮不做：
- NL2SQL LangGraph pipeline
- SQL 生成 / EXPLAIN / SQL 执行
- 聊天接入 `mode=data_qa`
- 前端图表
- 宽表或视图

遇到以下情况必须 stop/ask：
- 端口冲突（3306/9200/6333/8081）且无法调整
- Python 依赖与现有 knowledge 环境版本冲突
- README 与 DDL 字段描述冲突影响指标口径
- embedding 服务不可用导致向量构建无法完成
