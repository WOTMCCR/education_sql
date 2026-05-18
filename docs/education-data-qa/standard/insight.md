# 教育问数系统设计规格

日期：2026-05-18

## 1. 项目概述

基于现有 education_brain_fullstack 项目，新增面向教育业务的 NL2SQL 问数系统。用户通过自然语言查询报名、收入、退款、完课率等经营和教学指标，系统自动生成 SQL 并返回结构化分析结果。

核心设计约束：

- 学习项目，全部代码可改，不保护旧架构
- 保留知识库 RAG，问数 pipeline 与 RAG pipeline 独立
- 不做视图/宽表，直接基于 `edu-data` 原始 66 张业务表生成 SQL
- 暂不做续费/复购指标

## 2. 产品形态

聊天页面新增显式模式开关：

```text
[普通问答] [数据问数]
```

普通问答走现有 RAG / 课程 / 题库。数据问数走 NL2SQL pipeline，回复包含：

```text
回答摘要 | 图表或指标卡 | 结果表格 | 指标口径 | SQL | 执行追溯 | 警告或降级说明
```

问数结果进入同一个聊天历史，聊天 message 扩展为 block 结构：

```ts
type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  mode?: 'knowledge' | 'data_qa'
  blocks?: Array<
    | { type: 'markdown'; content: string }
    | { type: 'data_qa_result'; data: DataQaResult }
  >
}
```

## 3. 技术架构

### 3.1 全链路

```text
用户问题
  → 显式 trigger 判断 data_qa 模式
  → 关键词提取 (jieba TF-IDF + 教育业务自定义词典 + 原 query 兜底)
  → 三路并行召回 (Qdrant 字段召回 / Qdrant 指标召回 / ES 取值召回)
  → 合并元数据上下文 (指标→列补全 / 值→列补全 / 列→表分组 / join 路径推导 / 时间范围解析)
  → LLM 过滤相关表、字段、指标、取值
  → LLM 生成 SQL
  → EXPLAIN 校验 → 失败时 LLM 纠错一次
  → 只读执行 SQL
  → 生成 DataQaResult
  → 聊天回复中渲染图表、表格、SQL、解释
```

### 3.2 核心思想

- MySQL meta 表是元知识主存储（唯一真相源）
- Qdrant 做字段和指标的语义召回（向量相似度匹配）
- ES 做维度字段取值的全文召回（关键词精确匹配）
- LLM 不直接面对全库 66 张表 schema，只面对召回和过滤后的子集（通常 10-15 张相关表）
- SQL 生成后必须校验，失败时最多纠错一次，纠错后仍失败返回降级说明
- SQL 只允许 SELECT，禁止写操作

### 3.3 LangGraph DAG（12 节点）

```text
extract_keywords
  → [recall_column ∥ recall_metric ∥ recall_value]   fan-out 三路并行
  → merge_retrieved_info                              fan-in 合并
  → [filter_table ∥ filter_metric]                    fan-out LLM 精筛
  → add_extra_context                                 fan-in 补充日期/方言/default_filters
  → generate_sql
  → validate_sql
  → correct_sql                                       条件分支，有 error 时触发
  → execute_sql
```

各节点职责：

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| extract_keywords | jieba TF-IDF 分词 + 原 query 兜底 | query | keywords[] |
| recall_column | LLM 扩展关键词 → 逐关键词 Qdrant 向量搜索 → 按 column_id 去重 | keywords | retrieved_columns[] |
| recall_metric | 与 recall_column 对称，搜索 metric_info collection | keywords | retrieved_metrics[] |
| recall_value | LLM 扩展关键词 → 逐关键词 ES 全文搜索 → 按 value_id 去重 | keywords | retrieved_values[] |
| merge_retrieved_info | 指标→列补全 / 值→列补全 / 列→表分组 / 补主外键 / **join 路径推导** / **时间范围解析** | 三路召回结果 | table_infos[] + metric_infos[] |
| filter_table | LLM 精筛相关表和字段 | table_infos | 过滤后 table_infos[] |
| filter_metric | LLM 精筛相关指标 | metric_infos | 过滤后 metric_infos[] |
| add_extra_context | 补充当前日期、数据库方言版本、注入 default_filters | 过滤结果 | 完整上下文 |
| generate_sql | LLM 基于上下文生成 SQL | 完整上下文 | sql |
| validate_sql | EXPLAIN 校验 SQL 合法性 | sql | error \| None |
| correct_sql | LLM 根据错误信息纠错 SQL（仅 error 时触发） | sql + error | corrected_sql |
| execute_sql | 只读执行 SQL，返回结果集 | sql | result_rows[] |

