# Iteration 02 Goal: 问数 Pipeline

## Pre-flight

上一轮收束验证，使用只读 reviewer subagent（当前可用角色优先用 `explorer`）执行：

- [ ] `SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh` 全部通过
- [ ] `/analytics/health` 中 MySQL meta / Qdrant / ES / Embedding 均可用
- [ ] `paid_revenue`、`enrollment_count` 等首批指标能通过 `/analytics/meta/metrics` 召回
- [ ] `order.paid_amount` 等关键字段能通过 `/analytics/meta/columns` 召回
- [ ] 真实校区/课程名能通过 `/analytics/meta/values` 召回
- [ ] review Iteration 01 是否有遗留问题需要修补

Pre-flight 结果输出后，等待用户确认是否继续。如果 Pre-flight 发现问题，报告问题清单，不要自行修复上一轮代码。

## Goal

实现从自然语言问题到 SQL 执行结果的最小 NL2SQL 闭环：12 节点 LangGraph DAG 端到端可运行，三个首批问题能生成合法 SQL 并执行返回结果。

## References

- 需求和设计：[requirements-and-plan.md](requirements-and-plan.md)
- 设计标准（DAG 定义见 §3.3）：[../../standard/insight.md](../../standard/insight.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)
- 参考实现：`~/dev/LearningProject/nl2sql-shopkeeper/app/agent/`

## Tasks

### Stage A：Pipeline 基础框架

**Task 1: LangGraph DAG 骨架与 State** `[subagent: single]`
- 文件范围：`education_brain/knowledge/analytics/agent/`
- 交付：DataAgentState 定义 + 12 节点 DAG 编排（先用 placeholder 函数）
- 验收：DAG 可实例化并空跑不报错
- 参考：nl2sql-shopkeeper `app/agent/state.py` 和 `app/agent/graph.py`

### Stage B：召回节点（可并行）

以下三个召回节点互不依赖，使用 subagent 并行执行。

**Task 2: extract_keywords** `[subagent: parallel]`
- 交付：jieba TF-IDF 关键词提取 + 教育业务自定义词典
- 验收："本月总收入是多少"提取出含"收入"的关键词

**Task 3: recall_column + recall_metric + recall_value** `[subagent: parallel]`
- 交付：LLM 关键词扩展 → Qdrant/ES 搜索 → entity ID 去重
- 验收：输入"收入"相关关键词，能召回 paid_revenue 指标和 order.paid_amount 字段

**Task 4: merge_retrieved_info** `[subagent: parallel]`
- 交付：合并三路召回结果，根据 meta_join_info 推导 join 路径
- 验收：给定 paid_revenue 的召回结果，能推导出 order → order_item → series_cohort 的 join 链

### Stage C：过滤与生成（依赖 Stage B）

**Task 5: filter_table + filter_metric** `[subagent: single]`
- 交付：LLM 从候选中过滤出最相关的表和指标
- 验收：噪音候选被过滤，保留核心表和指标

**Task 6: add_extra_context → generate_sql → validate_sql → correct_sql → execute_sql** `[subagent: single]`
- 交付：SQL 生成、EXPLAIN 校验、纠错（最多 1 次）、只读执行
- 重点：MySQL 保留字转义（`order` → `` `order` ``）、时间表达式解析、SQL 安全边界
- 验收：三个首批问题能生成合法 SQL 并执行返回 DataQaResult

### Internal Checkpoint：02A 召回上下文

在进入 Task 6 前，必须先确认：

- 三个首批问题都能召回正确 metric、关键字段和候选取值。
- `merge_retrieved_info` 能输出必要 join path。
- 输出上下文足够解释 SQL 生成需要使用哪些表、字段、过滤和时间列。

如果 02A 不稳定，不进入 SQL 生成/执行阶段。

### Stage D：API 接入

**Task 7: /analytics/query 接口** `[subagent: single]`
- 交付：`POST /analytics/query` 接受自然语言问题，返回 DataQaResult
- 验收：`SMOKE_STAGE=pipeline` 通过

## Validation

```bash
cd education_brain
SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh
```

必须通过的断言：
- "本月总收入是多少" → single_metric, paid_revenue, visual.type=stat
- "最近30天收入趋势" → trend, visual.type=line, 行数 > 1
- "哪个校区收入最高" → ranking, visual.type=bar, 有排序
- 所有成功请求返回 explain.metrics / explain.tables / explain.joins / trace.stages
- SQL 注入 / 多语句输入返回结构化错误，不执行危险 SQL

## Review

使用只读 reviewer subagent（当前可用角色优先用 `explorer`）review：
- DAG 节点间的 state 传递是否完整
- SQL 安全边界是否严格执行（SELECT-only, 禁多语句, EXPLAIN 前置）
- LLM prompt 中是否只暴露了召回/过滤后的上下文（不是全库 schema）
- 是否引入了聊天接入或前端代码

## Guardrails

本轮不做：
- 聊天接入 `mode=data_qa`
- 前端图表渲染
- 宽表或视图
- 超出首批指标范围的 metric 支持

遇到以下情况必须 stop/ask：
- meta_join_info 无法推导必要 join 路径（说明 Iteration 01 的 join 配置不完整）
- LLM 服务不可用且无法完成关键词扩展/SQL 生成
- 时间表达式解析覆盖不了首批问题中的时间范围
