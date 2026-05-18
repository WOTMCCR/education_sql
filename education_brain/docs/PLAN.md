# 教育知识库整体计划

> 状态：总体路线图 / 架构设计文档
>
> 本文档用于说明项目整体目标、数据特点和长期实现路线；当前前后端联调的接口细节请以 `docs/api-reference.md` 为准。

## 1. 目标

这个项目的目标不是先做一个"通用 RAG 框架"，而是围绕当前真实数据，做一个面向教育场景的知识库系统，稳定支持四类能力：

- 课程介绍与课程详情查询
- 题库与题目检索
- 课程文档与项目文档检索
- 基于知识库内容的引用式问答

**为什么不做通用 RAG 框架：** 通用 RAG 框架的设计起点是"任意文档进来都能切块向量化再检索"，但当前数据天然分成四种形态，处理策略完全不同。如果强行走统一链路，课程目录和题库这类强结构化数据会丢失字段语义（比如"适合人群""题型"这些字段被切成无意义的文本碎片），而文档类数据又需要分块、向量化、重排序这些结构化数据不需要的步骤。通用框架会在两个方向上同时做得不好。

**当前数据分为四类：**

| 数据源 | 文件 | 规模 | 特征 | 处理策略 |
|--------|------|------|------|----------|
| 课程目录 | `data/数据/课程介绍.md` | 219 个系列，657 个模块，4602 行 | 强结构化，字段固定，层级稳定 | 确定性解析，直接落库 |
| 题库 | `data/数据/题目资料.md` | 73 个题库，1752 道题，17582 行 | 强结构化，但存在题型扩展和少量脏数据 | 确定性解析 + 质量标记 |
| 课程文档 | `data/数据/课程文档/*.docx` | 16 个文件，152 MB | 长文本、代码、表格、图片、嵌入对象 | .docx → .md 转换 → 统一 Markdown 解析 → 分块 → 向量化 |
| 项目文档 | `data/数据/项目文档/*.docx\|*.md` | 2 个 .docx + 19 个 .md，86 MB | 系统设计/实现型，大量图片引用和流程说明 | 同课程文档链路（.docx 先转 .md），标记 `doc_type=project_doc` |

所以系统设计围绕"结构化数据 + 文档知识 + 向量检索"三层展开，而不是把所有内容一股脑切块向量化。

## 2. 数据现状与设计约束

在做架构决策之前，需要先理解数据本身的特点和限制，因为这些直接决定了导入链路和查询链路的设计。

### 2.1 课程目录的结构

`课程介绍.md` 格式高度稳定：`## 系列标题` 开始一个系列，下方是固定字段（系列编码、描述、课程分类、适合人群、学习目标、适合年级），`### 课程` 下列出该系列的所有模块（模块名、编码、课时、学时、描述）。

这种数据不需要 LLM 理解，不需要向量化，用正则或行扫描就能 100% 准确地提取。如果强行向量化，"适合人群: 在校生, 职场人, 求职者"这种字段会被切成无意义的文本片段，反而损害检索精度。

### 2.2 题库的复杂性

`题目资料.md` 主体结构稳定（`## 题库名` → `### 题目编码` → 题型/题干/选项/答案/解析），但存在以下真实问题：

- **题型多样**：不只有单选、多选、判断，还有简答、编程、阅读理解、材料分析、案例分析、情境分析、计算题。
- **字段语义漂移**：材料分析题和案例分析题的"答案"字段实际是"作答要求"而非标准答案，需要区分 `answer_key`（标准答案）和 `reference_answer`（参考回答）。
- **少量脏数据**：空白选项（C/D 只有标签没有内容）、混合答案分隔符（`A、B、C` vs `A,B,C` vs `ABC`）、异常标点。

这要求解析器不能是简单的正则匹配，而是要有质量检测机制（`quality_flags`），把异常标记出来但不阻断导入。

### 2.3 课程文档的挑战与转换策略

16 个 `.docx` 文件体量差异很大（从 1200 行到 98000 行），包含：

- 多级标题层级（Heading 1-4）
- 代码块（Python、SQL、Shell，但 .docx 中没有原生代码块标记，通常靠字体或缩进区分）
- 内嵌表格
- 内嵌图片和 OLE 对象
- 超链接

**采用 "docx → Markdown 转换" 策略而非直接解析 .docx：**

如果直接用 `python-docx` 解析，代码块识别需要启发式规则（等宽字体检测、缩进模式识别），样式丢失严重时甚至需要降级到 OOXML 级解析，链路复杂且脆弱。更好的做法是先用成熟的转换工具将 `.docx` 转为 `.md`，然后统一走 Markdown 解析链路。

**转换工具选型：**

| 工具 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| `markitdown`（微软开源） | Python 原生，API 调用简单，支持 .docx/.pptx/.xlsx 等多格式，内置图片提取 | 复杂表格和嵌套列表的转换质量依赖文档样式 | 首选方案，纯 Python 集成无外部依赖 |
| `pandoc` | 转换质量最高，社区成熟，格式支持最广 | 需要系统级安装（非 Python 包），调用方式为子进程 | 备选方案，适合 markitdown 效果不理想时降级 |
| `docling`（IBM 开源） | 基于 AI 的文档理解，对复杂版式支持好 | 依赖重（需要模型推理），速度慢，首版不需要 | 后续如果遇到版式极复杂的文档再考虑 |

**首版方案：markitdown 为主，pandoc 为降级备选。**

