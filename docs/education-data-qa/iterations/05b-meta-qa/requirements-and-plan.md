# Iteration 05B：Meta QA 数据说明问答

## 背景

`data_qa` 回答“多少、趋势、排名、明细”，需要生成并执行 SQL。`meta_qa` 回答“是什么、怎么算、能不能问、为什么不能问”，只解释 meta，不触碰统计查询。

这种分离能避免两类退化：

- `meta_qa` 为了解释口径误生成 SQL。
- `data_qa` 为了补充说明绕过结构化问数 pipeline。

## 产品模式

```ts
type ProductChatMode = 'data_qa' | 'meta_qa'
```

- `data_qa`：数据问数，允许 SQL 生成和执行。
- `meta_qa`：数据说明，不生成 SQL、不执行 SQL。
- 未知 mode 或旧 `knowledge`：返回 400。

## 旧 RAG 生命周期

- Iteration 04 起：旧文档 RAG 已删除，不保留旧 API。
- Iteration 05A 起：数据准备入口收束为 `init_db -> generate -> build_meta`。
- Iteration 05B 起：产品只有 `data_qa` 和 `meta_qa` 两个显式 mode；旧 `knowledge` 请求返回 400。

## 后端结构化模型

建议新增 Pydantic model：

```python
from typing import Literal
from pydantic import BaseModel, Field

MetaCitationKind = Literal["metric", "column", "table", "dimension", "join", "value"]
MetaCitationSource = Literal[
    "meta_metric_info",
    "meta_column_info",
    "meta_table_info",
    "meta_dimension_info",
    "meta_join_info",
]

class MetaCitation(BaseModel):
    kind: MetaCitationKind
    id: str
    name: str
    source: MetaCitationSource
    description: str = ""

class MetaQaResponse(BaseModel):
    answer_markdown: str
    citations: list[MetaCitation] = Field(default_factory=list)
    unsupported_reason: str = ""
    suggested_mode: Literal["meta_qa", "data_qa"] = "meta_qa"
    trace_summary: dict = Field(default_factory=dict)
```

`source` 是必填字段，前端可据此选择图标、标签和跳转策略。`kind=value` 的 citation 仍应归属到对应维度定义，`source="meta_dimension_info"`。

## Prompt 规范

新增 prompt：

```text
education_brain/knowledge/analytics/meta_qa/prompts/meta_qa_answer.md
```

必须包含：

- 只解释 meta，不生成 SQL。
- 不回答真实统计值；遇到统计值问题建议切换 `data_qa`。
- 只引用提供的 metric/table/column/dimension/join/value context。
- 输出严格 JSON，符合 `MetaQaResponse`。
- 2-5 个 few-shot：指标口径、字段含义、支持维度、join path、未定义指标。

Prompt 维护规则：

- 每次 smoke/eval 发现稳定失败模式，优先补充 few-shot 或约束语句。
- prompt 变更必须附带至少一个 eval/smoke case，避免只靠人工感觉调 prompt。
- trace 面向前端只保留 prompt 名称或 hash、输入摘要、输出摘要和 usage，不暴露完整 system prompt 或完整 raw response。

## Pipeline

```text
query
  -> recall_metric_column(Qdrant)
  -> load_meta_context(MySQL)
  -> search_dimension_value(ES, optional)
  -> meta_qa_llm(MetaQaResponse)
  -> validate_citations
  -> ChatResponse blocks
```

错误码：

- `META_RECALL_EMPTY`
- `META_QA_UNAVAILABLE`
- `META_QA_OUTPUT_INVALID`
- `META_CITATION_INVALID`
- `META_QUERY_REQUIRES_DATA_QA`

## Chat blocks

```ts
type MetaCitationSource =
  | 'meta_metric_info'
  | 'meta_column_info'
  | 'meta_table_info'
  | 'meta_dimension_info'
  | 'meta_join_info'

type MetaCitation = {
  kind: 'metric' | 'column' | 'table' | 'dimension' | 'join' | 'value'
  id: string
  name: string
  source: MetaCitationSource
  description?: string
}

type ChatBlock =
  | { type: 'markdown'; content: string }
  | { type: 'data_qa_result'; data: DataQaResult }
  | { type: 'meta_citations'; data: MetaCitation[] }
```

`meta_qa` 成功响应：

- `mode="meta_qa"`
- `intent="meta_qa"`
- `result_type="meta_answer"`
- `blocks[0].type="markdown"`
- `blocks[1].type="meta_citations"`

## Smoke

`SMOKE_STAGE=meta_qa` 必须验证：

- `POST /chat/query mode=meta_qa` 返回 `result_type=meta_answer`。
- `blocks` 中存在 markdown 和 `meta_citations`。
- citations 的 `source` 只能是约定枚举。
- trace 中存在 `meta_qa_llm` 调用证据、usage 或 usageUnavailable。
- 清空或禁用 LLM key 后不能返回正常 `meta_answer`。
- `GET /chat/history` 能恢复完整 `meta_qa` blocks。
- 回答“本月收入是多少？”时返回 `META_QUERY_REQUIRES_DATA_QA` 或建议切换 `data_qa`，不执行 SQL。

## 验收问题

- 实付收入怎么算？
- 收入相关指标有哪些？
- paid_revenue 支持哪些维度？
- 校区收入排名涉及哪些表？
- 为什么复购率暂时不能问？
- 本月收入是多少？（应建议切换 `data_qa`）