merge_retrieved_info 是与简单星型模型项目差异最大的节点。教育数据是雪花型 + 事件表混合（66 张表），需要：
- 从 `meta_join_info` 查出召回表之间的 join 路径，补充必要的中间表
- 将"本月"/"最近30天"等中文时间表达转成具体日期范围

### 3.4 三路召回机制

每个 recall 节点的执行流程：

1. LLM 对 query 做同义词/近义词扩展，生成额外关键词
2. 合并 jieba 关键词 + LLM 扩展关键词，set 去重
3. 逐个关键词独立搜索（不合并向量，避免语义平均化）
4. 按实体 ID 去重（同一字段可能被多个关键词通过不同路径命中）

字段和指标用 Qdrant 向量搜索（语义匹配），取值用 ES 全文搜索（关键词精确匹配）。取值是具体实体名称（"朝阳校区"、"Python 入门"），用户通常原文引用，全文匹配比向量模糊匹配更准确。

### 3.5 Metric 设计

采用半结构化 metric 定义 + LLM 生成最终 SQL。

metric 定义核心口径（度量列、时间列、默认过滤、可用维度），LLM 负责根据用户问题组合维度、时间范围、过滤、排序。每个指标写一次核心定义，查询时动态组合。

纯自然语言口径的问题：LLM 需要自己判断用哪个度量列、哪个时间列、过滤哪些状态，导致口径漂移。写死完整 SQL 的问题：遇到不同维度、时间范围、排序方式时，需要为每种组合单独写一条 SQL，配置爆炸。

LLM 在 SQL 生成中的边界：

- 负责：从用户问题识别 metric/dimension/time_range/filter/sort/limit → 选择召回候选 → 生成最终 SQL
- 禁止：从全库自由猜表、创造不存在的字段、更改 metric 默认口径、绕过 `meta_join_info` 猜 join

metric 格式示例（同时用于 YAML 配置和 meta_metric_info 表）：

```yaml
- id: paid_revenue
  name: 收入金额
  description: 已支付成功订单的实收金额总和
  alias: [收入, 营收, 实收金额, 支付金额]
  metric_type: sum
  base_table: order
  measure_column: order.paid_amount
  time_column: order.paid_at
  default_filters:
    - field: order.order_status
      op: in
      value: [paid, completed, partial_refunded, refunded]
    - field: order.paid_at
      op: is_not_null
  formula: SUM(order.paid_amount)
  relevant_columns:
    - order.id
    - order.paid_amount
    - order.order_status
    - order.paid_at
    - order_item.cohort_id
    - series_cohort.series_id
    - series_cohort.campus_id
    - org_campus.campus_name
    - series.series_name
  allowed_dimensions: [date, month, campus, series, cohort, channel]
  unit: yuan
```

ratio 类型示例：

```yaml
- id: refund_rate
  name: 退款率
  description: 已审批退款金额占已支付收入金额的比例
  alias: [退款率, 退费率]
  metric_type: ratio
  numerator_metric_id: refund_amount
  denominator_metric_id: paid_revenue
  base_table: order
  time_column: order.paid_at
  formula: refund_amount / paid_revenue
  allowed_dimensions: [date, month, campus, series, cohort]
  unit: percent
```

同一个 metric 覆盖不同维度的查询：

| 用户问题 | metric | dimension | 额外参数 |
|---------|--------|-----------|---------|
| 最近 30 天收入趋势 | paid_revenue | day | time_range=recent_30_days, chart=line |
| 哪个校区收入最高 | paid_revenue | campus | order_by=desc, limit=10, chart=bar |
| 本月总收入 | paid_revenue | - | time_range=current_month, chart=stat |

## 4. 元数据系统