转换后的 `.md` 文件与项目文档中的原生 `.md` 文件走完全相同的解析链路，大幅简化了分块逻辑——标题层级变成 `#`/`##`/`###`，代码块变成标准的 `` ``` `` 围栏，表格变成 Markdown 表格语法，不再需要启发式格式识别。

**转换过程中的图片处理：** markitdown/pandoc 在转换时可将 .docx 内嵌图片导出到指定目录，并在 Markdown 中生成 `![](images/xxx.png)` 引用。导出的图片在分块阶段上传 MinIO，Markdown 中的图片引用路径替换为 MinIO URL。

**转换质量的已知局限：**
- 复杂嵌套表格可能转换为不完美的 Markdown 表格（合并单元格会丢失）
- OLE 嵌入对象（如嵌入的 Excel 图表）无法转换，会被跳过
- 极少数样式驱动的语义信息（如"红色标注的重点"）会丢失

这些局限对教育文档（以文本+代码+简单表格为主）影响很小。如果个别文件转换效果不理想，可以单独用 pandoc 重试或人工修正转换后的 `.md` 文件。

### 2.4 文档与课程目录的映射缺失

**这是一个关键的数据治理问题。** 课程目录中的模块编码是 `general_purpose_programming_foundation_m1` 这样的 ID，而课程文档的文件名是 `尚硅谷大模型技术之Python1.0.docx` 这样的自然语言。两套命名体系之间没有天然主键。

解决方案是引入显式映射表 `source_mapping`：
- 默认通过规则匹配建立初始映射（如从文件名中提取关键词，匹配课程系列的描述或分类路径）
- 允许人工补录和覆盖
- 查询时，如果一个文档 chunk 命中了，可以通过映射表找到它属于哪个课程系列和模块，从而在返回结果中带上课程归属信息

不依赖文件名硬推断所有归属。首版接受"规则映射 + 人工补充"的治理方式。

## 3. 核心架构

整体架构分成五层，每层有明确的职责边界：

### 3.1 接入层（FastAPI）

**职责：** HTTP 协议适配、请求校验、认证（预留）、路由分发。

**为什么用 FastAPI：** 当前系统需要同步接口（导入状态查询、结构化搜索）和异步接口（文档导入、流式问答），FastAPI 原生支持 `async/await`、`BackgroundTasks`、SSE（Server-Sent Events），不需要额外引入消息队列。Pydantic v2 与 FastAPI 深度集成，请求/响应模型可以复用 schema 定义。

**接口按能力边界拆分，不做大一统入口：**

| 端点 | 方法 | 职责 |
|------|------|------|
| `/ingest/catalog` | POST | 导入课程目录 |
| `/ingest/questions` | POST | 导入题库 |
| `/ingest/documents` | POST | 导入课程/项目文档 |
| `/ingest/tasks/{task_id}` | GET | 查询导入任务状态 |
| `/search/courses` | GET | 课程介绍与详情查询 |
| `/search/questions` | GET | 题目检索 |
| `/search/documents` | GET | 文档片段检索 |
| `/chat/query` | POST | 统一问答入口（内部做意图路由） |
| `/chat/stream/{task_id}` | GET | SSE 流式输出端点 |
| `/chat/history/{session_id}` | GET | 历史会话查询 |
| `/health` | GET | 服务健康检查 |

**为什么导入接口按数据类型拆分而不是一个统一 `/ingest`：** 三类数据的导入参数完全不同——课程目录只需要文件路径，题库需要文件路径 + 质量检查选项，文档需要文件路径 + 文档类型 + 可选的映射信息。统一入口会导致参数混乱和校验复杂化。

**导入侧用轮询，查询侧用 SSE：** 导入流程耗时几十秒到几分钟，客户端轮询 `/ingest/tasks/{task_id}` 间隔 1.5 秒足够。查询流程中 LLM 需要逐字输出（几十毫秒一个 token），轮询无法满足实时性要求，必须用 SSE 长连接。两种场景的延迟特征不同，不强行统一。

### 3.2 编排层（LangGraph）

**职责：** 管理导入和查询两条流程的节点编排、状态传递、条件路由和错误处理。

**为什么用 LangGraph 而不是纯函数调用链：**

- **导入流程**需要按数据类型做条件分支（课程目录走确定性解析，文档走分块+向量化），LangGraph 的 `StateGraph` 天然支持条件路由，比 if-else 链更容易可视化和调试。
- **查询流程**需要并行执行多路检索（向量检索 + HyDE 检索）再合并结果，LangGraph 的 fan-out/fan-in 模式比手写 `asyncio.gather` 或 `ThreadPoolExecutor` 更声明式，状态管理更清晰。
- 两条流程共享同一套 `BaseNode` 抽象（`__call__` → `process()`），LangGraph 无差别调用，导入节点和查询节点写法一致。

**放弃的替代方案：**

- **Celery / RQ**：引入消息队列和 Worker 进程，首版数据量（16 个 .docx + 2 个 .md 结构化文件）不需要分布式调度，增加部署复杂度但没有收益。当数据量增长到需要多 Worker 并行处理时再考虑。
- **Prefect / Airflow**：面向数据工程的编排工具，调度粒度是"作业"而非"请求"，不适合在线查询场景。
- **纯 async 函数链**：能工作，但状态传递靠函数参数层层透传，调试时难以观察中间状态，也无法做到"查询管线跑到一半可以看到哪个节点在执行"。

**拆成两条流程图：**

- **导入流程（Import Pipeline）**：接收文件路径 → 按类型分流 → 解析 → 存储 → 向量化（仅文档类） → 入 Milvus → 更新任务状态
- **查询流程（Query Pipeline）**：接收用户问题 → 意图分流 → 结构化查询或多路向量检索 → 融合排序 → Rerank → 答案生成 → 保存历史

### 3.3 存储层（MongoDB + Milvus + MinIO）

存储层是整个系统的核心，三个组件各有明确角色，下文 §4 专门展开。

### 3.4 解析与检索层

**职责：** Markdown/Docx 解析、分块、Embedding 生成、混合检索、HyDE 检索、Rerank。

这一层是系统中"脏活最多"的地方，因为它直接面对真实数据的不规则性。

**解析策略按数据类型区分：**

| 数据类型 | 解析器 | 策略 |
|----------|--------|------|
| 课程目录 `.md` | 确定性行扫描 | 逐行读取，用 `##` / `###` / `- **字段**:` 模式匹配提取 |
| 题库 `.md` | 确定性块解析 | 以 `## 题库` 和 `### question_code` 为边界切块，每块内提取固定字段 |
| 课程/项目 `.docx` | markitdown 转换 + Markdown 解析 | .docx → .md 转换（图片导出到临时目录）→ 走统一 Markdown 解析链路 |
| 课程/项目 `.md` | Markdown 标题层级解析 | 按标题层级、代码块、表格、图片引用分块，保留 `section_path`（.docx 转换后的 .md 也走此链路） |

**分块策略（仅文档类数据）：**

分块不是简单的按固定字符数切割。教育文档有明显的章节结构，分块应该尊重这个结构：
- 首选按标题层级分块（一个 Heading 2 或 Heading 3 下的内容作为一个 chunk）
- 如果单个章节过长（超过 `max_content_length`，默认 2000 字符），在段落边界处二次拆分
- 相邻短段落合并（低于 `min_content_length`，默认 500 字符时向后合并）
- 每个 chunk 保留 `section_path`（如 `["第3章 深度学习基础", "3.2 反向传播", "3.2.1 链式法则"]`），因为真实查询经常落到"某章节某小节"
- 代码块和表格作为完整单元保留，不在中间切断

**Embedding 模型选择 BGE-M3 的原因：**

| 需求 | BGE-M3 的适配性 |
|------|-----------------|
| 中英混合内容（Python 课程中代码和中文解释交替） | 原生多语言支持 |
| 代码片段的语义理解 | 训练数据包含代码 |
| 稠密+稀疏混合检索 | 同时输出 dense embedding 和 sparse embedding |
| 本地部署 | 支持 GPU 本地推理，不依赖外部 API |

BGE-M3 同时生成稠密向量（语义相似度）和稀疏向量（关键词匹配），这对教育场景很重要——学生问"Python 怎么连接 MySQL"时，"Python"和"MySQL"是精确关键词（稀疏向量擅长），而"连接"的语义（可能是 `pymysql.connect`、数据库驱动配置等）需要稠密向量捕捉。

**Rerank 模型选择 BGE-Reranker 的原因：** 向量检索是双塔模型（query 和 doc 独立编码再算相似度），精度有上限。Reranker 是交叉编码器（query 和 doc 拼接后一起编码），精度更高但速度慢。用向量检索做粗筛（Top 10-20），再用 Reranker 精排（保留 Top 3-5），是精度和延迟的最佳平衡。

### 3.5 应用层

**职责：** 封装面向用户的四类能力，每类能力有独立的 service 模块。

| 能力 | Service | 主查询路径 | 备注 |
|------|---------|-----------|------|
| 课程查询 | `course_search_service` | MongoDB 结构化查询 | 支持按名称、分类、人群、目标过滤 |
| 题库查询 | `question_search_service` | MongoDB 结构化查询 | 支持按题库、题型、关键词过滤 |
| 文档查询 | `document_search_service` | Milvus 向量检索 + MongoDB 回表 | 返回带来源信息的文档片段 |
| 知识问答 | `query_service` | LangGraph 查询管线 | 意图路由 → 多路检索 → 答案生成 |

**为什么课程查询和题库查询不走向量检索：** 这两类数据已经有完善的结构化字段（课程分类、适合人群、题型、题库编码等），结构化查询的精度是 100%——用户搜"Python 相关课程"，用 `category_path` 包含 "Python" 的条件查就行，不需要语义理解。向量检索反而会引入噪音（比如把"Python 连接 MySQL"的文档 chunk 也召回来）。

## 4. 存储层设计

### 4.1 MongoDB — 业务真相（Source of Truth）

**角色：** 所有业务数据的权威存储。如果 Milvus 挂了，MongoDB 里的数据仍然是完整的、可恢复的。

**为什么选 MongoDB 而不是 PostgreSQL：**

