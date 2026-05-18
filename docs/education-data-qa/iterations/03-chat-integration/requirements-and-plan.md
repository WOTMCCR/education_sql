# Iteration 03：聊天接入

## 目标

把问数能力接入现有聊天体验，让问数结果进入同一个聊天历史。

## 范围

- 前端聊天页增加显式模式开关：
  - 普通问答
  - 数据问数
- 后端聊天接口支持 `mode=data_qa`。
- assistant message 支持 block 结构：
  - `markdown`
  - `data_qa_result`
- 问数结果保存到同一个聊天历史。
- RAG pipeline 和 data_qa pipeline 保持独立。

## 前后端契约

以 `standard/insight.md` 中的 `DataQaResult` 为标准。

## 模型变更要求

现有聊天模型只有普通 `answer/items/citations` 结构，本迭代需要显式扩展：

- `ChatRequest` 增加 `mode?: "knowledge" | "data_qa"`，默认普通问答。
- `ChatResponse` 增加 `mode` 和 `blocks`，同时保留 `answer` 等旧字段以兼容现有前端。
- `ChatMessage` 历史持久化增加 `mode` 和 `blocks`，问数失败也必须保存 assistant 回复。
- `blocks` 中的 `data_qa_result` 必须保存完整 `DataQaResult`，不能只保存渲染后的文本摘要。

## 验收标准

- 必须通过 `docs/education-data-qa/testing/smoke-test-metrics.md` 中的 Iteration 03 smoke 指标。
- 必须能执行：
  ```bash
  cd education_brain
  SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
  ```
- 普通问答模式仍可通过 `POST /chat/query` 走现有 RAG / 搜索。
- 数据问数模式下，`POST /chat/query` 带 `mode=data_qa` 后返回 `data_qa_result` block。
- 历史记录重新加载后，问数回复仍能恢复，包括 `mode`、`blocks`、SQL 和口径解释。

## 注意事项

- 显式开关优先，不在本迭代做复杂自动意图切换。
- 数据问数失败也应作为一条 assistant 回复呈现，包含失败阶段和可读错误。
- RAG pipeline 和 data_qa pipeline 仍保持独立；不要把问数逻辑塞进现有 RAG graph。
- 普通问答 smoke 必须继续通过，避免接入 `mode` 时破坏既有 `/chat/query` 行为。
- 前端改动必须至少通过 `npm run build`；模式开关和请求体 `mode=data_qa` 需要用 Playwright 或等价浏览器测试验证。
