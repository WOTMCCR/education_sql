# Iteration 03 Goal: 完整 LLM NL2SQL

## Pre-flight

上一轮收束验证，使用只读 reviewer subagent（当前可用角色优先用 `explorer`）执行：

- [ ] `SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh` 通过，确认规则化 baseline 未回归。
- [ ] `POST /analytics/query` 首批三题返回完整 `DataQaResult`。
- [ ] SQL 注入 / 多语句输入被拦截，`execute_sql=skipped`。
- [ ] 当前 OpenAI 兼容 LLM 配置可用：`OPENAI_API_KEY` 必须存在，`LLM_MODEL` 必须存在，`OPENAI_BASE_URL` 可为空或指向兼容服务。
- [ ] 使用 `knowledge.core.llm.chat_completion_text` 做一次真实结构化 JSON smoke，确认不是本地规则 fallback。
- [ ] review 当前 `education_brain/knowledge/analytics/agent/`，确认哪些节点仍是规则/模板实现。

Pre-flight 结果输出后，等待用户确认是否继续。本轮只升级 `/analytics/query` 的 LLM NL2SQL 能力，不接聊天历史和前端真实联调。

## Goal

将当前规则/模板 SQL 生成升级为受限上下文驱动的 LLM NL2SQL：LLM 负责意图结构化、候选过滤、SQL 生成和一次纠错；系统负责元数据召回、join path 约束、SQL 安全校验、执行和 `DataQaResult` 包装。

本轮 `SMOKE_STAGE=llm` 必须真实调用 LLM。LLM 不可用时返回结构化 `LLM_UNAVAILABLE`，不能用规则模板静默通过本轮验收。

入口边界：本轮只验收显式问数 trigger，例如 `/analytics/query`。不要依赖普通聊天意图识别自动切到 NL2SQL；未来 `/chat/query mode=data_qa` 属于 Iteration 04 的显式 trigger 接入，不属于本轮。

本轮完成后，系统应能支持首批问题之外的教育经营问数，例如：

- 朝阳校区本月收入是多少？
- 最近 30 天各校区收入趋势如何？
- 本月报名人数最多的课程系列是什么？
- 上周和本周收入对比如何？
- 本月退款金额是多少？

## References

- 需求和设计：[requirements-and-plan.md](requirements-and-plan.md)
- 长期标准：[../../standard/insight.md](../../standard/insight.md)
- API 契约：[../../api-contract.md](../../api-contract.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)
- 当前规则 baseline：`education_brain/knowledge/analytics/agent/nodes/core.py`
- LLM 调用包装：`education_brain/knowledge/core/llm.py`

## Tasks

### Stage A：LLM 契约与状态结构

**Task 1: LLM Provider 与结构化输出策略** `[subagent: single]`
- 文件范围：`education_brain/knowledge/core/llm.py`、`education_brain/knowledge/analytics/agent/llm_utils.py`
- 交付：使用现有 OpenAI SDK 封装，优先 `response_format={"type":"json_schema", ...}` 的 Structured Outputs；兼容服务不支持时才退到 `json_object` + Pydantic 校验。
- 配置：`OPENAI_API_KEY` 和 `LLM_MODEL` 是 Iteration 03 必需项；`OPENAI_BASE_URL` 可用于 OpenAI 兼容服务。
- 推理参数：结构化节点默认 `temperature=0`，必要时最高 `0.1`；每个节点设置独立 timeout 和 max tokens。
- 验收：无 LLM 配置时 `SMOKE_STAGE=llm` 返回 `LLM_UNAVAILABLE`，不能走规则 fallback 伪装成功。

**Task 2: LLM 输出 schema 与解析器** `[subagent: single]`
- 文件范围：`education_brain/knowledge/analytics/agent/`
- 交付：定义 `StructuredIntent`、`SqlPlan`、`SqlCandidate` 等 Pydantic/schema，支持 JSON 提取、字段校验、错误降级。
- 验收：LLM 返回 markdown fenced JSON、普通 JSON、轻微多余文本时都能解析；缺字段时返回结构化错误。

**Task 3: DataAgentState 与 LLM Trace 扩展** `[subagent: single]`
- 文件范围：`state.py`、`nodes/core.py` 或拆分后的节点文件。
- 交付：保存 `expanded_keywords`、`structured_intent`、`llm_filter_decision`、`sql_plan`、`candidate_context`、`llm_raw_outputs`、`llm_usage`。
- 验收：trace 中能看到每个 LLM 节点的输入摘要、输出状态、token usage、降级原因；敏感信息不写入 trace。

