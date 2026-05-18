# Iteration 03：完整 LLM NL2SQL

## 背景

当前 Iteration 02 已经形成最小 NL2SQL 闭环，但 SQL 生成主要依赖规则和模板分支：

```text
analysisType=trend   -> 固定 DATE(time_column) + GROUP BY
analysisType=ranking -> 固定校区维度 join + GROUP BY + ORDER BY
default              -> 固定 SUM(paid_amount)
```

这能稳定跑通首批问题，但不能泛化到更多教育经营问题。Iteration 03 的目标是把 SQL 生成升级为 LLM 主导，同时保留 meta、join path、安全校验和只读执行这些确定性边界。

## 目标

实现受限上下文 LLM NL2SQL：

- LLM 负责理解问题、选择候选、生成 SQL、解释生成计划、进行一次纠错。
- 系统负责召回候选、提供 meta 约束、推导 join path、校验 SQL、安全执行、包装 `DataQaResult`。
- LLM 不能直接面对全库 schema，不能创造不存在的表/字段/指标/维度。

## 范围

本轮覆盖：

- OpenAI 兼容 LLM provider 策略和结构化输出能力探测。
- LLM 关键词扩展，替代不断追加硬编码业务别名的主路径。
- 结构化意图识别：metric、dimension、filter、timeRange、sort、limit、analysisType。
- LLM 精筛候选表、字段、指标、维度和取值。
- LLM SQL 生成，输出结构化 SQL plan。
- LLM SQL 纠错一次。
- 扩展 eval case 和 smoke 覆盖。
- `DataQaResult.visual` 泛化映射。

本轮不覆盖：

- 自动意图识别并从普通问答切换到问数。
- 流式问数。
- 宽表/视图/预聚合。
- 未定义业务口径的新指标。
- 续费、复购等当前明确排除的指标。

触发策略：

- Iteration 03 只以显式问数入口作为 trigger：`POST /analytics/query`。
- 后续聊天入口即使接入问数，也应使用显式 `mode=data_qa` 或前端“问数据”入口作为强 trigger。
- 普通聊天意图识别只能作为建议或辅助，不应单独决定是否进入 NL2SQL，避免解释类问题、课程问答或普通 RAG 被误路由。

## 关键设计

### 1. LLM 不是安全边界

LLM 可以生成 SQL，但不能决定 SQL 是否安全。安全边界仍由确定性代码执行：

- 只允许 `SELECT`。
- 禁止多语句。
- 禁止注释绕过。
- 禁止危险函数和文件写入。
- `EXPLAIN` 必须先通过。
- 执行必须使用只读事务。
- 明细查询必须有默认 `LIMIT`。

这条边界不可交给 LLM 判断。可以放宽的是结构化输出格式兼容，例如 LLM 在 `joins` 中返回候选 join path 的等价表达式时，由代码归一化为 `join_id`；但是否允许执行仍必须由候选 context 校验、`is_safe_select_sql`、`EXPLAIN` 和只读事务共同决定。

### 2. LLM 只看候选子集

Prompt 中只允许出现：

- 召回和过滤后的 table/column/metric/dimension/value。
- `meta_join_info` 推导出的 join path。
- metric 默认过滤和允许维度。
- 当前日期、数据库方言、安全规则。

禁止把 66 张表全量 schema 放进 prompt。

### 3. LLM 输出必须结构化

建议拆成两个 schema：

```ts
type StructuredIntent = {
  analysisType: 'single_metric' | 'trend' | 'ranking' | 'comparison' | 'detail'
  metrics: string[]
  dimensions: string[]
  filters: Array<{ field: string; op: string; value: unknown; label?: string }>
  timeRange?: { start: string; end: string; endExclusive: string; grain?: string; label?: string }
  sort?: Array<{ field: string; direction: 'asc' | 'desc' }>
  limit?: number
  visualHint?: 'stat' | 'line' | 'bar' | 'table'
}

type SqlPlan = {
  sql: string
  visual: { type: 'stat' | 'line' | 'bar' | 'table'; x?: string; y?: string[] }
  usedTables: string[]
  usedColumns: string[]
  usedMetrics: string[]
  joins: string[]
  assumptions: string[]
}
```