### 4.1 文件和脚本位置

| 资源 | 位置 | 说明 |
|------|------|------|
| YAML 配置 | `data_ge/edu-data/meta/education_meta.yaml` | 元数据定义归属数据侧 |
| meta DDL | `data_ge/edu-data/sql/edu.sql` 末尾 | meta 表与业务表一起建，`init_db.py` 一次建好 |
| 构建脚本 | `education_brain/knowledge/analytics/build_meta.py` | 构建和消费归属后端 |

`edu-data` 负责定义 YAML 和提供数据，`education_brain` 负责构建和消费。

### 4.2 Meta 表

meta 表放在 `edu-data` 同一个 MySQL database 中，表名前缀 `meta_`。

第一版 6 张表：

```text
meta_table_info        描述业务表
meta_column_info       描述字段
meta_metric_info       描述指标
meta_column_metric     字段与指标的关联（支持 metric→columns→tables 反向补全和调试）
meta_join_info         描述表间 join 关系
meta_dimension_info    维度注册表（将 allowed_dimensions 中的名称映射到具体表和列）
```

可选第二批：`meta_value_alias`、`meta_query_example`。

#### `meta_table_info`

| 字段 | 说明 |
|------|------|
| id | 表名，如 `order_item` |
| table_name | 表名 |
| table_role | `fact` / `dim` / `bridge` / `event` |
| description | 表描述 |
| domain | `trade` / `learning` / `marketing` / `service`（用于缩小 LLM context 范围） |

#### `meta_column_info`

| 字段 | 说明 |
|------|------|
| id | `table.column` 格式，如 `order.paid_amount` |
| table_id | 关联 meta_table_info.id |
| column_name | 字段名 |
| physical_type | 来自 dw 真实表（SHOW COLUMNS），不依赖人工配置 |
| column_role | `primary_key` / `foreign_key` / `dimension` / `measure` / `time` / `status` |
| description | 字段描述（人工配置） |
| alias | JSON array，用户可能使用的别名（人工配置），用于 Qdrant 向量化和关键词匹配 |
| examples | JSON array，来自 dw 真实数据（SELECT DISTINCT，最多 10 条），给 LLM 当 few-shot |
| sync_value | 是否同步字段真实取值到 ES |

数据来源的双源设计：物理类型和样例值来自 dw 真实数据库（保证准确），角色/描述/别名来自 YAML 人工配置（业务语义无法自动推导）。

#### `meta_metric_info`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | 列 | 指标 ID，如 `paid_revenue` |
| metric_name | 列 | 指标名称 |
| description | 列 | 指标描述 |
| alias | JSON | 别名数组 |
| metric_type | 列 | `sum` / `count` / `count_distinct` / `ratio` / `avg` |
| formula | 列 | 人类可读公式 |
| base_table | 列 | 主表名 |
| measure_column | 列 | 度量列，如 `order.paid_amount`。ratio 类型为 NULL |
| time_column | 列 | 时间列，如 `order.paid_at` |
| numerator_metric_id | 列 | ratio 类型专用：分子指标 ID，如 `refund_amount`。非 ratio 为 NULL |
| denominator_metric_id | 列 | ratio 类型专用：分母指标 ID，如 `paid_revenue`。非 ratio 为 NULL |
| default_filters | JSON | 默认过滤条件，防止口径漂移 |
| allowed_dimensions | JSON | 可用维度 ID 列表，引用 meta_dimension_info.id |
| relevant_columns | JSON | 相关列列表 |
| sql_expression | 列 | 可选 SQL 表达式片段 |
| unit | 列 | `yuan` / `person` / `percent` / `count` |

ratio 类型指标通过 `numerator_metric_id` / `denominator_metric_id` 引用已有的 sum/count 指标，避免 LLM 自由猜测分子分母口径。例如 `refund_rate` 的分子是 `refund_amount`，分母是 `paid_revenue`，两者都有独立的 metric 定义和 default_filters。

核心字段直接写入表列，扩展字段（default_filters/allowed_dimensions/relevant_columns/alias）用 JSON 列存储。

#### `meta_column_metric`

