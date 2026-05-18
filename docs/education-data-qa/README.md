# 教育问数系统开发文档

本目录用于沉淀教育问数系统的标准设计和迭代规划。

## 目录结构

```text
docs/education-data-qa/
  standard/
    insight.md
  testing/
    smoke-test-metrics.md
  iterations/
    01-meta-system/
      goal.md                  ← agent 执行入口
      requirements-and-plan.md
      development-plan.md
    02-nl2sql-pipeline/
      goal.md
      requirements-and-plan.md
    03-chat-integration/
      goal.md
      requirements-and-plan.md
    04-visualization-and-polish/
      goal.md
      requirements-and-plan.md
```

## 文档职责

- `standard/insight.md`：长期标准设计，记录系统目标、架构约束、核心数据结构和技术边界。
- `testing/smoke-test-metrics.md`：跨迭代 smoke test 标准，记录每轮必须通过的真实请求级验收。
- `iterations/*/goal.md`：**agent 执行入口**。结构化的迭代指令，包含 Pre-flight（上一轮收束验证）、Goal、Tasks（含 subagent 并行/串行标注）、Validation、Review、Guardrails。开发时以 goal.md 为主驱动。
- `iterations/*/requirements-and-plan.md`：每次迭代的范围、交付物、验收标准和注意事项。
- `iterations/*/development-plan.md`：详细开发计划，goal.md 中的 task 引用此文件获取实现细节。

## 使用规则

- 迭代要求和实施计划只写入对应迭代目录。
- `standard/insight.md` 只在标准设计发生变化时更新。
- 每次迭代的验收必须引用 `testing/smoke-test-metrics.md`，优先用 `curl` 真实请求验证服务行为。
- 每次迭代完成后，应在对应迭代文档中补充验收结果和遗留问题。

## Agent 驱动开发流程

每轮迭代按以下流程执行：

1. **Pre-flight**：使用 review subagent 验证上一轮交付物，跑上一轮 smoke test，输出状态摘要
2. **用户确认**：Pre-flight 通过后等待用户确认继续，有问题则报告不自行修复
3. **Tasks 执行**：按 goal.md 中的 Stage 顺序执行，标记为 `parallel` 的 task 使用 subagent 并行
4. **Validation**：执行本轮 smoke test
5. **Review**：使用只读 reviewer subagent（当前可用角色优先用 `explorer`）独立审查本轮交付物
6. **用户确认关闭**：review 结果输出后等待用户确认关闭迭代