后端需要校验：

- `usedTables` 都在候选 context 中。
- `usedColumns` 都在候选 context 中。
- `usedMetrics` 都在候选 context 中。
- `joins` 都来自 `meta_join_info` 的路径。
- SQL 中引用的表/字段能在 context 中找到。

### 4. 规则 baseline 作为 fallback

当前规则模板不要直接删除。建议保留为：

- eval 对照组。
- 非 `SMOKE_STAGE=llm` 的开发期显式降级路径。
- 三个首批问题的稳定兜底。

但 fallback 必须在 trace 中标记，例如：

```json
{ "name": "generate_sql", "status": "ok", "message": "used rule fallback because LLM unavailable" }
```

不能让用户误以为使用了完整 LLM NL2SQL。

`SMOKE_STAGE=llm` 是例外：本阶段验收必须证明真实 LLM 节点被调用。LLM 不可用时应返回 `LLM_UNAVAILABLE`，不能用规则 baseline 通过。

### 5. OpenAI 兼容结构化输出策略

默认使用现有 `knowledge.core.llm.chat_completion_text` 和 OpenAI 兼容配置：

- `OPENAI_API_KEY`：Iteration 03 必需。
- `LLM_MODEL`：Iteration 03 必需。
- `OPENAI_BASE_URL`：可为空；为空时走 OpenAI 默认服务，非空时走兼容服务。
- 结构化节点默认 `temperature=0`，必要时最高 `0.1`。

结构化输出优先级：

1. 启动或首次调用时做一次 capability probe，测试当前模型/服务是否支持 `response_format={"type":"json_schema", ...}`。
2. 支持时使用 JSON Schema structured output。
3. 不支持时退到 `response_format={"type":"json_object"}` + Pydantic 校验。
4. 如果兼容服务连 `json_object` 也不支持，则使用 JSON-only prompt + Pydantic 校验，但 trace 必须记录降级原因。

Capability probe 应集中在 `llm_utils.py` 中完成，不能让每个节点各自处理 provider 兼容分支。

### 6. Prompt 策略

Prompt 模板放在：

```text
education_brain/knowledge/analytics/agent/prompts/
```

建议拆分：

```text
expand_keywords.md
structure_intent.md
filter_candidates.md
generate_sql.md
correct_sql.md
```

每个 prompt 必须包含：

- 固定 system 约束：MySQL 8.0、SELECT-only、只输出 JSON、不得猜 schema。
- 当前日期由系统注入，LLM 不得自行假设。
- 候选 context 只包含召回/过滤后的子集。
- 2-5 个教育问数 few-shot 示例，覆盖收入、趋势、排名、过滤、错误态。
- 明确的 token budget 和截断策略。

Prompt 维护规则：

- 每次 smoke/eval 发现稳定失败模式，优先补充 few-shot 或约束语句。
- prompt 变更必须同时新增或更新至少一个 eval/smoke case，避免只靠人工感觉调 prompt。
- prompt 文件可以记录完整约束；面向前端的 trace 只保留 prompt 名称或 hash，不返回完整 system prompt。

### 7. Trace 与成本记录

每个 LLM 节点都要在 trace 中记录：

- 节点名。
- 是否真实调用 LLM。
- provider/model。
- 结构化输出模式：`json_schema` / `json_object` / `json_prompt`。
- 输入 context 摘要和输出摘要。
- token usage，如果 provider 返回 usage；否则记录 `usageUnavailable=true`。
- 降级原因或解析错误。

面向前端或聊天历史返回的 trace 必须脱敏：

- 保留：节点名、是否真实调用 LLM、provider/model、输出模式、prompt 名称或 hash、输入摘要、输出摘要、usage。
- 移除：完整 system prompt、完整 user prompt、完整 raw response、API key、base URL 中的敏感 token。
- 若需要排查完整 prompt/raw response，只能写入受控服务端 debug 日志或本地 artifact，不随 API 返回。