| 字段 | 说明 |
|------|------|
| column_id | `table.column` 格式，关联 meta_column_info.id |
| metric_id | 关联 meta_metric_info.id |

联合主键 (column_id, metric_id)。从 metric 的 relevant_columns 自动展开写入。用于：
- merge_retrieved_info 节点中的 metric→columns→tables 反向补全
- 调试时快速查看某个字段被哪些指标依赖

#### `meta_dimension_info`

| 字段 | 说明 |
|------|------|
| id | 维度 ID，如 `campus`、`series`、`channel` |
| dimension_name | 维度名称，如"校区"、"课程系列"、"渠道" |
| dimension_type | `column` / `time_derived`。普通业务维度用 `column`，按日/月等时间粒度用 `time_derived` |
| column_id | 维度展示列，如 `org_campus.campus_name`（关联 meta_column_info.id）。`time_derived` 类型可为空 |
| expression_template | `time_derived` 专用表达式模板，如 `DATE_FORMAT({time_column}, '%Y-%m')` |
| grain | `time_derived` 专用粒度，如 `day` / `week` / `month` |
| description | 维度描述 |

将 allowed_dimensions 中的抽象名称映射到具体的表和列。SQL 生成时，LLM 看到 `dimension=campus` 即可查到对应的 `org_campus.campus_name`，结合 `meta_join_info` 确定 join 路径。

#### `meta_join_info`

| 字段 | 说明 |
|------|------|
| left_table | 左表名 |
| left_column | 左表列名 |
| right_table | 右表名 |
| right_column | 右表列名 |
| join_type | `many_to_one` / `one_to_many` / `one_to_one` |
| description | join 关系描述 |

教育数据是雪花型 + 事件表混合（66 张表），多跳 join 路径（如 order → order_item → series_cohort → org_campus，共 3 跳）无法由 LLM 可靠推测，必须显式维护。

### 4.3 YAML 配置结构

```yaml
tables:
  - name: order
    role: fact
    domain: trade
    description: 订单主表
    columns:
      - name: id
        role: primary_key
        description: 订单ID
        alias: [订单ID]
        sync: false
      - name: paid_amount
        role: measure
        description: 订单实付金额
        alias: [实付金额, 收入, 支付金额]
        sync: false
      # ...

dimensions:
  - id: campus
    name: 校区
    type: column
    column_id: org_campus.campus_name
    description: 按校区维度分组
  - id: series
    name: 课程系列
    type: column
    column_id: series.series_name
    description: 按课程系列维度分组
  - id: cohort
    name: 班次
    type: column
    column_id: series_cohort.cohort_name
    description: 按班次维度分组
  - id: channel
    name: 渠道
    type: column
    column_id: dim_channel.channel_name
    description: 按招生渠道维度分组
  - id: date
    name: 日（天）
    type: time_derived
    column_id: null
    grain: day
    expression_template: "DATE({time_column})"
    description: 按天分组
  - id: month
    name: 月
    type: time_derived
    column_id: null
    grain: month
    expression_template: "DATE_FORMAT({time_column}, '%Y-%m')"
    description: 按月分组

joins:
  - left: order_item.order_id
    right: order.id
    type: many_to_one
    description: 订单明细关联订单主表
  - left: order_item.cohort_id
    right: series_cohort.id
    type: many_to_one
    description: 订单明细关联班次
  - left: series_cohort.series_id
    right: series.id
    type: many_to_one
    description: 班次关联课程系列
  - left: series_cohort.campus_id
    right: org_campus.id
    type: many_to_one
    description: 班次关联校区

metrics:
  - id: paid_revenue
    name: 收入金额
    # ... (完整格式见 §3.5)
```

YAML 中 `alias` 字段的两个用途：写入 Qdrant 向量索引（description + alias 拼成文本 → Embedding → 向量，用于语义相似度匹配）；关键词匹配（用户问题中出现别名时直接匹配到对应字段）。

`sync` 字段控制是否将该字段的真实取值同步到 ES。只有 `dimension` 角色且 `sync: true` 的字段进入 ES 全文索引：

