# Iteration 04 Goal: 真实图表与体验打磨

## Pre-flight

上一轮收束验证，使用只读 reviewer subagent（当前可用角色优先用 `explorer`）执行：

- [ ] `SMOKE_STAGE=all ./knowledge/tests/smoke_test_data_qa.sh` 中 meta / pipeline / chat 阶段全部通过
- [ ] 普通问答回归通过
- [ ] 问数 assistant 消息在聊天历史中可恢复，包含完整 DataQaResult
- [ ] review Iteration 03 是否有遗留问题

Pre-flight 结果输出后，等待用户确认。发现问题时报告，不自行修复。

## Goal

基于稳定的 DataQaResult 结构，完成真实图表（stat/line/bar/table）渲染和 SQL/口径/trace 折叠面板，打磨错误和空结果状态展示。

本轮以前端 mock 版问数体验为基线，联调时将 mock `DataQaResult` 切换为真实 `/analytics/query` 和 `/chat/query mode=data_qa` 返回的数据，不改变前端渲染契约。

## References

- 需求和设计：[requirements-and-plan.md](requirements-and-plan.md)
- 前端功能与联调准备：[frontend-functionality.md](frontend-functionality.md)
- 设计标准（DataQaResult.visual 见 §5）：[../../standard/insight.md](../../standard/insight.md)
- API 契约：[../../api-contract.md](../../api-contract.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)

## Tasks

### Stage A：图表组件（可并行）

以下图表类型互不依赖，使用 subagent 并行执行。

**Task 1: stat 指标卡** `[subagent: parallel]`
- 交付：single_metric 类型渲染为指标卡，支持货币/百分比格式
- 验收："本月总收入"显示为格式化数值卡片

**Task 2: line 趋势图** `[subagent: parallel]`
- 交付：trend 类型渲染为折线图，x 轴为日期，y 轴为指标值
- 验收："最近30天收入趋势"显示为折线图

**Task 3: bar 排名图** `[subagent: parallel]`
- 交付：ranking 类型渲染为柱状图，按值排序
- 验收："哪个校区收入最高"显示为排名柱状图

**Task 4: table 结果表** `[subagent: parallel]`
- 交付：detail/comparison 类型渲染为数据表格
- 验收：明细查询显示为可滚动表格

### Stage B：辅助面板（依赖 Stage A）

**Task 5: SQL / 口径 / trace 折叠面板** `[subagent: single]`
- 交付：SQL 代码块 + 指标口径解释 + trace 阶段状态/耗时，默认折叠
- 验收：点击可展开，字段完整

### Stage C：异常状态

**Task 6: 错误和空结果展示** `[subagent: single]`
- 交付：空结果、SQL 校验失败、召回失败、降级说明的 UI 状态
- 验收：各异常场景有明确 UI 反馈，且能在聊天历史中恢复

### Stage D：前后端联调与打包

**Task 7: 真实接口切换** `[subagent: single]`
- 交付：前端从 mock fixtures 切换到真实 `POST /analytics/query` / `POST /chat/query mode=data_qa`，保持 `DataQaResultView` 不改业务逻辑
- 验收：首批 stat/line/bar/table/error 五类结果均来自真实后端响应

**Task 8: 历史回放验证** `[subagent: single]`
- 交付：`GET /chat/history` 返回的问数 assistant message 可恢复完整 `data_qa_result` block
- 验收：刷新页面后仍展示图表、SQL、口径、trace、warnings/error

**Task 9: Bundle 检查** `[subagent: single]`
- 交付：保持图表组件和图表库按需加载
- 验收：`npm run build` 不出现 `chunk larger than 500 kB` 警告；如出现需解释并修复或记录原因

## Validation

```bash
cd education_brain
SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=all ./knowledge/tests/smoke_test_data_qa.sh
```

前端验证：

```bash
cd education_brain_front
npm run build
# Playwright 或等价浏览器测试：stat/line/bar/table 均有真实渲染，SQL/口径/trace 可展开。
```

必须通过的断言：
- stat/line/bar/table 四种图表类型均可渲染
- visual.columns 中每列都能在 visual.rows 中找到对应 key
- SQL/口径/trace 默认折叠但可展开，字段齐全
- 空结果和错误态有 UI 状态，不渲染为普通文本
- `mode=data_qa` 的聊天回复渲染 `data_qa_result` block
- 刷新历史后问数图表和错误态可恢复
- 图表库不进入聊天页主 chunk，构建无大 chunk 警告
- 所有前序 smoke 阶段（meta/pipeline/chat）不回归

## Review

使用只读 reviewer subagent（当前可用角色优先用 `explorer`）做最终全量 review：
- 前端是否纯粹根据 visual.type 渲染，不硬编码业务逻辑
- 图表数据是否来自后端 DataQaResult.visual，不在前端重新计算
- 异常状态是否覆盖完整（空结果 / SQL 失败 / 召回失败 / 降级）
- 聊天历史是否保存完整 `DataQaResult`，不是只保存摘要文本
- code splitting 是否仍隔离 Recharts / DataQaResultView
- 全链路回归：meta → pipeline → chat → visual

## Guardrails

本轮不做：
- 自动意图识别（保持显式开关）
- 续费/复购指标
- 数据导出

遇到以下情况必须 stop/ask：
- 图表库选型影响包体积或与现有前端框架冲突
- DataQaResult.visual 结构需要扩展才能支持某种图表
- 后端返回结构与 `api-contract.md` 不一致，导致前端必须写业务推断或兼容分支
