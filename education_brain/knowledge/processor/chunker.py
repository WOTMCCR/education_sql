# knowledge/processor/chunker.py
"""
智能文档分块器

分块不是简单的按固定字符数切割。教育文档有明显的章节结构，
分块应该尊重这个结构。

分块流程（三阶段）：

  阶段1: 按标题分组
    将 ParsedBlock 列表按标题切分为"章节组"。
    每遇到一个标题，就开始一个新的分组。
    标题本身不单独成 chunk，而是作为下一组内容的上下文。

  阶段2: 长段拆分
    如果某个分组的文本超过 max_content_length（默认 2000 字符），
    在段落边界（空行）处二次拆分。
    代码块和表格不拆分——它们作为完整单元保留。

  阶段3: 短段合并
    如果相邻的分组文本都很短（低于 min_content_length=500 字符），
    将它们合并为一个 chunk，避免产生大量碎片化的小 chunk。
    合并时保留第一个分组的 section_path。

为什么不用 langchain 的 RecursiveCharacterTextSplitter？
  langchain 的分块器是"通用文本切割"，不理解 Markdown 结构。
  它会在代码块中间切断、在表格中间切断，产生无意义的碎片。
  我们的教育文档有清晰的章节结构，应该利用这个结构来分块。
"""
from dataclasses import dataclass
import logging
from uuid import uuid4

from knowledge.core.config import get_settings
from knowledge.models.document import KnowledgeChunk
from knowledge.processor.markdown_parser import ParsedBlock

logger = logging.getLogger(__name__)

@dataclass
class _Section:
    """内部使用的章节分组，聚合标题下的所有内容块"""
    section_path: list[str]
    blocks: list[ParsedBlock]
    text_length: int = 0        # 所有块文本的总长度

    def combined_text(self) -> str:
        """将所有块的文本合并为一个字符串"""
        parts = []
        for b in self.blocks:
            if b.kind == "code" and b.code_language:
                parts.append(f"```{b.code_language}\n{b.content}\n```")
            elif b.kind == "code":
                parts.append(f"```\n{b.content}\n```")
            elif b.kind == "table":
                parts.append(b.content)
            else:
                parts.append(b.content)
        return "\n\n".join(parts)
    
    def primary_kind(self) -> str:
        """判断该分组的主要内容类型"""
        kinds = {b.kind for b in self.blocks if b.kind != "heading"}
        if not kinds:
            return "text"
        if kinds == {"code"}:
            return "code"
        if kinds == {"table"}:
            return "table"
        if len(kinds) > 1:
            return "mixed"
        return kinds.pop()
    
    def all_image_paths(self) -> list[str]:
        """收集所有块中引用的图片路径"""
        paths = []
        for b in self.blocks:
            paths.extend(b.image_paths)
        return paths


def chunk_document(
    blocks : list[ParsedBlock],
    doc_id : str,
)->list[KnowledgeChunk]:
    """
    将解析后的 ParsedBlock 列表转换为 KnowledgeChunk 列表。

    参数：
        blocks:  markdown_parser.parse_markdown() 的输出
        doc_id:  所属文档的 ID（用于建立关联）

    返回：
        KnowledgeChunk 列表，每个 chunk 有唯一的 chunk_id
    """
    s = get_settings()

    # 阶段1 按标题分组
    sections = _split_by_heading(blocks)

    # 阶段2 : 长段拆分
    sections = _split_long_sections(sections, s.max_content_length)

    # ── 阶段3：短段合并 ──
    sections = _merge_short_sections(sections, s.min_content_length)

    # ── 生成 KnowledgeChunk ──
    chunks: list[KnowledgeChunk] = []
    for idx, section in enumerate(sections):
        text = section.combined_text()
        if not text.strip():
            continue

        chunks.append(KnowledgeChunk(
            chunk_id=uuid4().hex[:16],
            doc_id=doc_id,
            section_path=section.section_path,
            chunk_text=text,
            chunk_kind=section.primary_kind(),
            chunk_index=idx,
            image_refs=section.all_image_paths(),
        ))

    logger.info("分块完成: doc_id=%s, %d 个 chunk", doc_id, len(chunks))
    return chunks