当前项目的数据模型不是传统的关系型结构：
- 课程系列的 `audience`（适合人群）和 `goal_tags`（学习目标）是变长数组，在关系数据库中需要多值字段或关联表
- 题目的 `options` 是嵌套结构（每个选项有 label 和 content），在 MongoDB 中天然是嵌入文档
- 文档 chunk 的 `section_path` 是变长数组，`image_refs` / `code_refs` / `table_refs` 也是
- 任务状态的 `progress_logs` 是追加式数组，每条日志有时间戳和消息
- 首版没有复杂的联表查询、事务要求或 ACID 强一致性需求

MongoDB 的文档模型天然匹配这些数据形态，不需要 ORM 做对象-关系映射。

**放弃 PostgreSQL 的具体原因：** PostgreSQL 能做所有这些事（JSONB 字段、数组类型、pgvector 扩展），但首版的数据量和查询模式不需要关系数据库的核心优势（事务、联表、约束），引入 PostgreSQL 会增加 schema migration 管理、ORM 选择等不必要的复杂度。如果后续需要强事务场景（如权限审批、财务结算），可以在那时引入关系数据库。

**MongoDB 中的 Collection 划分：**

| Collection | 数据来源 | 写入频率 | 查询频率 |
|------------|---------|---------|---------|
| `course_series` | 课程介绍.md | 低（批量导入） | 高（课程查询） |
| `course_module` | 课程介绍.md | 低 | 高 |
| `question_bank` | 题目资料.md | 低 | 中 |
| `question_item` | 题目资料.md | 低 | 高 |
| `knowledge_document` | .docx / .md 文件元数据 | 低 | 中 |
| `knowledge_chunk` | 文档分块结果 | 低 | 高（向量检索回表） |
| `source_mapping` | 人工+规则映射 | 极低 | 中（检索结果补充来源信息） |
| `asset_object` | MinIO 图片元数据 | 低 | 低 |
| `ingest_task` | 导入任务状态 | 中（任务进行时频繁更新） | 低 |
| `chat_history` | 问答历史记录 | 中 | 中（多轮对话需要读取历史） |

**MongoDB 故障影响范围：**

MongoDB 是整个系统的业务主数据库，如果它不可用：
- **课程查询、题库查询完全不可用**（数据只存在 MongoDB 中）
- **文档检索降级**（Milvus 能返回向量匹配结果，但无法回表获取完整 chunk 文本和来源信息，检索结果不完整）
- **导入完全不可用**（任务状态和解析结果都写不进去）
- **问答部分不可用**（历史会话丢失，但如果 Milvus 可用，仍能做单轮问答，只是没有来源追溯）

**恢复策略：** MongoDB 本身支持副本集（replica set），生产环境应至少部署 3 节点副本集。首版开发环境单节点即可，但导入完成后应做一次 `mongodump` 备份。

### 4.2 Milvus — 向量检索副本

**角色：** 文档 chunk 的向量检索索引。它不存储业务真相，只存储检索所需的向量和必要的过滤字段。

**为什么需要独立的向量数据库而不是在 MongoDB 里做向量检索：**

MongoDB Atlas 支持向量搜索，但有两个问题：
- 自建 MongoDB 社区版不包含向量搜索功能
- 向量检索需要专门的索引结构（HNSW / IVF_FLAT），这些索引的构建和查询性能在专用向量数据库中更优

Milvus 的核心价值在于：
- 支持 BGE-M3 输出的稠密+稀疏混合检索（`WeightedRanker` 将两路结果融合）
- 支持 `scalar` 过滤（如 `doc_type == "course_doc"`）与向量检索组合，避免先全量召回再后过滤
- 内存索引 + 磁盘持久化，查询延迟在毫秒级

**Milvus 中只存储检索副本，不存储完整业务数据：**

| 字段 | 类型 | 用途 |
|------|------|------|
| `chunk_id` | VARCHAR | 主键，关联 MongoDB `knowledge_chunk._id` |
| `doc_id` | VARCHAR | 所属文档 ID，用于过滤 |
| `doc_type` | VARCHAR | `course_doc` / `project_doc`，用于过滤 |
| `dense_vector` | FLOAT_VECTOR(1024) | BGE-M3 稠密向量 |
| `sparse_vector` | SPARSE_FLOAT_VECTOR | BGE-M3 稀疏向量 |

检索流程：Milvus 返回 `chunk_id` 列表 → 用 `chunk_id` 回 MongoDB `knowledge_chunk` 表取完整文本和元数据。

**为什么不把完整文本也存到 Milvus：** Milvus 的存储成本和查询效率都针对向量数据优化，存大段文本会浪费内存且增加传输开销。MongoDB 对文本字段的查询更灵活（支持全文索引、正则匹配、投影等）。

**Milvus 故障影响范围：**

- **文档检索不可用**（无法做向量检索）
- **知识问答降级**（多路检索中的向量检索和 HyDE 检索都失败，但如果意图分流到课程/题库查询，这些走 MongoDB 结构化查询的链路不受影响）
- **课程查询、题库查询不受影响**（不依赖 Milvus）
- **导入流程部分降级**（文档解析和 MongoDB 写入可以完成，但向量入库步骤失败，需要等 Milvus 恢复后重新执行向量化步骤）

**恢复策略：** Milvus 的数据是 MongoDB 的"衍生物"——只要 MongoDB 中的 `knowledge_chunk` 完整，就能重新生成向量并导入 Milvus。这也是为什么 MongoDB 是 Source of Truth 而 Milvus 只是检索副本。

### 4.3 MinIO — 对象存储

**角色：** 存储文档解析过程中提取的图片文件，以及后续可能出现的原始文件副本或处理中间产物。

**为什么不把图片存到 MongoDB GridFS：**

- GridFS 将文件切成 255KB 的 chunk 存到两个 collection 中，读取时需要重组，不适合直接通过 URL 提供给前端展示
- MinIO 兼容 S3 协议，图片可以直接通过 HTTP URL 访问，前端 `<img src="...">` 即可展示
- 如果后续要做图片 OCR 或多模态理解，MinIO 中的图片可以直接被图像处理服务读取，不需要从数据库导出

**MinIO 存储的对象：**

| 对象类型 | Bucket | 命名规则 | 来源 |
|----------|--------|---------|------|
| 文档内嵌图片 | `education-knowledge` | `documents/{doc_id}/images/{image_name}` | .docx 解析时提取 |
| 后续扩展：原始文件副本 | `education-knowledge` | `raw/{source_type}/{filename}` | 预留 |

**MongoDB 中只保存图片的元数据引用，不保存图片本身：**

```
asset_object: {
    object_key: "documents/doc_123/images/fig1.png",
    bucket: "education-knowledge",
    content_type: "image/png",
    width: 800,
    height: 600,
    source_doc_id: "doc_123",
    source_chunk_id: "chunk_456"
}
```

这样后续如果要做图片预览、OCR、多模态增强，不需要重构存储层。

**MinIO 故障影响范围：**

- **图片无法显示**（前端引用的图片 URL 不可用，但文本内容检索完全正常）
- **文档导入中的图片上传步骤失败**（但文本解析和分块不受影响，可以标记图片上传失败，等 MinIO 恢复后补传）
- **课程查询、题库查询、文本检索、问答全部不受影响**

MinIO 是三个存储组件中影响范围最小的，因为首版的核心能力都是文本驱动的，图片只是辅助。

### 4.4 三组件边界总结

```
┌────────────────────────────────────────────────────┐
│                    MongoDB                          │
│  业务真相：所有结构化数据 + 文档元数据 + chunk 全文    │
│  + 任务状态 + 历史会话 + 来源映射 + 图片元数据引用     │
│                                                     │
│  如果只剩一个组件可用，系统仍能提供：                   │
│  课程查询 ✓  题库查询 ✓  文本浏览 ✓                   │
│  向量检索 ✗  图片展示 ✗                               │
└──────────────────────┬─────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
┌────────┴────────┐      ┌──────────┴──────────┐
│     Milvus       │      │       MinIO          │
│  检索副本：       │      │  对象存储：            │
│  chunk 的向量索引 │      │  图片文件              │
│                  │      │                       │
│  数据可从         │      │  数据在导入时生成，      │
│  MongoDB 重建    │      │  图片丢失不影响文本检索  │
└─────────────────┘      └───────────────────────┘
```

