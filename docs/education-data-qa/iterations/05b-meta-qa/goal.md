# Iteration 05B Goal: Meta QA 数据说明问答

## Pre-flight

本轮是新功能开发，必须在 Iteration 04 联调闭环和 Iteration 05A 数据准备标准化后开始。

- [ ] Iteration 04 `SMOKE_STAGE=e2e` 通过。
- [ ] Iteration 05A 数据准备流程通过：`generate -> build_meta -> SMOKE_STAGE=meta`。
- [ ] `GET /chat/history` 已能返回 `mode`、`result_type` 和 `blocks`。
- [ ] `/analytics/health` 为 `healthy`，且 table、column、metric、join、dimension counts 非空。
- [ ] 旧“上传课程文档后问文档内容”已经在 Iteration 04 删除，不保留 `knowledge` 兼容模式。

## Goal

新增 `mode=meta_qa`，把现有 meta 资产做成数据说明/指标字典问答：

1. 回答指标口径、字段含义、表关系、join path、支持维度和可问范围。
2. 复用 MySQL meta 表、Qdrant metric/column collection、ES 维度取值索引。
3. LLM 只负责组织解释和引用，不生成 SQL、不执行 SQL。
4. 前端展示“数据问数 / 数据说明”两个主模式。
5. 聊天历史可保存和回放 `meta_qa` blocks。

## Tasks

**Task 1: API 契约与模型** `[subagent: single]`

- 文件范围：`docs/education-data-qa/api-contract.md`、`education_brain/knowledge/models/chat.py`、前端 types。
- 交付：
  - `ChatRequest.mode` 支持 `data_qa`、`meta_qa`。
  - 未知 mode 返回 400。
  - 新增 `result_type=meta_answer`。
  - 新增 `meta_citations` block。
- 验收：契约中存在 `MetaQaResponse`、`MetaCitation` 和 `ChatBlock` 类型定义。

**Task 2: Meta QA prompt 与结构化输出** `[subagent: single]`

- 文件范围：`education_brain/knowledge/analytics/meta_qa/`、prompt 目录。
- 交付：
  - 新增 `meta_qa_answer.md` prompt。
  - 新增 Pydantic model：`MetaQaResponse`、`MetaCitation`。
  - LLM 输出必须结构化解析，解析失败返回 `META_QA_OUTPUT_INVALID`。
  - trace 记录 `stage=meta_qa_llm`、prompt hash、输出摘要、usage；不得向前端返回完整 system prompt 或完整 raw response。
- 验收：清空 LLM key 后不能返回正常 `meta_answer`。

**Task 3: Meta QA 检索与回答 pipeline** `[subagent: single]`

- 文件范围：`education_brain/knowledge/analytics/search.py`、`education_brain/knowledge/analytics/meta_qa/`、`education_brain/knowledge/api/routes/chat.py`。
- 交付：
  - Qdrant 召回 metric/column。
  - MySQL meta 表补全公式、描述、默认过滤、允许维度和 join path。
  - ES 只用于维度值解释和 disambiguation。
  - citations 只能来自已召回或已补全的 meta 对象。
- 验收：首批问题返回 markdown + `meta_citations`，且不包含 SQL 或 `DataQaResult.visual`。

**Task 4: 前端模式与渲染** `[subagent: single]`

- 文件范围：`education_brain_front/src/app/api/chat.ts`、chat page、types。
- 交付：
  - 主 UI 展示两个模式：“数据问数”=`data_qa`，“数据说明”=`meta_qa`。
  - 不展示旧 `knowledge` 主入口。
  - `meta_citations` 渲染为指标/字段/表/维度/join 引用列表。
  - `DataQaResultView` 不复用给 `meta_qa`。
- 验收：同一会话中 `data_qa` 和 `meta_qa` 可混合展示、刷新恢复。

**Task 5: 历史与 smoke** `[subagent: single]`

- 文件范围：`chat_history.py`、`smoke_test_data_qa.sh`、smoke 文档。
- 交付：
  - 保存并回放 `mode=meta_qa`、`result_type=meta_answer`、`blocks`。
  - 新增 `SMOKE_STAGE=meta_qa`。
  - `SMOKE_STAGE=all` 可以包含 `meta_qa`，但不包含 `bootstrap`。
- 验收：
  ```bash
  cd education_brain
  SMOKE_STAGE=meta_qa ./knowledge/tests/smoke_test_data_qa.sh
  ```

## Validation

```bash
cd education_brain
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=meta_qa ./knowledge/tests/smoke_test_data_qa.sh
SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
```

```bash
cd education_brain_front
npm run build
```

## Guardrails

- `meta_qa` 不生成 SQL、不执行 SQL。
- `meta_qa` 不回答真实统计值；统计值必须走 `data_qa`。
- `meta_qa` 不猜不存在的 metric/table/column。
- 旧 `knowledge` 不作为兼容 mode 保留；传入 `knowledge` 或未知 mode 返回 400。
- 如果 `education_meta.yaml` 描述不足，优先补 meta，不让 LLM 猜。
