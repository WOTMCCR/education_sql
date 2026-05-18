# knowledge/models/document.py
"""文档领域数据模型 — 对应 PLAN.md §5.3 / §5.4"""

from pydantic import BaseModel , Field

class KnowledgeDocument(BaseModel):
    """文档元数据 — 每个导入的 .docx 或 .md 文件对应一条记录

    这个模型存的是"整个文件"的信息，而不是分块后的内容。
    分块结果存在 KnowledgeChunk 中，通过 doc_id 关联。

    示例：导入 "尚硅谷大模型技术之Python1.0.docx" 时，
    会创建一条 KnowledgeDocument（记录文件级元数据）
    + 若干条 KnowledgeChunk（记录分块后的文本片段）
    """

    doc_id: str                             # 唯一 ID（由导入流程生成）
    doc_type: str = "course_doc"            # "course_doc" | "project_doc"
    source_path: str = ""                   # 原始文件完整路径
    source_file: str = ""                   # 文件名（不含路径）
    title: str = ""                         # 从文件名或首标题提取
    domain_tags: list[str] = Field(default_factory=list)
    chunk_count: int = 0                    # 分块总数（写入后回填）
    image_count: int = 0                    # 提取的图片总数
    ingest_task_id: str = ""                # 导入该文档的任务 ID

class KnowledgeChunk(BaseModel):
    """文档分块 — 向量检索的最小粒度

    每个 chunk 是一个语义完整的文本片段。
    section_path 记录它在文档中的位置（章节路径），
    这样检索命中后能告诉用户"这段内容来自第3章 → 3.2节 → 反向传播"。

    chunk_kind 区分内容类型：
    - text: 纯文本段落
    - code: 代码块
    - table: 表格
    - mixed: 混合内容（文本+代码交替）
    """

    chunk_id: str                           # 唯一 ID
    doc_id: str                             # 所属文档 ID（外键）
    section_path: list[str] = Field(default_factory=list)   # 章节路径
    chunk_text: str = ""                    # chunk 正文
    chunk_kind: str = "text"                # text / code / table / mixed
    chunk_index: int = 0                    # 在文档内的顺序号
    image_refs: list[str] = Field(default_factory=list)     # 分块后为原始路径，上传替换后为图片 URL
    code_refs: list[dict] = Field(default_factory=list)     # 代码块引用
    table_refs: list[dict] = Field(default_factory=list)    # 表格引用

class SourceMapping(BaseModel):
    """来源映射表 — 解决"文档与课程目录命名体系不同"的问题

    课程目录的编码是 general_purpose_programming_foundation_m1，
    文档的文件名是 尚硅谷大模型技术之Python1.0.docx，
    两者之间没有天然主键。

    这张表建立它们之间的映射关系：
    - mapping_type="rule"：系统自动推断的映射
    - mapping_type="manual"：人工手动补录的映射

    查询时，如果一个 chunk 被检索命中，可以通过
    doc_id → source_mapping → series_code/module_code
    告诉用户"这段内容属于哪个课程系列"。
    """
    source_file: str = ""                   # 原始文件名
    doc_id: str = ""                        # 文档 ID（文档级映射）
    bank_code: str = ""                     # 题库编码（题库级映射，可选）
    series_code: str = ""                   # 映射到的课程系列
    module_code: str = ""                   # 映射到的课程模块（可选）
    project_name: str = ""                  # 项目名称（项目文档用）
    mapping_type: str = "rule"              # "rule" | "manual"
