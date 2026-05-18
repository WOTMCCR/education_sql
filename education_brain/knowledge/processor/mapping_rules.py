# knowledge/processor/mapping_rules.py
"""
来源映射规则匹配 — 对应 PLAN.md §6.4 步骤 6

从文档文件名中提取关键词，
匹配 MongoDB 中已有的课程系列的 description 或 category_path。

这是一个"尽力而为"的规则匹配，不保证 100% 准确。
首版接受"规则映射 + 人工补充"的治理方式（PLAN.md §2.4）。

映射思路：
  文件名 "尚硅谷大模型技术之Python1.0.docx"
  → 提取关键词 "Python"
  → 在 course_series 的 title/description/category_path 中搜索
  → 如果命中，建立映射关系

为什么不用 LLM 做映射？
  文件名中的关键词特征非常明显（Python、MySQL、Git...），
  简单的字符串匹配就够了。LLM 调用有延迟和成本，
  对于这种"模式明确"的任务是杀鸡用牛刀。
"""
import logging
import re
from pymongo.database import Database

from knowledge.models.document import SourceMapping

logger = logging.getLogger(__name__)

# 从文件名中提取关键词的正则
# "尚硅谷大模型技术之Python1.0.docx" → "Python"
# "尚硅谷大模型技术之numpy与pandas2.0.docx" → "numpy与pandas"
_KEYWORD_RE = re.compile(r"之(.+?)[\d.]*\.docx$", re.IGNORECASE)

def infer_source_mapping(
    db: Database,
    source_file: str,
    doc_id: str,
    doc_type: str,
) -> SourceMapping | None:
    """
    从文件名推断来源映射。

    返回 SourceMapping 或 None（无法推断时）。
    """

    # 项目文档：直接用目录名作为 project_name
    if doc_type == "project_doc":
        # 掌柜智库的 .md 文件 → project_name = "掌柜智库"
        if "掌柜智库" in source_file:
            return SourceMapping(
                source_file=source_file,
                doc_id=doc_id,
                project_name="掌柜智库",
                mapping_type="rule",
            )
        return None
    
    # 课程文档：从文件名提取关键词，匹配课程系列
    m = _KEYWORD_RE.search(source_file)
    if not m:
        logger.debug("无法从文件名提取关键词: %s", source_file)
        return None
    
    keyword = m.group(1).strip()

    # 在 course_series 中搜索匹配的系列
    col = db["course_series"]
    query = {
        "$or": [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
            {"category_path": {"$regex": keyword, "$options": "i"}},
        ]
    }
    match = col.find_one(query)

    if match:
        return SourceMapping(
            source_file=source_file,
            doc_id=doc_id,
            series_code=match.get("series_code", ""),
            mapping_type="rule",
        )
    
    logger.debug("关键词 '%s' 未匹配到课程系列: %s", keyword, source_file)
    return None