### Stage B：关键词扩展、意图结构化与候选过滤

**Task 4: expand_search_keywords LLM 节点** `[subagent: single]`
- 交付：在 `extract_keywords` 后调用 LLM 做同义词/近义词/业务别名扩展，输出用于 `recall_column`、`recall_metric`、`recall_value` 的搜索关键词。
- 重点：替代当前 `_with_income_aliases` 中不断追加硬编码别名的趋势；硬编码词典只能作为最低限度 seed，不是泛化主路径。
- 验收：用户问“营业额/销售额/实收/退费/报名数”时，expanded keywords 能覆盖对应 metric alias 和字段 alias。

**Task 5: structure_intent LLM 节点** `[subagent: single]`
- 交付：LLM 将自然语言问题转换为结构化 intent，包括 analysisType、metrics、dimensions、filters、timeRange、sort、limit、visualHint。
- 重点：必须把中文时间表达转为绝对日期范围；日期由系统注入，不让 LLM 自行假设今天。
- 验收：覆盖单指标、趋势、排名、明细、对比、过滤、退款类问题。

**Task 6: filter_table + filter_metric LLM 精筛** `[subagent: parallel]`
- 交付：LLM 只在召回候选内选择表、字段和指标；不得创造不存在的 schema。
- 验收：噪音候选被剔除；缺少必要候选时返回 `RECALL_EMPTY` 或 `JOIN_PATH_NOT_FOUND`，不硬猜。

**Task 7: filter_dimension/filter_value 确定性精筛** `[subagent: single]`
- 依赖：Task 6 输出的候选表和指标。
- 设计变更：维度和取值过滤优先使用 `StructuredIntent`、`allowed_dimensions`、候选取值和 join path 做确定性筛选，不再单独增加 LLM 节点；LLM 负责意图结构化和 SQL 生成，系统负责把维度/取值约束到已召回 context。
- 交付：在已保留表/指标范围内筛选维度和取值过滤，补齐必要 join path。
- 验收：校区、课程、课程系列、顾问等过滤不会选择已被剔除表上的字段；缺 join path 时停止。

### Stage C：受限上下文 SQL 生成

**Task 8: Prompt 模板与 SQL context builder** `[subagent: single]`
- 交付：将过滤后的指标、维度、字段、join path、默认过滤、时间范围、数据库方言压缩成 LLM prompt context。
- prompt 文件：放在 `education_brain/knowledge/analytics/agent/prompts/`，按节点拆分为 `expand_keywords`、`structure_intent`、`filter_candidates`、`generate_sql`、`correct_sql`。
- prompt 策略：system prompt 固定 MySQL 8.0、SELECT-only、安全禁止事项、只输出 JSON；few-shot 示例只使用教育问数核心场景，且不得包含全库 schema。
- 重点：context 中只包含候选子集，不暴露全库 66 张表；每个 prompt 有 token budget 上限和截断策略。
- 维护规则：每次 smoke/eval 暴露稳定失败模式时，必须补充 few-shot 或约束，并配套新增/更新 eval case。
- 验收：prompt 输入可记录到 trace/debug，包含必要 join path 和禁止事项。

**Task 9: generate_sql LLM 节点** `[subagent: single]`
- 交付：LLM 基于 SQL context 输出只读 MySQL SELECT，以及所用字段、join、过滤、排序、limit 的结构化解释。
- 重点：LLM 不负责安全放行；安全仍由 `validate_sql` 和 `execute_sql` 控制。
- 验收：首批问题与扩展问题都生成合法 SQL，并返回 `DataQaResult.visual` 所需字段。

**Task 10: correct_sql LLM 纠错** `[subagent: single]`
- 交付：`EXPLAIN` 失败时，将错误、原 SQL、受限 context 交给 LLM 纠错一次。
- 约束：`correct_sql` 只能在 `validate_sql` 失败、SQL unsafe 或 `EXPLAIN` 报错时触发。SQL 已合法时必须跳过，不得无条件调用 LLM。
- 验收：保留字、列别名、join 顺序等常见错误可纠正；第二次失败返回 `SQL_VALIDATE_FAILED`，不执行。

### Stage D：安全、评测与降级

**Task 11: SQL 安全边界加固** `[subagent: single]`
- 交付：继续强制 SELECT-only、禁多语句、禁注释、禁危险函数、禁 `INTO OUTFILE`、只读事务、明细默认 limit。
- 验收：prompt 注入和 SQL 注入问题均返回结构化错误，`execute_sql=skipped`。

