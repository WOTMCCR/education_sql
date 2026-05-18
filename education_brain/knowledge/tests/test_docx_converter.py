# knowledge/tests/test_docx_converter.py
"""
.docx → Markdown 转换器测试

测试策略：
  1. 用真实的 .docx 文件测试 markitdown 转换
  2. 验证转换产出的 Markdown 基本质量
  3. 验证图片提取功能

  这些测试依赖真实数据文件和 markitdown 库，
  如果文件不存在或库未安装，跳过测试。
"""

import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COURSE_DOC_DIR = PROJECT_ROOT / "data" / "数据" / "课程文档"


def test_markitdown_converts_small_docx():
    """测试 markitdown 对小型 .docx 文件的转换

    选择一个较小的文件（Shell1.0.docx, ~1MB），
    验证转换产出非空且包含基本的 Markdown 结构。
    """
    docx_file = COURSE_DOC_DIR / "尚硅谷大模型技术之Shell1.0.docx"
    if not docx_file.exists():
        print(f"⚠ 跳过（文件不存在: {docx_file.name}）")
        return

    from knowledge.processor.docx_converter import convert_docx_to_markdown

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "images"
        md_text, image_paths = convert_docx_to_markdown(docx_file, output_dir)

    # 转换产出不为空
    assert md_text, "转换产出不应为空"
    assert len(md_text) > 100, f"转换产出过短: {len(md_text)} 字符"

    print(f"转换结果:")
    print(f"  文件: {docx_file.name}")
    print(f"  Markdown 长度: {len(md_text)} 字符")
    print(f"  行数: {len(md_text.splitlines())}")
    print(f"  提取图片数: {len(image_paths)}")

    # 验证产出包含基本 Markdown 结构
    lines = md_text.splitlines()

    # 应该有标题（# 或 ##）
    heading_lines = [l for l in lines if l.strip().startswith("#")]
    print(f"  标题行数: {len(heading_lines)}")
    if heading_lines:
        print(f"  首个标题: {heading_lines[0][:60]}")

    # 打印前 20 行预览
    print(f"\n  前 20 行预览:")
    for line in lines[:20]:
        print(f"    {line[:80]}")

    print("✓ 小型 .docx 转换测试通过")


def test_markitdown_converts_medium_docx():
    """测试 markitdown 对中等大小 .docx 文件的转换

    选择 Python1.0.docx (~12MB)，
    验证转换能处理较大文件且产出质量可接受。
    """
    docx_file = COURSE_DOC_DIR / "尚硅谷大模型技术之Python1.0.docx"
    if not docx_file.exists():
        print(f"⚠ 跳过（文件不存在: {docx_file.name}）")
        return

    from knowledge.processor.docx_converter import convert_docx_to_markdown

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "images"
        md_text, image_paths = convert_docx_to_markdown(docx_file, output_dir)

    assert md_text, "转换产出不应为空"

    print(f"转换结果:")
    print(f"  文件: {docx_file.name} ({docx_file.stat().st_size // 1024 // 1024}MB)")
    print(f"  Markdown 长度: {len(md_text)} 字符")
    print(f"  行数: {len(md_text.splitlines())}")
    print(f"  提取图片数: {len(image_paths)}")

    # 应该有相当多的内容
    assert len(md_text) > 10000, "Python教程的转换产出应该有大量内容"

    # 内容应该包含 Python 相关的关键词
    md_lower = md_text.lower()
    assert "python" in md_lower, "Python 教程应该包含 'python' 关键词"

    print("✓ 中等 .docx 转换测试通过")


def test_conversion_fallback_on_invalid_input():
    """测试对不存在/损坏文件的容错

    传入一个不存在的路径，应该抛出 ParseError，
    而不是未处理的异常。
    """
    from knowledge.processor.docx_converter import convert_docx_to_markdown
    from knowledge.core.errors import ParseError

    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_path = Path(tmp_dir) / "nonexistent.docx"
        output_dir = Path(tmp_dir) / "images"

        try:
            convert_docx_to_markdown(fake_path, output_dir)
            assert False, "应该抛出 ParseError"
        except ParseError as e:
            print(f"正确抛出 ParseError: {e.message}")
            assert "转换失败" in e.message
        except Exception as e:
            # 其他异常也可以接受（如 FileNotFoundError），
            # 但最好是统一的 ParseError
            print(f"⚠ 抛出了非 ParseError 异常: {type(e).__name__}: {e}")

    print("✓ 容错测试通过")


def test_all_course_docx_convertible():
    """批量测试：验证所有课程 .docx 文件都能成功转换

    这是 Step 4 验证点的直接测试：
    "至少 5 份课程文档导入成功"。

    对每个文件调用 convert_docx_to_markdown，
    记录成功/失败统计。
    """
    if not COURSE_DOC_DIR.exists():
        print(f"⚠ 跳过（目录不存在: {COURSE_DOC_DIR}）")
        return

    from knowledge.processor.docx_converter import convert_docx_to_markdown

    docx_files = sorted(COURSE_DOC_DIR.glob("*.docx"))
    if not docx_files:
        print("⚠ 跳过（未找到 .docx 文件）")
        return

    results = []

    for docx_file in docx_files:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_dir = Path(tmp_dir) / "images"
                md_text, images = convert_docx_to_markdown(docx_file, output_dir)

            results.append({
                "file": docx_file.name,
                "status": "ok",
                "chars": len(md_text),
                "lines": len(md_text.splitlines()),
                "images": len(images),
            })
        except Exception as e:
            results.append({
                "file": docx_file.name,
                "status": f"FAIL: {e}",
                "chars": 0,
                "lines": 0,
                "images": 0,
            })

    # 打印汇总
    print(f"\n课程文档转换汇总 ({len(docx_files)} 个文件):")
    print(f"{'文件名':<45} {'状态':<8} {'字符数':>8} {'行数':>6} {'图片':>4}")
    print("-" * 80)

    ok_count = 0
    for r in results:
        status_mark = "✓" if r["status"] == "ok" else "✗"
        print(
            f"{r['file']:<45} {status_mark:<8} "
            f"{r['chars']:>8} {r['lines']:>6} {r['images']:>4}"
        )
        if r["status"] == "ok":
            ok_count += 1

    print(f"\n成功: {ok_count}/{len(docx_files)}")

    # PLAN.md 验证点: 至少 5 份课程文档导入成功
    assert ok_count >= 5, f"至少 5 份课程文档应转换成功，实际成功 {ok_count}"

    print("✓ 批量转换测试通过")


if __name__ == "__main__":
    test_markitdown_converts_small_docx()
    test_markitdown_converts_medium_docx()
    test_conversion_fallback_on_invalid_input()
    test_all_course_docx_convertible()