| 角色 | 是否进 ES | 原因 |
|------|----------|------|
| primary_key | 否 | ID 值无业务语义 |
| foreign_key | 否 | 只是关联 ID |
| dimension + sync: true | 是 | 用户可能按维度值筛选，如"朝阳校区" |
| dimension + sync: false | 否 | 如 year/month 是数字，全文搜索意义不大 |
| measure | 否 | 金额/数量做模糊匹配没有业务意义 |

适合同步的维度字段：校区名称、课程系列名称、班次名称、渠道名称、课程分类名称、学员身份名称。

### 4.4 三阶段构建流程

构建脚本（`build_meta.py`）读取 YAML 配置 + dw 真实数据，写入三份存储：

```text
education_meta.yaml + dw 数据库
        │
  build_meta.py
        │
  ┌─────┼──────────────┐
  │     │              │
阶段一  阶段二          阶段三
MySQL   Qdrant         ES
  │     │              │
meta_table_info     edu_column_info 集合   维度取值全文索引
meta_column_info    edu_metric_info 集合   (sync=true 的字段)
meta_metric_info    (三路向量化)
meta_column_metric
meta_join_info
meta_dimension_info
```

**阶段一 MySQL**：读 dw 表结构（SHOW COLUMNS 获取物理类型）+ 采样数据（SELECT DISTINCT 获取样例值，最多 10 条）+ YAML 配置（角色/描述/别名），合并后写入 6 张 meta 表。meta_column_metric 从各 metric 的 relevant_columns 自动展开写入。

**阶段二 Qdrant**：取阶段一产出的 column_info 和 metric_info，做三路向量化写入两个 collection（`edu_column_info`、`edu_metric_info`，加 `edu_` 前缀避免与其他项目共用 Qdrant 时冲突）。同一个字段实体从三个角度生成向量 point：

```text
字段 order.paid_amount
  ├── name 路:  "paid_amount"           → 向量 point A (payload = 完整字段信息)
  ├── desc 路:  "订单实付金额"           → 向量 point B (payload = 完整字段信息)
  └── alias 路: "实付金额" / "收入"      → 向量 point C, D (payload = 完整字段信息)
```

用户提问方式不可预测（可能用字段名、描述或别名），每路文本独立生成向量 point，但 payload 都指向同一个字段实体。任意一路命中即可召回完整字段信息。

向量 point ID 使用 `uuid5(NAMESPACE, f"{entity_id}:{source_type}:{text}")`，保证同一实体的同一路向量生成的 ID 总是相同的，脚本重复运行时 Qdrant point 会被覆盖而非新增。构建时先删后建（`recreate_collection`），保证 YAML 配置删除也能生效。

**阶段三 ES**：取 `sync: true` 的维度字段，从 dw 查询全量去重取值（limit=10000 上限保护），为每个取值构建一条 ES 文档。ES 使用 `ik_max_word` 分词器，支持中文全文搜索。

ES 文档结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | keyword | `column_id.value` 格式，天然去重 |
| value | text (ik_max_word) | 字段取值，如"朝阳校区" |
| column_id | keyword | 关联 column_info.id |
| column_name | keyword | 字段名 |
| table_id | keyword | 所属表名 |

## 5. 前后端契约

### 5.1 DataQaResult

```ts
type DataQaResult = {
  queryId: string
  mode: 'data_qa'
  question: string
  answer: string
  intent: {
    analysisType: 'single_metric' | 'trend' | 'ranking' | 'comparison' | 'detail'
    metrics: string[]
    dimensions: string[]
    filters: Array<{ field: string; op: string; value: unknown; label?: string }>
    timeRange?: { start: string; end: string; grain?: 'day' | 'week' | 'month' }
    sort?: Array<{ field: string; direction: 'asc' | 'desc' }>
    limit?: number
  }
  visual: {
    type: 'stat' | 'line' | 'bar' | 'table'
    title: string
    columns: Array<{
      key: string
      label: string
      type: 'string' | 'number' | 'date' | 'percent' | 'currency'
    }>
    rows: Array<Record<string, unknown>>
    x?: string
    y?: string[]
  }
  explain: {
    sql: string
    metrics: Array<{
      id: string
      name: string
      formula: string
      description: string
    }>
    tables: string[]
    columns: string[]
    joins: string[]
    assumptions: string[]
  }
  trace: {
    stages: Array<{ name: string; status: 'ok' | 'error' | 'skipped'; durationMs?: number }>
    rowCount: number
    durationMs: number
  }
  warnings: string[]
  error?: {
    stage: string
    code: string
    message: string
  }
}
```

