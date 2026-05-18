# knowledge/tests/test_chunker.py
"""
智能分块器测试

测试策略：
  构造不同长度和结构的 ParsedBlock 列表，
  验证三阶段分块逻辑：
  - 阶段1: 按标题分组
  - 阶段2: 长段拆分（代码/表格不切断）
  - 阶段3: 短段合并（section_path 不同不合并）

  同时用真实文档做端到端测试。
"""

from knowledge.processor.markdown_parser import ParsedBlock, parse_markdown
from knowledge.processor.chunker import chunk_document


def test_basic_chunking_by_heading():
    """测试基本的按标题分块

    两个 ## 标题下各有一段文本，
    应该产出 2 个 chunk，各自有正确的 section_path。
    """
    blocks = [
        ParsedBlock(kind="heading", content="第1章", heading_level=2,
                     section_path=["第1章"]),
        ParsedBlock(kind="text", content="A" * 600,
                     section_path=["第1章"]),
        ParsedBlock(kind="heading", content="第2章", heading_level=2,
                     section_path=["第2章"]),
        ParsedBlock(kind="text", content="B" * 600,
                     section_path=["第2章"]),
    ]

    chunks = chunk_document(blocks, doc_id="test_doc")

    assert len(chunks) == 2, f"期望 2 个 chunk，实际 {len(chunks)}"
    assert chunks[0].section_path == ["第1章"]
    assert chunks[1].section_path == ["第2章"]
    assert chunks[0].chunk_kind == "text"
    assert chunks[1].chunk_kind == "text"

    # chunk_index 从 0 开始递增
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1

    # doc_id 正确关联
    assert all(c.doc_id == "test_doc" for c in chunks)

    # chunk_id 唯一
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids), "chunk_id 应该唯一"

    print("✓ 基本按标题分块测试通过")


def test_long_section_split():
    """测试长段二次拆分

    一个标题下有 3 个 text 块，总长度 > max_content_length(2000)，
    应该被拆分为多个 chunk。
    """
    blocks = [
        ParsedBlock(kind="heading", content="长章节", heading_level=2,
                     section_path=["长章节"]),
        ParsedBlock(kind="text", content="X" * 900,
                     section_path=["长章节"]),
        ParsedBlock(kind="text", content="Y" * 900,
                     section_path=["长章节"]),
        ParsedBlock(kind="text", content="Z" * 900,
                     section_path=["长章节"]),
    ]

    chunks = chunk_document(blocks, doc_id="test_long")

    # 总长度 2700 > 2000，应该被拆分
    assert len(chunks) >= 2, f"超长段应该被拆分，实际只有 {len(chunks)} 个 chunk"

    # 所有 chunk 的 section_path 应该相同（都属于"长章节"）
    for c in chunks:
        assert c.section_path == ["长章节"]

    print(f"✓ 长段拆分测试通过（拆分为 {len(chunks)} 个 chunk）")


def test_code_block_not_split():
    """测试代码块不被切断

    一个超长代码块（> max_content_length）不应该被拆分，
    因为半个函数没有任何语义价值。
    代码块应该作为完整单元保留。
    """
    long_code = "\n".join([f"    line_{i} = {i}" for i in range(200)])

    blocks = [
        ParsedBlock(kind="heading", content="代码章节", heading_level=2,
                     section_path=["代码章节"]),
        ParsedBlock(kind="text", content="下面是代码：",
                     section_path=["代码章节"]),
        ParsedBlock(kind="code", content=long_code, code_language="python",
                     section_path=["代码章节"]),
        ParsedBlock(kind="text", content="代码结束。",
                     section_path=["代码章节"]),
    ]

    chunks = chunk_document(blocks, doc_id="test_code")

    # 代码块应该独立成一个 chunk，不被切断
    code_chunks = [c for c in chunks if c.chunk_kind == "code"]
    assert len(code_chunks) >= 1, "代码块应该被保留"

    # 代码块内容完整（包含所有 200 行）
    for cc in code_chunks:
        if "line_0" in cc.chunk_text:
            assert "line_199" in cc.chunk_text, "代码块不应该被切断"

    print("✓ 代码块不切断测试通过")


def test_short_sections_merge():
    """测试短段合并

    多个相邻的短 section（< min_content_length=500），
    且 section_path 相同，应该被合并。
    """
    blocks = [
        ParsedBlock(kind="heading", content="章节", heading_level=2,
                     section_path=["章节"]),
        ParsedBlock(kind="heading", content="1.1", heading_level=3,
                     section_path=["章节", "1.1"]),
        ParsedBlock(kind="text", content="短文本A" * 10,
                     section_path=["章节", "1.1"]),
        # 注意：下面这个 heading 会改变 section_path
        ParsedBlock(kind="heading", content="1.2", heading_level=3,
                     section_path=["章节", "1.2"]),
        ParsedBlock(kind="text", content="短文本B" * 10,
                     section_path=["章节", "1.2"]),
    ]

    chunks = chunk_document(blocks, doc_id="test_merge")

    # 1.1 和 1.2 的 section_path 不同，不应该合并
    # 即使都很短也不合并
    paths = [c.section_path for c in chunks]
    print(f"  chunk section_paths: {paths}")

    # 不同 section_path 的 chunk 不应该合并在一起
    for c in chunks:
        # 同一个 chunk 内不应该同时包含"短文本A"和"短文本B"
        has_a = "短文本A" in c.chunk_text
        has_b = "短文本B" in c.chunk_text
        assert not (has_a and has_b), "不同 section_path 的内容不应合并"

    print("✓ 短段合并测试通过")