**关键原则：数据流向是 MongoDB → Milvus / MinIO，而不是反过来。** Milvus 和 MinIO 的数据都可以从 MongoDB 重建，但反过来不行。这意味着在备份策略上，MongoDB 是最高优先级。

## 5. 数据对象设计

系统中有以下核心对象，按职责和来源分组：

### 5.1 课程领域

**`course_series`** — 课程系列

来自 `课程介绍.md` 的 `## 系列标题` 级别。每个系列是一个完整的培训方向。

| 字段 | 类型 | 说明 |
|------|------|------|
| `series_code` | string | 唯一编码，如 `general_purpose_programming_foundation` |
| `title` | string | 系列名称，如"通用编程入门班" |
| `description` | string | 描述路径，如"计算机科学能力线 / 通用程序设计 / 通用编程入门班" |
| `category_path` | string | 课程分类，如"计算机 / 编程语言 / 通用程序设计" |
| `audience` | string[] | 适合人群，如 `["在校生", "职场人", "求职者"]` |
| `goal_tags` | string[] | 学习目标，如 `["技能提升", "求职上岸"]` |
| `grade_tags` | string[] | 适合年级，如 `["专科", "本科"]` |

**`course_module`** — 课程模块

来自 `### 课程` 下的列表项。每个模块是一个可独立排课的单元。

| 字段 | 类型 | 说明 |
|------|------|------|
| `module_code` | string | 唯一编码，如 `general_purpose_programming_foundation_m1` |
| `series_code` | string | 所属系列编码（外键） |
| `module_title` | string | 模块名称，如"语法基础与开发环境" |
| `lesson_count` | int | 课时数 |
| `study_hours` | float | 学时 |
| `module_desc` | string | 模块描述 |
| `sort_order` | int | 在系列内的排序（从 `_m1` 后缀推断） |

### 5.2 题库领域

**`question_bank`** — 题库

来自 `题目资料.md` 的 `## 题库名` 级别。

| 字段 | 类型 | 说明 |
|------|------|------|
| `bank_code` | string | 唯一编码，如 `general_purpose_programming_bank` |
| `bank_name` | string | 题库名称，如"通用程序设计题库" |
| `domain_tags` | string[] | 领域标签（从题库名推断） |
| `question_count` | int | 题目总数 |

**`question_item`** — 题目

来自 `### question_code` 级别。

| 字段 | 类型 | 说明 |
|------|------|------|
| `question_code` | string | 唯一编码，如 `general_purpose_programming_bank_q001` |
| `bank_code` | string | 所属题库编码 |
| `question_type` | string | 题型：单选题/多选题/判断题/简答题/编程题等 |
| `stem` | string | 题干 |
| `options` | object[] | 选项列表，如 `[{"label": "A", "content": "..."}]` |
| `answer_key` | string | 标准答案（单选/多选/判断） |
| `reference_answer` | string | 参考回答（简答/材料分析等开放题型） |
| `analysis` | string | 解析 |
| `raw_block` | string | 原始 Markdown 文本块（保底，用于无法结构化解析时的回退展示） |
| `quality_flags` | string[] | 质量标记，如 `["empty_option_C", "mixed_answer_separator"]` |

**为什么保留 `raw_block`：** 题目解析不可能 100% 覆盖所有变体格式。当结构化字段提取失败或存疑时，`raw_block` 提供原始文本作为回退——至少能把原始题目展示给用户，不会丢数据。

**为什么区分 `answer_key` 和 `reference_answer`：** 数据中材料分析题、案例分析题的"答案"字段实际含义是"作答要求"或"参考回答"，如果统一用一个 `answer` 字段，会误导前端展示和题目评判逻辑。分开存储让下游消费方自行判断如何使用。

### 5.3 文档领域

**`knowledge_document`** — 文档元数据

每个导入的 .docx 或 .md 文件对应一条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | string | 唯一 ID |
| `doc_type` | string | `course_doc` / `project_doc` |
| `source_path` | string | 原始文件路径 |
| `source_file` | string | 文件名 |
| `title` | string | 从文件名或首标题提取的文档标题 |
| `domain_tags` | string[] | 领域标签 |
| `chunk_count` | int | 分块总数 |
| `image_count` | int | 提取的图片总数 |
| `ingest_task_id` | string | 导入该文档的任务 ID |

**`knowledge_chunk`** — 文档分块

文档分块后的结果，是向量检索的最小粒度。

| 字段 | 类型 | 说明 |
|------|------|------|
| `chunk_id` | string | 唯一 ID |
| `doc_id` | string | 所属文档 ID |
| `section_path` | string[] | 章节路径，如 `["第3章", "3.2 反向传播"]` |
| `chunk_text` | string | chunk 正文 |
| `chunk_kind` | string | `text` / `code` / `table` / `mixed` |
| `chunk_index` | int | 在文档内的顺序号 |
| `image_refs` | string[] | 引用的图片 `object_key` 列表 |
| `code_refs` | object[] | 代码块引用 |
| `table_refs` | object[] | 表格引用 |

### 5.4 映射与运维

**`source_mapping`** — 来源映射表

解决"文档与课程目录命名体系不同"的问题。

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_file` | string | 原始文件名 |
| `doc_id` | string | 文档 ID（可选，文档级映射） |
| `bank_code` | string | 题库编码（可选，题库级映射） |
| `series_code` | string | 映射到的课程系列 |
| `module_code` | string | 映射到的课程模块（可选，粒度更细） |
| `project_name` | string | 项目名称（项目文档用） |
| `mapping_type` | string | `rule` / `manual`（标记映射来源） |

**`asset_object`** — 图片资产元数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `object_key` | string | MinIO 中的对象路径 |
| `bucket` | string | Bucket 名称 |
| `content_type` | string | MIME 类型 |
| `width` / `height` | int | 图片尺寸 |
| `source_doc_id` | string | 来源文档 ID |
| `source_chunk_id` | string | 关联的 chunk ID |

**`ingest_task`** — 导入任务

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 唯一任务 ID |
| `task_type` | string | `catalog` / `questions` / `documents` |
| `status` | string | `pending` / `running` / `partial_success` / `completed` / `failed` |
| `sub_tasks` | object[] | 子任务列表（文档导入时，每个文件一个子任务） |
| `progress_logs` | object[] | 进度日志（时间戳 + 消息） |
| `created_at` / `updated_at` | datetime | 时间戳 |

**`chat_history`** — 会话历史

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID（多轮对话共享） |
| `task_id` | string | 单次查询任务 ID |
| `role` | string | `user` / `assistant` |
| `content` | string | 消息内容 |
| `citations` | object[] | 引用的 chunk/题目/课程信息 |
| `intent` | string | 意图分类结果 |
| `created_at` | datetime | 时间戳 |

**`session_id` 与 `task_id` 分离的原因：** `session_id` 标识一个会话（浏览器 tab 维度，前端生成存 localStorage），同一会话内的多轮对话共享。`task_id` 标识一次查询（后端每次生成），用于 SSE 队列和进度追踪。如果不分离，同一 session 下连续两次提问会互相覆盖进度状态。

### 5.5 对象存储位置总结

| 对象 | MongoDB | Milvus | MinIO |
|------|---------|--------|-------|
| `course_series` | 完整对象 | — | — |
| `course_module` | 完整对象 | — | — |
| `question_bank` | 完整对象 | — | — |
| `question_item` | 完整对象 | — | — |
| `knowledge_document` | 完整对象 | — | — |
| `knowledge_chunk` | 完整对象（含全文） | 向量副本（chunk_id + 向量 + 过滤字段） | — |
| `source_mapping` | 完整对象 | — | — |
| `asset_object` | 元数据引用 | — | 实际图片文件 |
| `ingest_task` | 完整对象 | — | — |
| `chat_history` | 完整对象 | — | — |

## 6. 导入流程

导入流程的目标是把不同形态的数据变成统一可检索对象。最关键的设计点是：**按数据类型分流，不走单一解析链路。**

### 6.1 总体流程

```
API 接收导入请求
        │
        ▼