### 5.2 analysisType 与 visual.type 的对应

| analysisType | 典型问题 | visual.type |
|-------------|---------|-------------|
| single_metric | "本月总收入是多少" | stat |
| trend | "最近 30 天收入趋势" | line |
| ranking | "哪个校区收入最高" | bar |
| comparison | "本周和上周收入对比" | bar / table |
| detail | "列出所有退款订单" | table |

## 6. 第一批指标

### 经营交易

| ID | 名称 | metric_type | 说明 |
|----|------|------------|------|
| paid_revenue | 收入金额 | sum | SUM(order.paid_amount) WHERE order_status IN (paid,completed,partial_refunded,refunded) AND paid_at IS NOT NULL |
| enrollment_count | 报名量 | count | COUNT(student_cohort_rel.id) WHERE enroll_status IN (active,completed)。一个学员报多个班次计多次 |
| enrolled_student_count | 报名学员数 | count_distinct | COUNT(DISTINCT student_cohort_rel.student_id) WHERE enroll_status IN (active,completed)。去重学员人头数 |
| paid_order_count | 支付订单数 | count | COUNT(order.id) WHERE order_status IN (paid,completed,partial_refunded,refunded) AND paid_at IS NOT NULL |
| refund_amount | 退款金额 | sum | SUM(refund_request.approved_amount) WHERE refund_status = 'refunded'。注意：refund_request 表无 refund_amount 字段，使用 approved_amount |
| refund_rate | 退款率 | ratio | numerator=refund_amount, denominator=paid_revenue |
| average_order_value | 客单价 | avg | AVG(order.paid_amount) WHERE order_status IN (paid,completed,partial_refunded,refunded) |
| consultation_to_enrollment_rate | 咨询转化率 | ratio | numerator=已报名咨询用户数, denominator=总咨询用户数（JOIN consultation_record + student_cohort_rel） |

### 教学学习

| ID | 名称 | metric_type |
|----|------|------------|
| attendance_rate | 出勤率 | ratio |
| video_completion_rate | 视频完播率 | ratio |
| homework_submit_rate | 作业提交率 | ratio |
| exam_submit_rate | 考试提交率 | ratio |

### 服务

| ID | 名称 | metric_type |
|----|------|------------|
| ticket_count | 工单数 | count |
| ticket_close_rate | 工单关闭率 | ratio |

## 7. 验收问题样例

1. 本月报名人数是多少？
2. 最近 30 天收入趋势如何？
3. 哪个校区报名人数最多？
4. 按课程系列统计收入 Top 10。
5. 哪个课程系列退款率最高？
6. 最近三个月退款金额趋势如何？
7. 各渠道的报名人数和收入是多少？
8. 某班次的出勤率是多少？
9. 哪些课程的视频完播率最高？
10. 最近 30 天工单数量和关闭率如何？

## 8. 实施阶段

### Phase 1：元数据系统

先把元数据基础一次性建完整：全量业务表物理字段 + 当前设计范围内的指标 + 必要 join / dimension 配置都进入 YAML 和 meta 表。随后仍用 `paid_revenue` 做端到端验收，确认 meta → 召回链路通畅后再进入 pipeline 开发。

1. 设计 `education_meta.yaml`：覆盖 `edu-data` 中问数需要的业务表、字段、join、dimension 和当前设计范围内的 metrics。字段、表、枚举、约束和中文释义的初稿以 `data_ge/edu-data/README.md` 的结构化提取为主，降低人工整理成本；真实 MySQL / `data_ge/edu-data/sql/edu.sql` 用于验证字段存在、类型一致性、外键关系和缺漏项，不作为人工整理入口。role / description / alias 在 YAML 中人工补充或校正
2. 在 `edu.sql` 中添加 meta 表 DDL
3. 实现 `education_brain/knowledge/analytics/build_meta.py`（三阶段构建：MySQL 6 张 meta 表 → Qdrant 2 个 collection → ES 取值索引）
4. **验收**：meta 表包含全量配置范围内的表字段、当前设计范围内的 metrics、join 和 dimensions；用"收入"关键词搜索 Qdrant `edu_metric_info`，确认能召回 `paid_revenue` 指标和 `order.paid_amount` 字段；用一个真实校区/课程名搜索 ES，确认能召回对应维度字段
5. 验证通过后进入问数 pipeline，不在 Phase 2 再补基础元数据

