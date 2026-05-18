# Iteration 02：问数 Pipeline

## 目标

实现从自然语言问题到 SQL 执行结果的最小 NL2SQL 闭环。

## 范围

实现 12 节点 LangGraph DAG：

```text
extract_keywords
  -> [recall_column || recall_metric || recall_value]
  -> merge_retrieved_info
  -> [filter_table || filter_metric]
  -> add_extra_context
  -> generate_sql
  -> validate_sql
  -> correct_sql
  -> execute_sql
```

## 首批支持问题

- 本月总收入是多少？
- 最近 30 天收入趋势如何？
- 哪个校区收入最高？

## 关键实现点

- `merge_retrieved_info` 需要根据 `meta_join_info` 推导 join 路径。
- 中文时间表达需要转为明确日期范围。
- `date` / `month` 使用 `meta_dimension_info.expression_template` 从 metric 的 `time_column` 派生。
- LLM 只基于召回和过滤后的上下文生成 SQL，不直接面对全库 schema。
- 物理 SQL 必须处理 MySQL 保留字表名；例如 meta 逻辑 ID `order` 在 SQL 中应渲染为 `` `order` ``。
- 如果 Iteration 01 的 `meta_join_info` 无法推导必要路径，本迭代应直接返回结构化错误，不让 LLM 自由猜 join。

## 前置要求

- Iteration 01 的 `SMOKE_STAGE=meta` 必须通过。
- `paid_revenue`、`enrollment_count`、`attendance_rate` 等首批指标必须能召回到 metric、相关字段和 join 路径。
- `/analytics/health` 中 MySQL meta、Qdrant、Elasticsearch、Embedding 必须可诊断；LLM 不可用时端到端 NL2SQL 可跳过，但不能把跳过计为通过。

## SQL 安全边界

- 只允许 `SELECT`。
- 禁止多语句。
- 禁止 SQL 注释绕过。
- 先 `EXPLAIN`，失败则纠错一次。
- 纠错后仍失败则返回降级说明，不执行。
- 未指定 limit 的明细查询默认追加 `LIMIT 1000`。

## 验收标准

- 必须通过 `docs/education-data-qa/testing/smoke-test-metrics.md` 中的 Iteration 02 smoke 指标。
- 必须能执行：
  ```bash
  cd education_brain
  SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh
  ```
- 三个首批问题都能通过 `POST /analytics/query` 真实生成 SQL、`EXPLAIN` 校验并执行。
- SQL 执行结果能转换为 `DataQaResult`，并返回 SQL、指标口径、使用表、join 路径和 trace。
- 危险 SQL / 多语句类输入不能执行，必须返回结构化错误或安全降级。

## 防偏差点

- 不要在本迭代引入宽表或视图；所有 SQL 仍基于 `edu-data` 原始表。
- 不要让 LLM 接触全库 schema；必须使用召回和过滤后的上下文。
- 不要把 SQL 字符串生成成功等同于 pipeline 成功；验收必须包含 `EXPLAIN`、只读执行和 `DataQaResult` 结构。
- 危险输入的理想返回是 `error.stage/code/message`，并在 trace 中标记 SQL 执行为 `skipped`。

## 风险拆分建议

本轮范围较大，执行时可以设置两个内部检查点：

- `02A`：完成关键词提取、三路召回、`merge_retrieved_info`、join path 推导，只返回可解释上下文，不生成 SQL。
- `02B`：在 `02A` 通过后，再实现 SQL 生成、`EXPLAIN`、纠错、只读执行和 `DataQaResult`。

如果 `02A` 不能稳定召回指标、字段、取值和 join path，不进入 SQL 生成阶段。