创建 ingest_task 到 MongoDB（status=pending）
        │
        ▼
BackgroundTasks 触发异步处理
        │
        ▼
LangGraph 导入流程开始执行
        │
        ├── task_type=catalog ──────► 课程目录解析分支
        │
        ├── task_type=questions ────► 题库解析分支
        │
        └── task_type=documents ───► 文档解析分支
                                       │
                                       ├── 为每个文件创建子任务
                                       │
                                       ▼
                                    逐文件处理：
                                    解析 → 分块 → 图片上传 MinIO
                                    → MongoDB 写入 → 向量化 → Milvus 写入
                                       │
                                       ▼
                                    更新子任务状态
        │
        ▼
更新 ingest_task 最终状态
```

### 6.2 课程目录导入（确定性路径）

**步骤 1：接收请求**
- 输入：`POST /ingest/catalog`，body 包含文件路径（默认 `data/数据/课程介绍.md`）
- 输出：`{ task_id: "..." }`，HTTP 202 Accepted
- 失败点：文件路径不存在或不可读
- 恢复：返回 400，不创建任务

**步骤 2：创建任务记录**
- 输入：task_type=catalog，文件路径
- 输出：MongoDB `ingest_task` 文档，status=pending
- 失败点：MongoDB 不可用
- 恢复：返回 503，提示存储服务不可用

**步骤 3：确定性 Markdown 解析**
- 输入：`课程介绍.md` 文件内容
- 输出：`course_series[]` + `course_module[]` 的结构化对象列表
- 处理逻辑：
  - 逐行扫描，`## ` 开头标记新系列
  - 系列块内匹配 `- **字段**: 值` 模式提取字段
  - `### 课程` 标记模块列表开始
  - 模块项匹配 `- **模块名**` + 缩进行提取编码、课时、学时、描述
- 失败点：文件格式变化导致解析异常（比如新增了未知字段，或缩进格式改变）
- 恢复：解析器应对未识别的行跳过而非崩溃；记录警告到 `progress_logs`；如果核心字段（series_code）缺失，标记该系列为解析失败但继续处理其他系列

**步骤 4：写入 MongoDB**
- 输入：解析后的 series/module 对象列表
- 输出：`course_series` 和 `course_module` collection 中的文档
- 写入策略：按 `series_code` / `module_code` 做 upsert（幂等），重复导入不会产生重复数据
- 失败点：MongoDB 写入超时或连接断开
- 恢复：已写入的数据不回滚（upsert 天然幂等），任务标记为 failed，下次重新导入会覆盖

**步骤 5：更新任务状态**
- 输入：解析和写入结果统计
- 输出：`ingest_task.status` = completed，记录解析到的系列数、模块数和任何警告
- 失败点：MongoDB 更新失败
- 恢复：任务状态停留在 running，但数据实际已写入。客户端轮询超时后可检查数据是否存在。

### 6.3 题库导入（确定性路径 + 质量标记）

**步骤 1-2：** 与课程目录导入类似，task_type=questions。

**步骤 3：确定性块解析**
- 输入：`题目资料.md` 文件内容
- 输出：`question_bank[]` + `question_item[]`
- 处理逻辑：
  - `## ` 开头标记新题库，提取题库名和编码
  - `### ` 开头标记新题目，提取题目编码
  - 题目块内提取：题型、题干、选项、答案、解析
  - 多选答案标准化：`A、B、C` / `A,B,C` / `ABC` → `["A", "B", "C"]`
  - 识别开放题型（简答、材料分析等），将"答案"字段映射到 `reference_answer` 而非 `answer_key`
  - 质量检查：空白选项 → `quality_flags: ["empty_option_C"]`；异常分隔符 → `quality_flags: ["mixed_answer_separator"]`
- 失败点：某个题目格式完全不可解析
- 恢复：跳过该题，记录到 `progress_logs`，保留 `raw_block` 以便人工修复。不因单题失败阻断整个题库导入。

**步骤 4：写入 MongoDB**
- 写入策略：按 `bank_code` / `question_code` 做 upsert
- 所有题目保留 `raw_block`，即使结构化字段提取完整

**步骤 5：更新任务状态**
- 记录：题库数、题目总数、成功数、质量标记汇总

### 6.4 文档导入（解析 + 分块 + 向量化路径）

这是最复杂的导入分支，因为涉及多个外部服务（MongoDB + MinIO + Milvus + BGE-M3 模型），每个都可能失败。

**核心设计决策：每个文件作为独立子任务。**

这意味着导入 16 个课程文档时，1 个文档解析失败不影响其他 15 个。任务状态结构如下：

```json
{
    "task_id": "task_001",
    "task_type": "documents",
    "status": "partial_success",
    "sub_tasks": [
        {"file": "Python1.0.docx", "status": "completed", "chunks": 85},
        {"file": "NLP1.0.9.docx", "status": "failed", "error": "docx 格式异常"},
        {"file": "Git1.4.0.docx", "status": "completed", "chunks": 120}
    ]
}
```

**步骤 1：接收请求**
- 输入：`POST /ingest/documents`，body 包含文件路径列表、`doc_type`（course_doc / project_doc）、可选的 `source_mapping` 信息
- 输出：`{ task_id: "..." }`

**步骤 2：创建主任务 + 子任务**
- 为每个文件创建一个子任务条目

**步骤 3：逐文件解析（per-file, 独立子任务）**

**3a. 文档格式统一（仅 .docx）**
- 输入：单个 .docx 文件
- 输出：转换后的 .md 文件 + 导出的图片目录
- 处理逻辑：调用 markitdown 将 .docx 转为 .md，内嵌图片导出到临时目录 `{work_dir}/{doc_id}/images/`
- 降级策略：如果 markitdown 转换失败或产出为空，尝试用 pandoc 重试（`pandoc -f docx -t markdown --extract-media={img_dir}`）
- 失败点：.docx 文件损坏（zipfile.BadZipFile）、转换工具不可用、转换产出为空
- 恢复：该子任务标记为 failed，记录错误详情，继续处理下一个文件