def _split_by_heading(blocks: list[ParsedBlock]) -> list[_Section]:
    """
    阶段1:按标题将 blocks 分组为 sections。

    每遇到一个 heading 类型的 block,就开始一个新的 section。
    heading 之前（文档开头）的内容归到一个"无标题"section。

    示例输入（简化）：
        [heading("第1章"), text("..."), code("..."), heading("第2章"), text("...")]

    示例输出：
        [Section(path=["第1章"], blocks=[text, code]),
         Section(path=["第2章"], blocks=[text])]
    """
    sections: list[_Section] = []
    current_blocks: list[ParsedBlock] = []
    current_path: list[str] = []

    for block in blocks:
        if block.kind == "heading":
            # 先把之前累积的 blocks 输出为一个 section
            if current_blocks:
                total_len = sum(len(b.content) for b in current_blocks)
                sections.append(_Section(
                    section_path=list(current_path),
                    blocks=current_blocks,
                    text_length=total_len,
                ))

            current_blocks = []
            current_path = list(block.section_path)
        else:
            current_blocks.append(block)
    
    # 最后一组
    if current_blocks:
        total_len = sum(len(b.content) for b in current_blocks)
        sections.append(_Section(
            section_path=list(current_path),
            blocks=current_blocks,
            text_length=total_len,
        ))

    return sections

def _split_long_sections(
    sections: list[_Section],
    max_length: int,
) -> list[_Section]:
    """
    阶段2: 将超长 section 在段落边界处二次拆分。

    只拆分 text 类型的内容。
    code 和 table 块即使超长也保持完整——
    因为代码块和表格在中间切断会丧失语义。

    拆分策略：
      - 遍历 section 中的 blocks
      - 累积 text blocks 的文本长度
      - 当累积长度超过 max_length 时，在当前位置切分
      - code/table blocks 总是作为独立单元，不参与累积
    """
    result : list[_Section] = []
    for section in sections:
        if section.text_length <= max_length:
            result.append(section)
            continue

        # 需要拆分
        current_blocks : list[ParsedBlock] = []
        current_len = 10

        for block in section.blocks:
            block_len = len(block.content)

            # code/table 块：如果之前有累积文本，先 flush，
            # 然后 code/table 单独成一个 section
            if block.kind in ("code", "table"):
                if current_blocks:
                    result.append(_Section(
                        section_path=list(section.section_path),
                        blocks=current_blocks,
                        text_length=current_len,
                    ))
                    current_blocks = []
                    current_len = 0

                # code/table 独立成 section
                result.append(_Section(
                    section_path=list(section.section_path),
                    blocks=[block],
                    text_length=block_len,
                ))
                continue

            # text 块：累积，超长时切分
            if current_len + block_len > max_length and current_blocks:
                result.append(_Section(
                    section_path=list(section.section_path),
                    blocks=current_blocks,
                    text_length=current_len,
                ))
                current_blocks = []
                current_len = 0

            current_blocks.append(block)
            current_len += block_len
        
        # flush 残余
        if current_blocks:
            result.append(_Section(
                section_path=list(section.section_path),
                blocks=current_blocks,
                text_length=current_len,
            ))
    
    return result

def _merge_short_sections(
    sections: list[_Section],
    min_length: int,
) -> list[_Section]:
    """
    阶段3 : 将相邻的短 section 合并。

    合并条件：
      1. 两个相邻 section 的合并后总长度 <= max_content_length
      2. 两个 section 的 section_path 相同（属于同一章节）

    为什么要限制 section_path 相同？
      不同章节的内容合并会产生语义混乱。比如"第1章的最后一段"
      和"第2章的第一段"不应该合并，即使它们都很短。

    合并后使用第一个 section 的 section_path。
    """
    if not sections:
        return []

    s = get_settings()
    max_length = s.max_content_length

    merged : list[_Section] = [sections[0]]

    for section in sections[1:]:
        prev = merged[-1]

        # 判断是否可以合并
        can_merge = (
            prev.text_length < min_length
            and section.text_length < min_length
            and prev.text_length + section.text_length <= max_length
            and prev.section_path == section.section_path
        )

        if can_merge:
            # 合并到前一个 section
            prev.blocks.extend(section.blocks)
            prev.text_length += section.text_length
        else:
            merged.append(section)

    return merged
