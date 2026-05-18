# Iteration 04：真实图表与体验打磨

## 目标

基于稳定的 `DataQaResult` 结构，完成真实图表、表格、SQL 与 trace 展示。

## 范围

- `stat` 指标卡。
- `line` 趋势图。
- `bar` 排名图。
- `table` 结果表。
- SQL / 指标口径 / trace 折叠面板。
- 错误和降级状态展示。

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

## 注意事项

- 不做营销式页面，保持后台工具型布局。
- 图表由后端 `visual.type` 和字段配置驱动，前端不重新推断业务语义。
- SQL、指标口径、trace 默认折叠，但字段必须完整保留，方便调试和教学。
- 前端图表验收不能只依赖后端 `visual` 协议；必须用 Playwright 或等价浏览器测试验证 stat、line、bar、table 至少各有一个真实渲染结果。