**3b. Markdown 解析（统一链路，.docx 转换后和原生 .md 共用）**
- 输入：.md 文件（原生或 .docx 转换产出）
- 输出：段落块列表（每块包含文本、标题层级、段落类型标记）
- 处理逻辑：按标题层级解析，识别代码块（` ``` `）、表格、图片引用（`![]()`）
- 失败点：文件编码异常、标题层级严重混乱
- 恢复：记录警告，尽力解析，不因格式问题阻断流程

**3c. 分块**
- 输入：段落块列表
- 输出：`knowledge_chunk[]`，每个 chunk 带 `section_path`、`chunk_kind`、`chunk_text`
- 分块规则见 §3.4 的分块策略描述
- 失败点：几乎不会失败（纯内存计算），除非输入数据异常大导致 OOM
- 恢复：限制单文件最大处理大小

**3d. 图片上传 MinIO**
- 输入：转换阶段（3a）导出的图片目录，或原生 .md 中 `![]()` 引用的本地图片文件
- 输出：MinIO 对象 + MongoDB `asset_object` 记录
- 处理逻辑：遍历导出的图片目录 → 生成 `object_key`（`documents/{doc_id}/images/{image_name}`）→ 上传 MinIO → 写 MongoDB 元数据 → 将 chunk 中的本地图片路径替换为 MinIO URL
- 失败点：MinIO 不可用或上传超时
- 恢复：图片上传失败不阻断文档导入。在 chunk 的 `image_refs` 中标记上传状态，等 MinIO 恢复后可单独补传。文本检索不依赖图片。

**3e. 写入 MongoDB**
- 输入：`knowledge_document` + `knowledge_chunk[]`
- 输出：MongoDB 文档记录
- 写入策略：先写 `knowledge_document`，再批量写 `knowledge_chunk`。按 `doc_id` 做 upsert，重复导入先删除旧 chunk 再写入新 chunk。
- 失败点：MongoDB 写入中断导致部分 chunk 写入
- 恢复：重新导入时 upsert 会覆盖，不会产生脏数据

**步骤 4：向量化**
- 输入：`knowledge_chunk[]` 的 `chunk_text`
- 输出：每个 chunk 的 dense_vector + sparse_vector
- 处理逻辑：BGE-M3 模型批量推理，batch_size 默认 8
- 失败点：GPU OOM（单 batch 太大）、模型加载失败
- 恢复：降低 batch_size 重试；模型加载失败标记任务失败，需人工排查

**步骤 5：向量入库 Milvus**
- 输入：chunk_id + doc_id + doc_type + dense_vector + sparse_vector
- 输出：Milvus collection 中的记录
- 写入策略：按 chunk_id upsert，重复导入覆盖旧向量
- 失败点：Milvus 不可用或连接超时
- 恢复：MongoDB 中的数据完整（步骤 4 已完成），等 Milvus 恢复后重跑向量化+入库步骤。任务状态标记为 `partial_success`（数据已入 MongoDB 但向量未入 Milvus）。

**步骤 6：更新来源映射**
- 输入：文件名、doc_id、请求中传入的映射信息
- 输出：`source_mapping` 记录
- 如果请求中未指定映射，则跑规则匹配（从文件名提取关键词，匹配课程系列的 description 或 category_path）

**步骤 7：更新子任务和主任务状态**
- 每个文件完成后更新对应子任务状态
- 所有子任务完成后，根据子任务结果汇总主任务状态：
  - 全部成功 → `completed`
  - 部分成功 → `partial_success`
  - 全部失败 → `failed`

### 6.5 导入幂等性

所有导入操作都设计为幂等的：

- 课程目录：按 `series_code` / `module_code` upsert
- 题库：按 `bank_code` / `question_code` upsert
- 文档：按 `doc_id` upsert（先删旧 chunk 再写新 chunk）
- Milvus 向量：按 `chunk_id` upsert

这意味着导入失败后可以安全地重新触发同一导入请求，不需要手动清理数据。

### 6.6 增量策略

- **课程目录和题库**：全量覆盖。整个 `.md` 文件每次重新解析并 upsert，数据量小（千级记录），全量重建成本可忽略。
- **文档**：文件级版本重建。重新导入某个文件时，删除该文件的所有旧 chunk 和旧向量，重新解析和向量化。不做 chunk 级的差分比对（复杂度高，收益低）。

## 7. 查询流程

查询流程不能只有一个统一问答入口靠 LLM 来理解和回答所有问题。应该先做意图分流，让确定性查询走结构化路径，只把真正需要语义理解的问题交给 LLM。

### 7.1 总体流程

```
用户输入（如"有哪些 Python 相关课程"）
        │
        ▼
意图分类（轻量 LLM 调用或规则匹配）
        │
        ├── course_intro ──► 课程查询（MongoDB 结构化）── ► 直接返回
        │
        ├── question_search ──► 题目检索（MongoDB 结构化）──► 直接返回
        │
        ├── doc_search ──► 文档检索（Milvus 向量 + MongoDB 回表）──► 直接返回
        │
        └── knowledge_qa ──► LangGraph 查询管线 ──► 多路检索 → 融合 → Rerank → 答案生成
                                                          │
                                                          ▼
                                                   保存历史到 MongoDB
```

### 7.2 意图分类

**输入：** 用户原始问题 + 会话历史（如有）

**输出：** 意图标签（`course_intro` / `question_search` / `doc_search` / `knowledge_qa`）

**实现方式：** 首版用规则匹配 + 轻量 LLM fallback：
- 规则层：关键词匹配（"有哪些课程""课程介绍""适合什么人" → `course_intro`；"题目""练习题""选择题" → `question_search`）
- LLM fallback：规则无法判断时，用一次轻量 LLM 调用做分类（system prompt 给出四个意图的定义和示例，让 LLM 返回分类标签）

**为什么不全部用 LLM 做分类：** 课程查询和题库检索这类请求，关键词特征非常明显，规则匹配既快又准。LLM 调用有延迟和成本，只在规则无法判断时才使用。

**失败点：** LLM 分类调用超时或返回无效标签
**恢复：** fallback 到 `knowledge_qa`（最通用的路径），宁可走一次完整的检索 + 生成，也不要拒绝用户请求

### 7.3 课程查询（结构化路径）

**输入：** 用户问题中的关键词/条件（如 Python、入门、在校生）

**输出：** 课程系列列表 + 课程详情，包含系列名称、描述、适合人群、学习目标、章节结构

**查询逻辑：**
- 从用户问题中提取查询条件（关键词 → `title` / `description` / `category_path` 的文本匹配；人群 → `audience` 数组匹配；目标 → `goal_tags` 匹配）
- MongoDB 查询 `course_series`，返回匹配的系列
- 对每个命中的系列，查 `course_module` 获取模块列表
- 查 `source_mapping` 获取关联的文档信息（如有）

**失败点：** MongoDB 查询超时
**恢复：** 返回错误提示，建议用户重试

### 7.4 题库检索（结构化路径）

**输入：** 题库筛选条件（题型、题库名/编码、关键词）

**输出：** 题目列表，包含题目内容、选项、答案、解析、所属题库

**查询逻辑：**
- 支持的过滤条件：`bank_code`、`question_type`、`stem` 关键词（MongoDB text index 或正则）
- 对 `quality_flags` 非空的题目，可选择是否展示质量标记

**失败点：** 同课程查询
**恢复：** 同课程查询

### 7.5 知识问答（LangGraph 查询管线）

这是最复杂的查询路径，只有被意图分类为 `knowledge_qa` 的问题才进入此路径。

```
用户问题
    │
    ▼
┌──────────────────────────────────────┐
│  意图确认 + 查询改写                   │
│  • 读取 MongoDB 历史做指代消解          │
│  • 将口语化问题改写为检索友好的查询      │
└──────────┬───────────────────────────┘
           │ (fan-out, 并行)
    ┌──────┴──────────┐
    ▼                  ▼
┌────────┐      ┌──────────┐
│向量检索  │      │HyDE 检索 │
│dense +  │      │LLM 生成  │
│sparse   │      │假设文档   │
│混合      │      │→ 向量检索 │
└───┬────┘      └────┬─────┘
    └──────┬─────────┘
           ▼
  ┌─────────────────┐
  │  RRF 融合        │
  │  基于排名的融合   │
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │  Rerank 重排序   │
  │  交叉编码器精排   │
  │  + 悬崖截断      │
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │  回表 MongoDB    │
  │  获取完整 chunk   │
  │  + 来源映射信息   │
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │  答案生成        │
  │  组装引用        │
  │  流式/非流式输出  │
  └────────┬────────┘
           ▼
  保存历史到 MongoDB