**Task 12: LLM NL2SQL eval set** `[subagent: parallel]`
- 文件范围：`education_brain/knowledge/tests/fixtures/`、`knowledge/tests/`、smoke 脚本。
- 交付：新增 15-25 条教育问数 eval case，覆盖指标、维度、时间、过滤、排序、明细、错误态。
- 验收：`SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh` 或等价 pytest 能输出通过率、失败 case、SQL 和 error。

**Task 13: DataQaResult visual mapper 泛化** `[subagent: single]`
- 交付：根据 LLM structured intent 和 SQL 结果自动选择 `stat`、`line`、`bar`、`table`，并生成 columns/x/y。
- 验收：扩展问题不需要前端硬编码即可渲染。

实现说明：当前 `finalize_result` 在 `graph.invoke()` 后由 `pipeline.py` 手动调用，用于纯计算地组装 `DataQaResult`，不访问外部依赖。这个做法可以接受；如果后续把更多后处理、外部调用或可失败逻辑放进 finalize，应把 `finalize_result_node` 注册进 LangGraph，让 trace 和异常处理保持一致。

## Validation

```bash
cd education_brain
SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
```

建议新增 pytest：

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m pytest knowledge/tests/test_llm_nl2sql_pipeline.py -q
```

必须通过的断言：

- 首批三题仍通过，SQL 安全边界不回归。
- 至少 15 条扩展 eval case 中，核心集合全部通过；可选集合通过率达到迭代文档设定阈值。
- `trace.stages` 至少包含真实 LLM 节点 `expand_search_keywords`、`structure_intent`、`generate_sql`，并记录 `llm_usage` 或等价 usage 摘要。
- 面向前端的 trace 必须脱敏：只保留 LLM 调用证据、prompt 名称/hash、输入摘要、输出摘要和 usage，不返回完整 system prompt 或完整 raw response。
- LLM 生成 SQL 只引用候选 context 中存在的表和字段。
- 所有成功 SQL 都经过 `EXPLAIN` 和只读执行。
- 所有失败都返回结构化 `DataQaResult.error`，并保留 trace。
- LLM 不可用时返回 `LLM_UNAVAILABLE`；`SMOKE_STAGE=llm` 不允许规则 fallback 通过。

## Review

使用只读 reviewer subagent（当前可用角色优先用 `explorer`）review：

- Prompt 是否只暴露召回/过滤后的子集，而不是全库 schema。
- Prompt 模板是否固定 MySQL 8.0、安全边界和 JSON-only 输出，并包含足够 few-shot。
- Prompt 是否有维护规则：每次 smoke/eval 暴露稳定失败模式时，必须补充 few-shot 或约束，并配套 eval case。
- 关键词扩展是否真实走 LLM，而不是继续依赖 `_with_income_aliases` 硬编码扩展。
- LLM 输出 schema 是否稳定，解析失败是否可诊断。
- `SMOKE_STAGE=llm` 是否能证明至少关键词扩展、意图结构化、SQL 生成三个 LLM 节点被调用。
- SQL 安全检查是否独立于 LLM，且不可绕过。
- 纠错是否仅在失败路径触发、最多一次，失败后是否停止执行。
- Eval case 是否覆盖真实业务问题，而不是只覆盖模板题。
- 是否破坏现有 `/analytics/query`、`DataQaResult` 和前端渲染契约。

## Guardrails

本轮不做：

- 自动从普通问答识别问数，仍使用显式 `mode=data_qa`。
- 用 LLM 自行判断 SQL 是否安全，或让 LLM 代替 `is_safe_select_sql`、`EXPLAIN`、只读事务等确定性边界。
- 宽表、物化视图或新数据仓库层。
- 续费/复购等尚未定义清楚口径的指标。
- 让 LLM 直接读取全库 schema 或自由猜 join。
- 在 `SMOKE_STAGE=llm` 中用规则模板 fallback 冒充 LLM 成功。
- 未经 schema 校验直接消费 LLM 文本。

遇到以下情况必须 stop/ask：

- LLM 生成 SQL 需要使用当前 meta 中不存在的指标、维度、join path。
- 用户问题需要新业务口径，但 `education_meta.yaml` 未定义对应 metric。
- Eval case 对“正确 SQL”的业务口径存在歧义。
- 需要从 OpenAI 兼容 API 切换到本地 Ollama 或其他非 OpenAI provider 作为默认实现。
