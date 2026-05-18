# Iteration 04：真实图表与体验打磨

## 目标

基于稳定的 `DataQaResult` 结构，完成真实图表、表格、SQL 与 trace 展示。

前端功能、mock 基线、联调检查清单详见：[frontend-functionality.md](frontend-functionality.md)。

## 范围

- `stat` 指标卡。
- `line` 趋势图。
- `bar` 排名图。
- `table` 结果表。
- SQL / 指标口径 / trace 折叠面板。
- 错误和降级状态展示。
- 聊天页显式 `[普通问答] [数据问数]` 模式切换。
- `data_qa_result` block 渲染与聊天历史回放。
- 前端 mock fixtures 与真实接口联调切换。
- 基础 code splitting，避免图表库进入聊天页主 bundle。

## 图表映射

| analysisType | visual.type | 示例 |
|---|---|---|
| `single_metric` | `stat` | 本月总收入 |
| `trend` | `line` | 最近 30 天收入趋势 |
| `ranking` | `bar` | 校区收入排名 |
| `comparison` | `bar` / `table` | 本周和上周对比 |
| `detail` | `table` | 明细列表 |

## 图表契约

- 前端只根据 `DataQaResult.visual.type`、`visual.columns`、`visual.rows`、`visual.x`、`visual.y` 渲染，不重新推断业务语义。
- `visual.columns[].key` 必须能在每一行 `visual.rows[]` 中找到。
- `stat` 至少有 1 行、1 个数值列。
- `line` 必须有 `x` 和至少一个 `y` 序列，日期顺序由后端保证。
- `bar` 必须有维度列和指标列，排序逻辑由后端结果体现。
- 错误态也使用 `data_qa_result` block 展示，前端不把失败渲染成普通文本。

## 聊天接入契约

- `POST /chat/query` 带 `mode=data_qa` 时，必须返回 `result_type=data_qa_result`。
- 数据问数 assistant 消息必须包含 `blocks`，其中至少一个 block 为 `{ "type": "data_qa_result" }`。
- `blocks[].data` 必须是完整 `DataQaResult` 对象，不能是摘要字符串。
- `/chat/history` 必须能恢复完整 `mode`、`result_type`、`blocks`、SQL、指标口径、trace、warnings 和 error。
- 当前不做流式问数；`/chat/query/stream` 继续用于普通问答。

## 联调准备要求

- 前端先用 `education_brain_front/src/app/mock/data-qa.ts` 的 mock fixtures 开发和验收视觉状态。
- 后端 `POST /analytics/query` 完成后，先绕过聊天历史直接联调 `DataQaResult`。
- 后端 `POST /chat/query mode=data_qa` 完成后，再联调聊天 block 和历史回放。
- 首批联调问题必须覆盖 `stat`、`line`、`bar`、`table`、错误态五类结果。
- 后端业务失败也应返回结构化 `DataQaResult.error`，不要只返回普通 HTTP 错误文本。
- 真实联调前必须确认 `visual.columns[].key` 与每行 `visual.rows[]` 对齐。

## 验收标准

- 必须通过 `docs/education-data-qa/testing/smoke-test-metrics.md` 中的 Iteration 04 smoke 指标。
- 必须能执行：
  ```bash
  cd education_brain
  SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
  ```
- 三个首批问题能展示真实图表，且图表数据来自后端返回的 `DataQaResult.visual`。
- 表格列名、数值格式、日期格式符合 `DataQaResult.visual.columns`。
- SQL 默认折叠但可展开。
- trace 展示阶段状态、耗时、行数。
- 空结果、SQL 失败、召回失败都有明确 UI 状态，并能在聊天历史中恢复。
- 聊天页 `mode=data_qa` 能渲染 `data_qa_result` block，而不是普通 markdown。
- 刷新页面后，问数历史消息仍能恢复为图表和折叠面板。
- 前端 `npm run build` 不出现 `chunk larger than 500 kB` 警告；如出现，需记录原因或继续拆分。

## 注意事项

- 不做营销式页面，保持后台工具型布局。
- 图表由后端 `visual.type` 和字段配置驱动，前端不重新推断业务语义。
- SQL、指标口径、trace 默认折叠，但字段必须完整保留，方便调试和教学。
- 前端图表验收不能只依赖后端 `visual` 协议；必须用 Playwright 或等价浏览器测试验证 stat、line、bar、table 至少各有一个真实渲染结果。
- 图表库保持按需加载；不要把 `recharts` 静态引入聊天页主模块。
- 移动端必须保证图表和表格主体可读；如果侧边栏挤压内容，优先隐藏侧边栏或改为抽屉导航。
