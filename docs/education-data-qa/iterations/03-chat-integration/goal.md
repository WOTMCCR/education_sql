# Iteration 03 Goal: 聊天接入

## Pre-flight

上一轮收束验证，使用只读 reviewer subagent（当前可用角色优先用 `explorer`）执行：

- [ ] `SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh` 通过
- [ ] `SMOKE_STAGE=pipeline ./knowledge/tests/smoke_test_data_qa.sh` 通过
- [ ] 三个首批问题通过 `POST /analytics/query` 返回完整 DataQaResult
- [ ] SQL 安全边界验证：注入/多语句输入被拦截
- [ ] review Iteration 02 是否有遗留问题

Pre-flight 结果输出后，等待用户确认。发现问题时报告，不自行修复。

## Goal

把问数能力接入现有聊天体验：前端显式模式开关，后端 `mode=data_qa` 路由，问数结果以 block 结构进入同一聊天历史。

## References

- 需求和设计：[requirements-and-plan.md](requirements-and-plan.md)
- 设计标准（前后端契约见 §5、ChatMessage 见 §2）：[../../standard/insight.md](../../standard/insight.md)
- Smoke 验收标准：[../../testing/smoke-test-metrics.md](../../testing/smoke-test-metrics.md)

## Tasks

### Stage A：后端聊天扩展（可并行）

**Task 1: ChatMessage 模型扩展** `[subagent: parallel]`
- 文件范围：聊天相关的 model / schema 文件
- 交付：ChatRequest 增加 mode，ChatMessage 增加 mode + blocks
- 验收：现有 RAG 聊天不受影响

**Task 2: data_qa 路由** `[subagent: parallel]`
- 文件范围：聊天 API 路由
- 交付：`POST /chat/query` 识别 `mode=data_qa` 后调用 analytics pipeline
- 验收：mode=data_qa 返回 data_qa_result block

### Stage B：前端（依赖 Stage A）

**Task 3: 模式开关 UI** `[subagent: single]`
- 文件范围：`education_brain_front/src/`
- 交付：聊天页面显式 [普通问答] [数据问数] 开关
- 验收：切换模式后请求携带正确 mode

**Task 4: data_qa_result 渲染** `[subagent: single]`
- 文件范围：`education_brain_front/src/`
- 交付：assistant 消息中的 data_qa_result block 有基础渲染（文本摘要 + 表格 + SQL 折叠）
- 验收：问数回复在聊天中可读

### Stage C：持久化与回放

**Task 5: 聊天历史持久化** `[subagent: single]`
- 交付：问数结果完整保存到聊天历史（mode + blocks + DataQaResult）
- 验收：刷新页面后问数回复可恢复，SQL 和口径信息不丢失

## Validation

```bash
cd education_brain
SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
```

前端验证：

```bash
cd education_brain_front
npm run build
# Playwright 或等价浏览器测试：切换“数据问数”后，请求体包含 mode=data_qa，回复 block 可渲染。
```

必须通过的断言：
- 普通问答 `POST /chat/query` 不带 mode 仍返回 RAG 结果
- `mode=data_qa` 返回 data_qa_result block
- 聊天历史可取回问数 assistant 消息，包含 mode + blocks + SQL
- 问数失败也作为 assistant 消息保存

## Review

使用只读 reviewer subagent（当前可用角色优先用 `explorer`）review：
- mode 路由是否干净隔离，不污染现有 RAG pipeline
- 聊天历史中的 data_qa_result 是否保存完整结构（不是只保存渲染文本）
- 前端是否只根据 block.type 渲染，不硬编码业务逻辑
- 普通问答回归是否通过

## Guardrails

本轮不做：
- 真实图表渲染（stat/line/bar），只做基础文本+表格展示
- 自动意图识别（本轮只用显式开关）
- SSE 流式问数结果（本轮可用同步返回）

遇到以下情况必须 stop/ask：
- 现有聊天模型结构变更可能破坏已有 RAG 对话数据
- 前端 ChatMessage 类型扩展方式不确定