## Eval Case 分层

### Core cases

这些必须全部通过：

| 问题 | 期望 |
|---|---|
| 本月总收入是多少？ | `single_metric` + `stat` |
| 最近30天收入趋势如何？ | `trend` + `line` |
| 哪个校区收入最高？ | `ranking` + `bar` |
| 朝阳校区本月收入是多少？ | filter=校区 + `stat` |
| 最近30天各校区收入趋势如何？ | time + campus + `line/table` |
| 本月报名人数最多的课程系列是什么？ | metric=enrollment_count + series ranking |
| 本月退款金额是多少？ | metric=refund_amount 或结构化缺口错误 |
| 本月总收入是多少？; DROP TABLE order; | `SQL_UNSAFE` + execute skipped |

### Extended cases

这些用于衡量泛化能力，允许初期设通过率阈值：

| 类别 | 示例 |
|---|---|
| 时间对比 | 上周和本周收入对比如何？ |
| 多条件过滤 | 朝阳校区 Python 课程本月收入是多少？ |
| 明细 | 查看本月新报名学员明细 |
| 排名 | 哪个顾问本月成交金额最高？ |
| 空结果 | 不存在的校区本月收入是多少？ |
| 口径缺失 | 本月复购率是多少？ |

建议第一版阈值：

- Core cases：100% 通过。
- Extended cases：>= 70% 返回正确结果或正确结构化错误。
- SQL 安全类：100% 通过。

## 实施计划

### Task 1：LLM Provider 与结构化输出策略

**文件：**

- `education_brain/knowledge/analytics/agent/llm_utils.py`
- `education_brain/knowledge/core/llm.py`

**工作：**

- 使用现有 OpenAI SDK 封装。
- 集中实现 JSON Schema capability probe。
- 支持 `json_schema -> json_object -> JSON-only prompt` 的能力降级。
- 设置结构化节点默认 `temperature=0`。
- 无 LLM 配置时返回 `LLM_UNAVAILABLE`。

**验收：**

- `SMOKE_STAGE=llm` 在缺少 LLM 配置时失败为结构化错误。
- trace 记录当前输出模式和 provider/model。

### Task 2：Schema 与解析器

**文件：**

- `education_brain/knowledge/analytics/agent/state.py`
- `education_brain/knowledge/analytics/agent/llm_schema.py`
- `education_brain/knowledge/analytics/agent/llm_utils.py`

**工作：**

- 定义 `StructuredIntent`、`SqlPlan`、`FilterDecision`。
- 实现 JSON 提取和 Pydantic 校验。
- 将解析错误映射为 `DataQaResult.error`。

**验收：**

```bash
PYTHONPATH=. knowledge/.venv/bin/python -m pytest knowledge/tests/test_llm_nl2sql_schema.py -q
```

### Task 3：DataAgentState 与 LLM Trace 扩展

**文件：**

- `education_brain/knowledge/analytics/agent/state.py`
- `education_brain/knowledge/analytics/agent/pipeline.py`
- `education_brain/knowledge/analytics/agent/nodes/`

**工作：**

- 保存 `expanded_keywords`、`structured_intent`、`llm_filter_decision`、`sql_plan`、`candidate_context`。
- 保存 `llm_raw_outputs` 和 `llm_usage`。
- trace 中记录真实 LLM 调用、provider/model、输出模式、usage、降级原因。

**验收：**

- `SMOKE_STAGE=llm` 返回的 trace 至少包含 `expand_search_keywords`、`structure_intent`、`generate_sql`。
- LLM 不可用时 trace 能定位失败节点。

### Task 4：expand_search_keywords 节点

**文件：**

- `education_brain/knowledge/analytics/agent/nodes/`
- `education_brain/knowledge/analytics/agent/prompts/`

**工作：**

- 在 `extract_keywords` 后调用 LLM 做同义词/近义词/业务别名扩展。
- 输出统一 `expanded_keywords`，供 `recall_column`、`recall_metric`、`recall_value` 使用。
- 当前 `_with_income_aliases` 只保留为最低限度 seed，不作为泛化主路径。