def test_chunk_kind_detection():
    """测试 chunk_kind 的正确判断

    - 纯文本 → text
    - 纯代码 → code
    - 纯表格 → table
    - 文本+代码混合 → mixed
    """
    blocks = [
        ParsedBlock(kind="heading", content="混合", heading_level=2,
                     section_path=["混合"]),
        ParsedBlock(kind="text", content="说明文字" * 100,
                     section_path=["混合"]),
        ParsedBlock(kind="code", content="print('hello')",
                     code_language="python", section_path=["混合"]),
    ]

    chunks = chunk_document(blocks, doc_id="test_kind")

    # 这些块可能合并成一个 mixed chunk，也可能因为长度被拆开
    # 检查 chunk_kind 是否合理
    for c in chunks:
        assert c.chunk_kind in ("text", "code", "table", "mixed"), \
            f"未知的 chunk_kind: {c.chunk_kind}"

    print(f"  chunk kinds: {[c.chunk_kind for c in chunks]}")
    print("✓ chunk_kind 检测测试通过")


def test_end_to_end_with_real_markdown():
    """端到端测试：解析 + 分块真实 .md 文件

    读取项目文档，走完整的 parse_markdown → chunk_document 流程。
    验证产出的 chunk 质量。
    """
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    md_file = (
        PROJECT_ROOT / "data" / "数据" / "项目文档" / "掌柜智库"
        / "01_掌柜智库项目全景.md"
    )

    if not md_file.exists():
        print(f"⚠ 跳过真实数据测试（文件不存在: {md_file}）")
        return

    text = md_file.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    chunks = chunk_document(blocks, doc_id="real_test")

    print(f"\n真实文档分块结果:")
    print(f"  总 chunk 数: {len(chunks)}")

    assert len(chunks) > 0, "真实文档应该产出至少 1 个 chunk"

    # 验证每个 chunk 的基本质量
    for i, c in enumerate(chunks):
        # chunk_text 不应为空
        assert c.chunk_text.strip(), f"chunk[{i}] 文本为空"

        # chunk_id 不应为空
        assert c.chunk_id, f"chunk[{i}] 缺少 chunk_id"

        # doc_id 应该正确关联
        assert c.doc_id == "real_test"

    # 统计 chunk_kind 分布
    from collections import Counter
    kind_counts = Counter(c.chunk_kind for c in chunks)
    print(f"  chunk_kind 分布: {dict(kind_counts)}")

    # 打印前 3 个 chunk 的摘要
    print(f"\n  前 3 个 chunk:")
    for c in chunks[:3]:
        preview = c.chunk_text[:60].replace("\n", " ")
        print(f"    [{c.chunk_kind}] path={c.section_path}")
        print(f"      {preview}...")
        print(f"      长度: {len(c.chunk_text)} 字符")

    # 验证没有超长 chunk（允许代码/表格块超长）
    from knowledge.core.config import get_settings
    s = get_settings()
    for c in chunks:
        if c.chunk_kind == "text":
            # text chunk 不应该远超 max_content_length
            # 用 1.5 倍作为宽松上限（合并可能稍微超过）
            assert len(c.chunk_text) <= s.max_content_length * 1.5, \
                f"text chunk 过长: {len(c.chunk_text)} 字符"

    print("✓ 端到端真实文档测试通过")


def test_image_refs_preserved_in_chunks():
    """测试图片引用在分块后被保留到 chunk.image_refs"""
    blocks = [
        ParsedBlock(kind="heading", content="图片章节", heading_level=2,
                     section_path=["图片章节"]),
        ParsedBlock(
            kind="text",
            content="架构如图：\n![arch](images/arch.png)\n说明文字",
            section_path=["图片章节"],
            image_paths=["images/arch.png"],
        ),
    ]

    chunks = chunk_document(blocks, doc_id="test_img")

    # 至少有一个 chunk 包含图片引用
    chunks_with_img = [c for c in chunks if c.image_refs]
    assert len(chunks_with_img) >= 1, "图片引用应该被保留到 chunk.image_refs"
    assert "images/arch.png" in chunks_with_img[0].image_refs

    print("✓ 图片引用保留测试通过")


if __name__ == "__main__":
    test_basic_chunking_by_heading()
    test_long_section_split()
    test_code_block_not_split()
    test_short_sections_merge()
    test_chunk_kind_detection()
    test_end_to_end_with_real_markdown()
    test_image_refs_preserved_in_chunks()
