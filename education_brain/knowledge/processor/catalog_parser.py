"""
课程介绍.md 确定性解析器

逐行扫描，用标题层级和字段模式匹配提取。
状态机：空闲 → 读系列 → 读模块 → 空闲
"""

import logging
import re
from pathlib import Path

from knowledge.models.course import CourseModule, CourseSeries

logger = logging.getLogger(__name__)

# 字段匹配模式
# 匹配 "- **系列编码**: general_purpose_programming_foundation"
_FIELD_RE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.+)$")

# 匹配模块行 "- **语法基础与开发环境**"
_MODULE_TITLE_RE = re.compile(r"^- \*\*(.+?)\*\*\s*$")

# 匹配模块详情 "  - 编码: xxx, 课时: 8, 学时: 16.00"
_MODULE_DETAIL_RE = re.compile(
    r"^\s+- 编码:\s*(.+?),\s*课时:\s*(\d+),\s*学时:\s*([\d.]+)"
)

# 匹配模块描述 "  - 描述: xxx"
_MODULE_DESC_RE = re.compile(r"^\s+- 描述:\s*(.+)$")

# 字段名 → CourseSeries 属性名的映射
_SERIES_FIELD_MAP: dict[str, str] = {
    "系列编码": "series_code",
    "描述": "description",
    "课程分类": "category_path",
    "适合人群": "audience",
    "学习目标": "goal_tags",
    "适合年级": "grade_tags",
}

# 需要拆分为列表的字段
# frozenset(...) 接收任意可迭代对象，把它转成不可变集合。
_LIST_FIELDS: frozenset[str] = frozenset({"audience", "goal_tags", "grade_tags"})

def _split_list(value: str) -> list[str]:
    """
    将 "在校生, 职场人, 求职者" 拆分为 ["在校生", "职场人", "求职者"]
    
    示例:
    - **适合人群**: 在校生, 职场人, 求职者
    """
    return [v.strip() for v in value.split(",") if v.strip()]

def parse_catalog(file_path: str | Path) -> tuple[list[CourseSeries], list[CourseModule]]:
    """
    解析 课程介绍.md, 返回 (系列列表, 模块列表)。

    不因单个系列解析失败而中断整个流程——
    跳过异常系列，记录警告，继续处理。
    """

    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    all_series : list[CourseSeries] = []
    all_modules : list[CourseModule] = []

    # 当前系列的临时状态
    current_title : str | None = None
    current_fields : dict[str , object] = {}
    in_module_section = False
    pending_module_title : str | None = None
    module_index = 0

    def _flush_series():
        """将当前积累的字段构建为 CourseSeries + CourseModule 对象"""
        nonlocal current_title , current_fields , in_module_section
        nonlocal pending_module_title , module_index

        if current_title is None:
            return
        
        series_code = current_fields.get("series_code" , "")
        if not series_code:
            logger.warning("系列 '%s' 缺少 series_code，跳过", current_title)
            _reset()
            return
        
        series = CourseSeries(
            title=current_title,
            **{k: v for k , v in current_fields.items() if k in CourseSeries.model_fields},
        )

        all_series.append(series)
        _reset()
        
    

    def _reset():
        nonlocal current_title, current_fields, in_module_section
        nonlocal pending_module_title, module_index
        current_title = None
        current_fields = {}
        in_module_section = False
        pending_module_title = None
        module_index = 0
    
    for line_no, line in enumerate(lines, 1):
        stripped = line.rstrip()

        # ── ## 系列标题 ──
        if stripped.startswith("## ") and not stripped.startswith("### "):
            _flush_series()
            current_title = stripped[3:].strip()
            in_module_section = False
            continue

        if current_title is None:
            continue

        # ── ### 课程（进入模块区） ──
        if stripped.startswith("### "):
            in_module_section = True
            continue

        if not in_module_section:
            # ── 系列字段区 ──
            m = _FIELD_RE.match(stripped)

            if m:
                field_label , value = m.group(1) , m.group(2)
                attr_name = _SERIES_FIELD_MAP.get(field_label)
                if attr_name:
                    if attr_name in _LIST_FIELDS:
                        current_fields[attr_name] = _split_list(value)
                    else :
                        current_fields[attr_name] = value
                else :
                    logger.debug(
                        "第 %d 行: 未识别的字段 '%s'，跳过", line_no, field_label
                    )
        else:
            # ── 模块区：模块标题行 ──
            mt = _MODULE_TITLE_RE.match(stripped)
            if mt:
                pending_module_title = mt.group(1)
                module_index += 1
                continue

            # ── 模块区：编码/课时/学时行 ──
            md = _MODULE_DETAIL_RE.match(stripped)
            if md and pending_module_title:
                module = CourseModule(
                    module_code=md.group(1).strip(),
                    series_code=str(current_fields.get("series_code", "")),
                    module_title=pending_module_title,
                    lesson_count=int(md.group(2)),
                    study_hours=float(md.group(3)),
                    sort_order=module_index,
                )
                all_modules.append(module)
                continue
            
            # ── 模块区：描述行（补充到最后一个模块） ──
            mdesc = _MODULE_DESC_RE.match(stripped)
            if mdesc and all_modules and all_modules[-1].series_code == current_fields.get("series_code"):
                all_modules[-1].module_desc = mdesc.group(1).strip()
    
    # 最后一个系列
    _flush_series()

    logger.info("解析完成: %d 个系列, %d 个模块", len(all_series), len(all_modules))
    return all_series, all_modules