**验收：**

- “营业额”“销售额”“实收”“退费”“报名数”能扩展到对应 metric/field alias。
- trace 记录 `expand_search_keywords` 的真实 LLM 调用。

### Task 5：structure_intent 节点

**文件：**

- `education_brain/knowledge/analytics/agent/nodes/`
- `education_brain/knowledge/analytics/agent/prompts/`

**工作：**

- 输入用户问题、当前日期、召回摘要。
- 输出结构化 intent。
- 时间范围必须转成绝对日期。

**验收：**

- “上周”“本月”“最近30天”都能落到明确 `start/end/endExclusive`。
- 不确定口径返回结构化错误或 `needs_metric_definition`。

### Task 6：filter_table + filter_metric LLM 精筛

**文件：**

- `nodes/filter.py` 或现有 `nodes/core.py`

**工作：**

- 从召回结果中筛表、字段和指标。
- 校验选择结果必须来自候选。
- 缺失关键候选时停止，不让 LLM 猜。

**验收：**

- 噪音召回不会进入 SQL context。
- 校区过滤能保留 `org_campus.campus_name` 和必要 join path。

### Task 7：filter_dimension/filter_value 确定性精筛

**文件：**

- `nodes/filter.py` 或现有 `nodes/core.py`

**工作：**

- 依赖 Task 6 输出的候选表和指标。
- 设计变更：维度和取值过滤不再单独增加 LLM 节点，改用 `StructuredIntent`、`allowed_dimensions`、候选取值和 join path 做确定性筛选。
- LLM 负责意图结构化、候选表/指标精筛、SQL 生成和必要纠错；维度/取值由系统约束到已召回 context，避免 LLM 在低价值步骤中扩大候选范围。
- 在已保留候选内筛选维度和取值过滤。
- 过滤结果必须能通过 `meta_join_info` 推导 join path。

**验收：**

- 校区、课程、课程系列、顾问过滤不会选择已被剔除表上的字段。
- 缺 join path 时返回结构化错误。

### Task 8：Prompt 模板与 SQL context builder

**文件：**

- `education_brain/knowledge/analytics/agent/sql_context.py`
- `education_brain/knowledge/analytics/agent/prompts/`

**工作：**

- 将候选 context 压缩为 prompt。
- 注入 MySQL 方言、只读限制、join path、metric 默认过滤。
- 编写 `expand_keywords`、`structure_intent`、`filter_candidates`、`generate_sql`、`correct_sql` prompt 模板。
- 加入少量教育问数 few-shot。
- 限制 token 大小，记录 context 摘要和截断信息。

**验收：**

- 不包含全库 schema。
- 包含 SQL 生成所需的 base table、measure column、time column、join path。
- Prompt 固定 JSON-only 输出、MySQL 8.0 和安全禁止事项。

### Task 9：LLM SQL 生成与校验

**文件：**

- `nodes/sql_generate.py`
- `analytics/agent/sql.py`

**工作：**

- LLM 输出 `SqlPlan`。
- 校验 SQL 引用的表/字段在 context 中。
- 接入现有 `is_safe_select_sql`、`EXPLAIN`、只读执行。

**验收：**

- Core cases 生成合法 SQL。
- 违反 context 的 SQL 被拒绝，不执行。

### Task 10：LLM SQL 纠错

**文件：**

- `nodes/sql_correct.py`

**工作：**

- 只在 `EXPLAIN` 失败时触发。
- 只在 `validate_sql` 失败、SQL unsafe 或 `EXPLAIN` 报错时触发。
- SQL 已合法时直接进入 `execute_sql`，或 `correct_sql` 节点提前返回 skipped，不得额外调用 LLM。
- 输入原 SQL、错误信息、受限 context。
- 最多纠错一次。

**验收：**

- 常见 SQL 错误可修复。
- 修复后仍失败返回 `SQL_VALIDATE_FAILED`。
- 合法 SQL 路径中 `correct_sql` 不调用 LLM，trace 标记为 `skipped` 或通过条件边不出现该节点。

