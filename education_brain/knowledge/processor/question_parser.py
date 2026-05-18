"""
题目资料.md 确定性解析器

状态机: 空闲 → 读题库头 → 读题目块 → 遇到新 ## 时 flush 题库

与课程目录解析器同一思路，但多了:
- 选项解析(A. B. C. D.)
- 多选答案标准化(A、B、C → ["A","B","C"])
- 开放题型识别(简答/案例分析等 → reference_answer)
- 质量标记(空选项、混合分隔符等)

外层（parse_questions）负责切块——按 ## / ### 把文件切成一个个题目的原始文本块
内层（_parse_single_question）负责提取——在单个题目块内提取字段、选项、答案
"""

import logging
import re
from pathlib import Path

from knowledge.models.question import QuestionBank, QuestionItem, QuestionOption

logger = logging.getLogger(__name__)

# ── 题型分类 ──
# 有标准答案的题型（答案存 answer_key）
_OBJECTIVE_TYPES: frozenset[str] = frozenset({
    "单选题", "多选题", "判断题",
})

# ── 正则 ──
_FIELD_RE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.*)$")
_OPTION_RE = re.compile(r"^([A-Z])\.\s*(.*)$")
_BANK_CODE_RE = re.compile(r"^- 题库编码:\s*(.+)$")

# ── 答案标准化 ──
_ANSWER_SEP_RE = re.compile(r"[、，,\s]+")

def _normalize_answer(raw: str, question_type: str) -> tuple[str, list[str]]:
    """
    标准化答案，返回 (normalized_answer, quality_flags)。

    多选题: "A、B、C" → "A,B,C"
    单选/判断: 原样保留
    """
    flags: list[str] = []
    cleaned = raw.strip()

    if question_type == "多选题":
        parts = _ANSWER_SEP_RE.split(cleaned)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 1:
            has_chinese_sep = "、" in raw or "，" in raw
            has_comma = "," in raw
            if has_chinese_sep and has_comma:
                flags.append("mixed_answer_separator")
            cleaned = ",".join(sorted(parts))
    return cleaned, flags

def _check_options_quality(options: list[QuestionOption]) -> list[str]:
    """检查选项质量，返回 quality_flags"""
    flags = [f"empty_option_{opt.label}" for opt in options if not opt.content.strip()]
    return flags

def parse_questions(file_path: str | Path) -> tuple[list[QuestionBank], list[QuestionItem]]:
    """
    解析题目资料.md , 返回 (题库列表, 题目列表)。

    容错策略: 单题解析失败不阻断整个题库。
    所有题目保留 raw_block 作为回退。
    """
    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    all_banks : list[QuestionBank] = []
    all_items : list[QuestionItem] = []

    # ── 当前题库状态 ──
    current_bank_name: str | None = None
    current_bank_code: str = ""
    bank_question_count = 0

    # ── 当前题目状态 ──
    current_q_code: str | None = None
    current_q_lines: list[str] = []

    def _flush_question():
        """将当前题目原始行解析为 QuestionItem"""
        nonlocal current_q_code, current_q_lines, bank_question_count
        if current_q_code is None:
            return

        raw_block = "\n".join(current_q_lines)
        item = _parse_single_question(
            current_q_code, current_bank_code, raw_block
        )
        if item:
            all_items.append(item)
            bank_question_count += 1

        current_q_code = None
        current_q_lines = []
    
    def _flush_bank():
        """将当前题库构建为 QuestionBank"""
        nonlocal current_bank_name, current_bank_code, bank_question_count
        if current_bank_name is None:
            return
        
        if not current_bank_code:
            logger.warning("题库 '%s' 缺少 bank_code，跳过", current_bank_name)
        else:
            bank = QuestionBank(
                bank_code=current_bank_code,
                bank_name=current_bank_name,
                question_count=bank_question_count,
            )
            all_banks.append(bank)
        
        current_bank_name = None
        current_bank_code = ""
        bank_question_count = 0

    for line in lines:
        stripped = line.rstrip()

        # -- ## 题库标题 --
        if stripped.startswith("## ") and not stripped.startswith("### "):
            _flush_question()
            _flush_bank()
            current_bank_name = stripped[3:].strip()
            continue

        if current_bank_name is None:
            continue

        # 题库编码
        m = _BANK_CODE_RE.match(stripped)
        if m :
            current_bank_code = m.group(1).strip()
            continue

        # -- ### question_code(新题的) --
        if stripped.startswith("### "):
            _flush_question()
            current_q_code = stripped[4:].strip()
            current_q_lines = []
            continue

        #  题目内容行
        if current_q_code is not None:
            current_q_lines.append(stripped)
    
    # 文件末尾 flush
    _flush_question()
    _flush_bank()

    logger.info(
        "解析完成: %d 个题库, %d 个题目",
        len(all_banks), len(all_items),
    )

    return all_banks , all_items

def _parse_single_question(
    q_code : str ,
    bank_code : str,
    raw_block : str
)->QuestionItem | None:
    """从原始文本块解析单个题目"""
    fields : dict[str , str] = {}
    options : list[QuestionOption] = []
    in_options = False

    for line in raw_block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # 字段行: - **题型**: xxx
        fm = _FIELD_RE.match(stripped)
        if fm:
            label , value = fm.group(1) , fm.group(2)
            if label == "选项":
                in_options = True
                continue

            in_options = False
            fields[label] = value
            continue

        # 选项行: A. xxx
        if in_options:
            om = _OPTION_RE.match(stripped)
            if om:
                options.append(QuestionOption(
                    label=om.group(1), content=om.group(2)
                ))
                continue

    question_type = fields.get("题型", "")
    stem = fields.get("题干", "")
    raw_answer = fields.get("答案", "")
    analysis = fields.get("解析", "")

    quality_flags : list[str] = []

    # 选项质量检查
    quality_flags.extend(_check_options_quality(options))

    # 答案处理: 客观题 → answer_key, 开放题 → reference_answer
    answer_key = ""
    reference_answer = ""

    if question_type in _OBJECTIVE_TYPES:
        normalized , ans_flags = _normalize_answer(raw_answer , question_type)
        answer_key = normalized
        quality_flags.extend(ans_flags)
    else :
        reference_answer = raw_answer
    
    if not stem :
        quality_flags.append("missing_stem")
        logger.warning("题目 %s 缺少题干", q_code)
    
    return QuestionItem(
        question_code=q_code,
        bank_code=bank_code,
        question_type=question_type,
        stem=stem,
        options=options,
        answer_key=answer_key,
        reference_answer=reference_answer,
        analysis=analysis,
        raw_block=raw_block,
        quality_flags=quality_flags,
    )




    

