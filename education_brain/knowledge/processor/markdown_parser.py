# knowledge/processor/markdown_parser.py
"""
统一 Markdown 结构解析器

职责：将 Markdown 文本解析为"段落块"列表，每个块带有：
  - 文本内容
  - 标题层级（如果是标题行）
  - 块类型(heading / text / code / table / image)
  - 所属的章节路径(section_path)

这个解析器不做分块（分块是下一步 chunker 的事），
它只负责"理解文档结构"——哪些行属于标题、哪些行属于代码块、
哪些行是表格、哪些行引用了图片。

为什么不直接用 langchain 的 MarkdownHeaderTextSplitter？
  langchain 的实现按标题拆分后丢失了代码块/表格的类型信息，
  而我们的分块策略需要知道"这个段落是代码块还是普通文本"
  （代码块不能在中间切断，表格也不能）。
"""

import re
from dataclasses import dataclass, field

# ── 正则 ──

# 匹配 Markdown 标题行：# / ## / ### / #### ...
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")

# 匹配代码块围栏的开始/结束：``` 或 ```python
_CODE_FENCE_RE = re.compile(r"^(`{3,})(.*)?$")

# 匹配图片引用：![alt](path)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# 匹配表格行：| col1 | col2 | col3 |
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")

# 匹配表格分隔行：|---|---|---|
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")

@dataclass
class ParsedBlock:
    """解析后的文档结构块

    一个 ParsedBlock 代表文档中的一个"语义单元":
    - 一个标题(heading)
    - 一段连续的普通文本(text)
    - 一个完整的代码块(code)
    - 一个完整的表格(table)
    - 一个图片引用(image)

    section_path 记录该块所在的章节层级，
    例如 ["第3章 深度学习", "3.2 反向传播"]
    表示这个块在"第3章 → 3.2节"下面。
    """
    kind: str                                       # heading / text / code / table / image
    content: str = ""                               # 块的文本内容
    heading_level: int = 0                          # 标题层级（1-6），非标题为 0
    section_path: list[str] = field(default_factory=list)
    code_language: str = ""                         # 代码块的语言标记（如 python）
    image_paths: list[str] = field(default_factory=list)  # 该块引用的图片路径

def parse_markdown(text: str) -> list[ParsedBlock]:
    """
    将 Markdown 文本解析为 ParsedBlock 列表。

    解析是一个单遍状态机：
    - 正常状态：逐行判断是标题、表格、图片还是普通文本
    - 代码块状态：遇到 ``` 开始，再遇到 ``` 结束，中间所有行作为代码内容
    - 表格状态：连续的 | 开头行组成一个表格块

    状态转换图：
        Normal ──(```)──→ InCode ──(```)──→ Normal
        Normal ──(|...)──→ InTable ──(非|行)──→ Normal

    section_path 的维护逻辑：
        遇到 ## 标题时，清空所有 level >= 2 的标题，压入新标题。
        遇到 ### 标题时，清空所有 level >= 3 的标题，压入新标题。
        这样 section_path 始终反映"当前位置的标题层级链"。
    """

    lines = text.splitlines()
    blocks: list[ParsedBlock] = []

    # ── 章节路径追踪 ──
    # heading_stack[i] = level i 的标题文本
    # 用 dict 而不是 list，因为标题层级可能跳跃（如直接从 # 跳到 ###）
    heading_stack: dict[int, str] = {}

    def _current_section_path() -> list[str]:
        """从 heading_stack 构建当前的 section_path"""
        return [heading_stack[k] for k in sorted(heading_stack)]
    
    # 临时状态
    current_text_lines: list[str] = []      # 累积普通文本行
    in_code_block = False                   # 是否在代码块内
    code_lines: list[str] = []              # 代码块内容
    code_language = ""                      # 代码块语言
    code_fence = ""                         # 记住开始时的围栏标记（可能是 ``` 或 ````）
    in_table = False                        # 是否在表格内
    table_lines: list[str] = []             # 表格内容

    def _flush_text():
        """将累积的普通文本行输出为一个 text 块"""
        nonlocal current_text_lines
        if not current_text_lines:
            return
        content = "\n".join(current_text_lines).strip()
        if content:
            # 检查文本中是否包含图片引用
            img_paths = _IMAGE_RE.findall(content)
            blocks.append(ParsedBlock(
                kind="text",
                content=content,
                section_path=_current_section_path(),
                image_paths=[path for _, path in img_paths],
            ))
        current_text_lines = []
    
    def _flush_table():
        """将累积的表格行输出为一个 table 块"""
        nonlocal in_table, table_lines
        if not table_lines:
            in_table = False
            return
        content = "\n".join(table_lines).strip()
        if content:
            blocks.append(ParsedBlock(
                kind="table",
                content=content,
                section_path=_current_section_path(),
            ))
        in_table = False
        table_lines = []
    
    for line in lines:
        stripped = line.rstrip()

        # ════════════════════════════════
        # 状态1：在代码块内部
        # ════════════════════════════════
        if in_code_block:
            # 检查是否遇到匹配的闭合围栏
            fence_match = _CODE_FENCE_RE.match(stripped)
            if fence_match and fence_match.group(1) == code_fence:
                # 代码块结束
                blocks.append(ParsedBlock(
                    kind="code",
                    content="\n".join(code_lines),
                    section_path=_current_section_path(),
                    code_language=code_language,
                ))
                in_code_block = False
                code_lines = []
                code_language = ""
                code_fence = ""
            else:
                code_lines.append(line)  # 保留原始缩进
            continue

        # ════════════════════════════════
        # 状态2：正常解析
        # ════════════════════════════════

        # ── 代码块开始 ──
        fence_match = _CODE_FENCE_RE.match(stripped)
        if fence_match:
            _flush_text()       # 先输出之前累积的文本
            _flush_table()      # 如果在表格中也要先 flush
            code_fence = fence_match.group(1)
            code_language = (fence_match.group(2) or "").strip()
            in_code_block = True
            code_lines = []
            continue

        # ── 标题行 ──
        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            _flush_text()
            _flush_table()

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            # 更新 heading_stack：
            # 遇到 level=2 的标题时，删除所有 >= 2 的旧标题
            for k in [k for k in heading_stack if k >= level]:
                del heading_stack[k]
            heading_stack[level] = title

            blocks.append(ParsedBlock(
                kind="heading",
                content=title,
                heading_level=level,
                section_path=_current_section_path(),
            ))
            continue

        # ── 表格行 ──
        if _TABLE_ROW_RE.match(stripped) or _TABLE_SEP_RE.match(stripped):
            _flush_text()
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
            continue

        # 如果之前在表格中，但当前行不是表格行 → 表格结束
        if in_table:
            _flush_table()

        # ── 普通文本行（包括空行） ──
        current_text_lines.append(stripped)

    # ── 文件末尾：flush 所有残余 ──
    if in_code_block and code_lines:
        # 未闭合的代码块，作为代码块处理
        blocks.append(ParsedBlock(
            kind="code",
            content="\n".join(code_lines),
            section_path=_current_section_path(),
            code_language=code_language,
        ))
    
    _flush_table()
    _flush_text()

    return blocks