```

#### 7.5.1 查询改写

**输入：** 用户原始问题 + 会话历史（最近 N 轮）

**输出：** 改写后的检索查询

**为什么需要改写：**
- **指代消解**：用户说"它怎么做反向传播的"，需要从历史中找到"它"指的是哪个模型/框架
- **口语→检索**：用户说"Python 怎么连数据库"，改写为"Python MySQL 数据库连接 pymysql"，更容易命中文档中的技术描述

**失败点：** LLM 调用失败
**恢复：** 使用原始问题作为检索查询（跳过改写，不阻断流程）

#### 7.5.2 向量检索

**输入：** 改写后的查询文本

**输出：** Top-K 个 chunk_id + 相似度分数

**处理逻辑：**
- BGE-M3 对查询文本生成 dense_vector + sparse_vector
- Milvus 混合检索：`WeightedRanker(dense_weight, sparse_weight)` 融合两路结果
- 支持 `doc_type` 过滤（如只搜课程文档或只搜项目文档）
- 返回 Top `query_search_limit`（默认 5）个结果

**失败点：** Milvus 不可用、BGE-M3 模型推理失败
**恢复：** 向量检索失败时，该路结果为空，不阻断整个查询流程。RRF 融合可以只用 HyDE 检索的结果。

#### 7.5.3 HyDE 检索

**输入：** 用户原始问题（或改写后的查询）

**输出：** Top-K 个 chunk_id + 相似度分数

**处理逻辑：**
1. LLM 根据用户问题生成一段"假设性回答文档"（Hypothetical Document Embedding）
2. 用这段假设文档（而非用户问题）生成向量
3. 用该向量去 Milvus 检索

**为什么 HyDE 对教育场景有用：** 学生问问题的方式和文档的表述差异往往很大。比如学生问"怎么让神经网络学得更快"，文档里写的是"学习率调度策略"和"优化器选择"。HyDE 让 LLM 先用专业语言"翻译"用户的问题为一段近似文档，缩小了查询和文档之间的语义鸿沟。

**放弃的替代方案：**
- **Query Expansion（查询扩展）**：在原始查询中追加同义词。比 HyDE 简单但效果差——同义词替换无法捕捉"概念级"的语义差异（"学得更快" ≠ "学习率"的任何同义词）。
- **不做 HyDE，只用向量检索 + Rerank**：可以工作，但在教育场景下学生提问和文档表述的 gap 较大，Rerank 能改善排序但不能改善召回——如果向量检索根本没召回正确文档，Rerank 也无能为力。

**失败点：** LLM 生成假设文档失败、Milvus 检索失败
**恢复：** HyDE 失败时，该路结果为空。RRF 融合可以只用向量检索的结果。

#### 7.5.4 RRF 融合

**输入：** 向量检索结果列表 + HyDE 检索结果列表

**输出：** 融合排序后的 chunk_id 列表

**处理逻辑：** Reciprocal Rank Fusion — 基于排名而非分数的融合算法：
```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```
其中 `k` 是平滑常数（默认 60），`rank_i(d)` 是文档 d 在第 i 路检索中的排名。

**为什么用 RRF 而不是简单的分数合并：** 两路检索（向量检索和 HyDE 检索）返回的相似度分数尺度不同，不能直接相加或取平均。RRF 只看排名不看分数，天然对不同度量尺度鲁棒。

**失败点：** 纯内存计算，几乎不会失败
**恢复：** 如果某一路结果为空（因为上游失败），RRF 退化为对另一路结果的排名重新编号，不影响流程。

#### 7.5.5 Rerank 重排序

**输入：** RRF 融合后的 chunk_id 列表（Top 10-20）

**输出：** 精排后的 chunk_id 列表（Top 3-5）

**处理逻辑：**
- 用 chunk_id 回 MongoDB 取 chunk_text
- BGE-Reranker 交叉编码器对 `(query, chunk_text)` 逐对打分
- 悬崖截断：不用固定 Top-K，而是检测相邻分数的陡降点，动态决定保留多少条。避免信息浪费（固定 Top-3 可能漏掉第 4 个高分结果）或噪声引入（固定 Top-10 可能包含低相关文档）

**悬崖截断的具体规则：**
- 至少保留 `rerank_min_top_k`（默认 3）条
- 最多保留 `rerank_max_top_k`（默认 10）条
- 当相邻两条的分差超过 `rerank_gap_abs`（默认 0.5）或相对分差超过 `rerank_gap_ratio`（默认 0.25）时，在该位置截断

**失败点：** Reranker 模型加载失败或推理超时
**恢复：** 跳过 Rerank，直接使用 RRF 融合的排序结果（质量降低但不阻断流程）

#### 7.5.6 回表与来源组装

**输入：** Rerank 后的 chunk_id 列表

**输出：** 完整的 chunk 信息 + 来源映射

**处理逻辑：**
- 用 chunk_id 批量查 MongoDB `knowledge_chunk` 取完整文本和元数据
- 用 doc_id 查 `knowledge_document` 取文件名和文档标题
- 用 doc_id / source_file 查 `source_mapping` 取课程归属信息
- 组装成带来源信息的引用列表

**失败点：** MongoDB 查询失败
**恢复：** 如果回表失败，答案生成只能基于 Milvus 中存储的有限字段（chunk_id, doc_type），引用信息不完整但仍可生成答案

#### 7.5.7 答案生成

**输入：** 用户问题 + 检索到的 chunk 列表（带来源信息）

**输出：** 引用式回答（文本 + citations）

**处理逻辑：**
- 将 chunk 按字符预算（默认 12000 字符，约 4000 token）组装到 prompt 中
- 字符预算的意义：留够 LLM 输出空间，避免上下文超长导致截断
- 如果 chunk 总量超过预算，只取 Rerank 排名靠前的，保证最相关的内容进入 prompt
- LLM 生成回答，要求引用来源（返回 chunk_id 或来源信息）
- 支持流式输出（SSE）和非流式输出（同步 JSON）

**流式输出的实现：**
- 非流式模式：LLM 生成完整回答后一次性返回 JSON
- 流式模式：
  1. `POST /chat/query` 返回 `task_id`
  2. 客户端用 `GET /chat/stream/{task_id}` 建立 SSE 连接
  3. LangGraph 执行过程中，`answer_output` 节点逐 token 推送到 SSE 队列
  4. 最后推送 `[DONE]` 事件

**失败点：** LLM 调用失败或超时
**恢复：** 返回检索结果但不生成答案（"以下是检索到的相关内容，但答案生成暂时不可用"），让用户自行阅读检索到的文档片段

#### 7.5.8 历史保存

**输入：** 用户问题 + 生成的回答 + citations + 意图标签

**输出：** MongoDB `chat_history` 记录

**失败点：** MongoDB 写入失败
**恢复：** 历史保存是 fire-and-forget，失败不影响已返回给用户的回答。记录日志，下次会话时历史可能不完整但不影响功能。

### 7.6 查询容错总结

| 组件故障 | 课程查询 | 题库查询 | 文档检索 | 知识问答 |
|---------|---------|---------|---------|---------|
| MongoDB 不可用 | ✗ 完全不可用 | ✗ 完全不可用 | ✗ 降级（无法回表） | ✗ 严重降级 |
| Milvus 不可用 | ✓ 不受影响 | ✓ 不受影响 | ✗ 不可用 | ✗ 降级（无检索结果） |
| MinIO 不可用 | ✓ 不受影响 | ✓ 不受影响 | ✓ 文本正常，图片缺失 | ✓ 文本正常 |
| LLM 不可用 | ✓ 不受影响 | ✓ 不受影响 | ✓ 不受影响 | ✗ 降级（只返回检索结果） |
| BGE-M3 不可用 | ✓ 不受影响 | ✓ 不受影响 | ✗ 不可用 | ✗ 降级 |
| BGE-Reranker 不可用 | ✓ 不受影响 | ✓ 不受影响 | ✓ 降级（无精排） | ✓ 降级（无精排） |

## 8. 关键设计决策汇总

### 8.1 结构化数据不向量化

**决策：** 课程目录和题库数据只存 MongoDB，不做向量化。

**解决的问题：** 避免结构化字段在分块时丢失语义。"适合人群: 在校生, 职场人" 这种信息用结构化查询精度是 100%，向量化后反而引入噪音。

**放弃的方案：** 全部数据统一向量化 → 检索时用 metadata filter 区分。放弃原因：需要把所有字段都编码到向量 metadata 中，冗余且查询条件组合爆炸。

### 8.2 文档和课程/项目文档走同一条链路

**决策：** 课程文档和项目文档共用同一套解析 → 分块 → 向量化流程，通过 `doc_type` 字段区分。

**解决的问题：** 项目文档（如掌柜智库的 19 篇讲义）和课程文档的内容形态相似（都是长文本+代码+图片），检索和问答的用户体验也一致，不需要独立链路。

**通过 `doc_type` 保留区分能力：** 如果用户只想搜项目文档，可以在向量检索时传 `doc_type=project_doc` 过滤。

### 8.3 source_mapping 用显式映射表而非文件名推断

**决策：** 引入 `source_mapping` collection，先跑规则映射，再允许人工补录。

**解决的问题：** 课程文档文件名（`尚硅谷大模型技术之Python1.0.docx`）和课程模块编码（`general_purpose_programming_foundation_m1`）之间没有天然主键。文件名推断容易出错（Python 课程可能属于多个系列）。

**放弃的方案：**
- 纯文件名推断 → 不可靠，错误映射比没有映射更糟糕
- 导入时强制指定 → 增加使用门槛，不适合首版快速验证
- 不建立映射 → 检索结果缺少课程归属信息，违背需求文档中"返回课程名、项目名"的要求

### 8.4 HyDE 纳入首版查询管线

**决策：** 知识问答路径同时走向量检索和 HyDE 检索，RRF 融合后 Rerank。

**解决的问题：** 教育场景下，学生提问方式和文档表述差异大。向量检索（双塔模型）的召回能力受限于 query-doc 语义距离，HyDE 通过 LLM 生成假设文档来缩小这个距离，提升召回率。

**成本：** 每次知识问答多一次 LLM 调用（生成假设文档）+ 一次向量检索。延迟增加约 1-2 秒。

**失败容错：** HyDE 是增强而非必要路径。如果 LLM 调用失败，只用向量检索结果，不阻断流程。

### 8.5 每个文档作为独立子任务

**决策：** 文档导入时，每个文件有独立的子任务状态。

**解决的问题：** 16 个课程文档中如果 1 个文件格式异常导致解析失败，不应该影响其他 15 个的导入。

**放弃的方案：**
- 整批回滚 → 一个文件的问题导致所有工作白费，用户体验差
- 无子任务（只有总任务状态） → 无法定位哪个文件失败，排查困难

### 8.6 导入侧轮询 vs 查询侧 SSE

**决策：** 导入任务状态用客户端轮询 `GET /ingest/tasks/{task_id}`，查询问答用 SSE 长连接。

**解决的问题：** 两种场景的实时性要求完全不同。导入耗时秒到分钟级，1.5 秒轮询足够。LLM 逐字输出（几十毫秒/token），轮询无法满足实时性，必须用 SSE。

**放弃的方案：**
- 统一用 WebSocket → 导入场景不需要双向通信，WebSocket 连接维护成本高
- 统一用 SSE → 可以但没必要，导入状态只需要"拉取"不需要"推送"
- 统一用轮询 → 问答场景下用户看到文字逐字出现的体验远好于等待几秒后一次性展示

## 9. 版本边界

### 首版做这些

- 课程目录导入与查询
- 题库导入与查询（含质量标记）
- 课程文档 / 项目文档导入（含分块、向量化）
- 来源映射表（规则 + 人工）
- 文档检索与知识问答（向量检索 + HyDE + RRF + Rerank）
- 引用式答案生成（流式 SSE + 非流式 JSON）
- MongoDB 任务状态（含子任务）
- MongoDB 历史会话
- MinIO 图片存储
- 意图分流（规则 + LLM fallback）

### 首版不做这些

- 后台管理页面
- 多租户权限系统
- 图片 OCR / 图片理解问答
- 视频检索
- 增量差分更新的复杂调度（首版用全量覆盖 / 文件级重建）
- Web MCP 外部网络搜索（参考实现中有，但教育场景首版知识库内容自洽，不需要外部补充）
- PDF 导入链路（当前数据没有 PDF 主数据源，保留扩展位）

## 10. 实施顺序

整体按下面顺序推进，每一步都形成可验证的增量：

1. **基础工程和配置层**
   搭好 FastAPI 骨架、pydantic-settings 配置管理、MongoDB/Milvus/MinIO 客户端初始化、异常基类、BaseNode 抽象。
   验证点：`/health` 端点可访问，配置能从 `.env` 加载。

2. **课程目录确定性导入**
   实现课程介绍解析器、course_series/course_module 写入 MongoDB、课程查询 API。
   验证点：219 个系列、657 个模块完整入库，`/search/courses?keyword=Python` 返回正确结果。

3. **题库确定性导入**
   实现题库解析器（含质量标记）、question_bank/question_item 写入 MongoDB、题目检索 API。
   验证点：73 个题库、1752 道题完整入库，quality_flags 正确标记异常题目。

4. **文档转换、解析、分块、MinIO 图片存储**
   实现 .docx → .md 转换（markitdown 为主，pandoc 降级）、统一 Markdown 解析器、分块逻辑、MinIO 图片上传、source_mapping 规则匹配。
   验证点：至少 5 份课程文档（.docx 转换后）和 3 份项目文档导入成功，chunk 保留 section_path，转换后的 .md 中标题层级和代码块格式正确。

5. **向量化与 Milvus 入库**
   实现 BGE-M3 embedding 生成、Milvus collection 创建和写入。
   验证点：文档 chunk 可通过 Milvus 向量检索召回。

6. **导入任务状态管理**
   实现 ingest_task 和 sub_task 状态追踪、轮询接口。
   验证点：文档导入时可查询到子任务级别的进度。

7. **三条检索链路**
   实现课程查询 service、题目检索 service、文档检索 service（含回表和来源组装）。
   验证点：三类查询各自通过 API 返回正确结果和来源信息。

8. **知识问答管线**
   实现意图分流 → 查询改写 → 向量检索 + HyDE → RRF 融合 → Rerank → 答案生成 → 历史保存。
   验证点：端到端问答返回带引用的答案。

9. **流式输出与前端对接**
   实现 SSE 端点、chat.html 前端页面。
   验证点：流式问答在浏览器中逐字展示。

10. **端到端验收**
    用真实数据跑全量导入，用评测集验证检索效果和问答质量。
    验证点：所有导入任务完成（允许 partial_success），四类查询能力达到可用水平。

## 11. 当前结论

当前这套需求下，推荐主路线是：

- `FastAPI` — 接入层，支持同步/异步/SSE
- `LangGraph` — 编排层，管理导入和查询两条流程
- `MongoDB` — 业务真相，所有结构化数据和元数据
- `Milvus` — 向量检索副本，文档 chunk 的语义检索
- `MinIO` — 对象存储，图片和未来资产
- `markitdown` — .docx → .md 转换（pandoc 作为降级备选）
- `BGE-M3` — Embedding，稠密+稀疏混合向量
- `BGE-Reranker` — 重排序，交叉编码器精排

这条路线是在参考实现（shopkeeper_brain）基础上，针对教育数据特点做的改造：

- **结构化数据不强行向量化** — 课程目录和题库走确定性解析和结构化查询
- **文档检索和题库检索分开设计** — 意图分流，确定性查询不经过 LLM
- **.docx 先转 Markdown 再解析** — 消除 python-docx 启发式解析的复杂性，.docx 和 .md 共用统一分块链路
- **引入 HyDE 检索** — 弥补学生口语化提问与文档专业表述之间的语义鸿沟
- **引入 source_mapping** — 解决文档与课程目录命名体系不同的真实问题
- **每个文档独立子任务** — 导入容错，单文件失败不影响整批
- **任务状态和历史统一落 MongoDB** — 单一数据源，简化运维
- **图片对象从一开始就进入 MinIO** — 预留多模态扩展能力