### Task 11：SQL 安全边界加固

**文件：**

- `education_brain/knowledge/analytics/agent/sql.py`
- `education_brain/knowledge/analytics/agent/nodes/`

**工作：**

- 继续强制 SELECT-only、禁多语句、禁注释、禁危险函数、禁 `INTO OUTFILE`。
- 保持 `EXPLAIN` 前置和只读事务。
- 明细查询默认追加 limit。

**验收：**

- prompt 注入和 SQL 注入问题均返回结构化错误，`execute_sql=skipped`。

### Task 12：LLM NL2SQL eval set

**文件：**

- `education_brain/knowledge/tests/test_llm_nl2sql_pipeline.py`
- `education_brain/knowledge/tests/fixtures/data_qa_eval_cases.yaml`
- `education_brain/knowledge/tests/smoke_test_data_qa.sh`
- `docs/education-data-qa/testing/smoke-test-metrics.md`

**工作：**

- 新增 15-25 条教育问数 eval case。
- 区分 core / extended / safety。
- 输出每条 eval 的 SQL、visual.type、error、LLM 节点调用情况、通过/失败原因。
- 当前收束策略：先保持现有 `SMOKE_STAGE=llm` 跑通全流程；完整 YAML eval set 可作为 Iteration 04 pre-flight 或独立测试补强项，不阻塞本轮聊天联调启动。

**验收：**

```bash
SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
```

### Task 13：Visual mapper 泛化

**文件：**

- `nodes/finalize.py` 或现有 result builder。

**工作：**

- 根据 `analysisType`、`SqlPlan.visual` 和结果列生成 `visual.columns/x/y`。
- 不再只硬编码 `paid_revenue`、`campus`、`paid_date`。

**验收：**

- 新 metric / 新 dimension 不需要前端改代码。

实现说明：当前 `finalize_result` 是 `graph.invoke()` 后的纯计算 result builder，不访问外部依赖，因此可以暂时保留在 `pipeline.py` 中手动调用。若后续在 finalize 中加入可失败后处理、外部服务调用、复杂 visual 推断或 trace 依赖，应将 `finalize_result_node` 注册到 LangGraph，避免绕过 `_stage` wrapper 的异常处理和 trace 收集。

## 验收标准

- Core cases 100% 通过。
- Safety cases 100% 通过。
- Extended cases 第一版 >= 70%。
- 所有成功结果返回完整 `DataQaResult`。
- 所有失败结果返回结构化 `DataQaResult.error`。
- SQL 引用表/字段必须来自候选 context。
- trace 至少包含真实 LLM 节点 `expand_search_keywords`、`structure_intent`、`generate_sql`。
- LLM 不可用时返回 `LLM_UNAVAILABLE`，`SMOKE_STAGE=llm` 不允许规则 fallback 通过。

## 风险与取舍

- LLM 结果不稳定：用结构化 schema、低温度、受限上下文和 eval 固定行为。
- Prompt 过长：context builder 必须压缩候选，只保留 SQL 需要的信息。
- Provider 兼容性差异：集中做 JSON Schema capability probe，不让每个节点各自处理。
- 业务口径漂移：metric 的默认过滤和 allowed_dimensions 必须优先于 LLM。
- SQL 安全：LLM 不是安全边界，任何绕过都必须被确定性代码拦截。
- 调试困难导致退回规则：`SMOKE_STAGE=llm` 必须验证真实 LLM 节点调用。
- 真实泛化速度：先让 Core 稳定，再逐步提高 Extended 覆盖率。

## Stop / Ask

遇到以下情况先停下来对齐：

- 用户问题依赖未定义 metric，例如复购率、续费率、转介绍率。
- LLM 需要新 join path，但 `meta_join_info` 没有路径。
- eval 中“正确结果”无法从现有业务口径判断。
- 需要切换 LLM 提供商或模型以满足 JSON 稳定性、成本、速度要求。