### Phase 2：问数 Pipeline

实现 12 节点 LangGraph DAG（§3.3），重点关注 merge_retrieved_info 节点中的 join 路径推导和时间表达式解析。

### Phase 3：聊天接入

1. 前端新增显式"数据问数"开关
2. 后端聊天接口支持 `mode=data_qa`
3. 问数结果写入同一聊天历史
4. 回复支持 `data_qa_result` block

### Phase 4：真实图表

1. `stat` 指标卡
2. `line` 趋势图
3. `bar` 排名图
4. `table` 明细表
5. SQL / 口径 / trace 折叠面板

## 9. 外部依赖与环境

问数环境优先参考本机已有目录：

```text
/home/ccr/local-docker/nl2sql-env
```

该目录已经包含 MySQL、Elasticsearch + IK、Kibana、Qdrant、TEI embedding 服务和本地 `bge-large-zh-v1.5` 模型。当前教育问数可以复用这个环境形态；后续如需独立隔离，可复制为 `education-nl2sql-env` 并调整容器名、volume 和 MySQL 初始化 SQL。

| 组件 | 版本要求 | 用途 | 备注 |
|------|---------|------|------|
| MySQL 8.0+ | 必须 | 业务数据 + meta 表 | `edu-data` 已有，问数系统使用只读账号连接 |
| Qdrant v1.16 | 必须 | 字段和指标的语义向量召回 | `/home/ccr/local-docker/nl2sql-env` 暴露 HTTP `6333`、gRPC `6334`；两个 collection：`edu_column_info`、`edu_metric_info` |
| Elasticsearch 8.19.10 | 必须 | 维度字段取值全文召回 | `/home/ccr/local-docker/nl2sql-env/elasticsearch/Dockerfile` 已安装 `elasticsearch-analysis-ik-8.19.10.zip`。若环境暂无 IK，可先用 `standard` analyzer 降级，但中文召回质量会下降 |
| Embedding 服务 | 必须 | 向量化文本 | 参考 `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`，端口 `8081`，本地模型 `/home/ccr/local-docker/nl2sql-env/embedding/bge-large-zh-v1.5`；`cpu-1.8` 在当前 WSL 环境真实 `/embed` 会触发 TEI 内部 queue panic |
| LLM | 必须 | 关键词扩展、表/指标过滤、SQL 生成、SQL 纠错 | DeepSeek / OpenAI 兼容接口 |
| jieba | 必须 | 中文分词和关键词提取 | 需加载教育业务自定义词典 |

ES IK 插件安装：

```bash
# Docker 方式
elasticsearch-plugin install https://get.infini.cloud/elasticsearch/analysis-ik/8.x.x

# 或在 Dockerfile 中
RUN elasticsearch-plugin install analysis-ik
```

## 10. SQL 安全边界

| 规则 | 说明 |
|------|------|
| SELECT-only | 只允许 SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE |
| 禁止多语句 | 禁止分号分隔的多条 SQL，防止注入 |
| 禁止注释绕过 | 过滤 `--`、`/* */`、`#` 等 SQL 注释语法 |
| 默认 LIMIT | 未指定 LIMIT 时自动追加 `LIMIT 1000`，防止全表扫描 |
| 查询超时 | 执行时设置 `MAX_EXECUTION_TIME`（建议 30 秒），超时自动终止 |
| 只读账号 | 问数系统使用独立的 MySQL 只读账号连接业务数据库，数据库层面兜底 |
| EXPLAIN 前置 | SQL 生成后先执行 EXPLAIN，失败则不执行，进入纠错流程 |
| 纠错上限 | EXPLAIN 失败后 LLM 纠错最多一次，纠错后仍失败则返回降级说明，不执行 |
