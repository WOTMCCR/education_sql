"""
.docx → Markdown 转换器

为什么不直接用 python-docx 解析？
  python-docx 能读取段落文本，但代码块识别需要启发式规则
  （等宽字体检测、缩进模式识别），样式丢失严重时需要降级到
  OOXML 级解析，链路复杂且脆弱。

  先转成 Markdown，再走统一解析链路：
  - 标题 → # / ## / ###
  - 代码块 → ``` 围栏
  - 表格 → Markdown 表格语法
  不再需要启发式格式识别。

转换策略（两级降级）：
  1. markitdown（微软开源）：纯 Python，API 简单
  2. pandoc（社区成熟）：转换质量最高，但需要系统级安装

图片处理：
  markitdown 在转换时会将 .docx 内嵌图片提取到临时目录，
  并在 Markdown 中生成 ![](images/xxx.png) 引用。
  pandoc 通过 --extract-media 参数实现同样的功能。
"""


import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from knowledge.core.config import get_settings
from knowledge.core.errors import ParseError

logger = logging.getLogger(__name__)

def convert_docx_to_markdown(
    docx_path: Path,
    output_dir: Path,
) -> tuple[str, list[Path]]:
    """
    将 .docx 文件转换为 Markdown 文本，并提取内嵌图片。

    参数：
        docx_path:  源 .docx 文件路径
        output_dir: 图片导出目录（转换器会将图片放到这个目录下）

    返回：
        (markdown_text, image_paths)
        - markdown_text: 转换后的 Markdown 文本
        - image_paths:   提取出的图片文件路径列表

    异常：
        ParseError: 所有转换方式都失败时抛出

    降级顺序：
        markitdown → pandoc → 抛异常
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 第一级：markitdown ──
    md_text = _try_markitdown(docx_path)
    if md_text:
        images = _collect_images(output_dir)
        logger.info(
            "markitdown 转换成功: %s (%d 字符, %d 张图片)",
            docx_path.name, len(md_text), len(images),
        )
        return md_text, images

    # ── 第二级：pandoc ──
    s = get_settings()
    if s.docx_fallback_pandoc:
        md_text = _try_pandoc(docx_path, output_dir)
        if md_text:
            images = _collect_images(output_dir)
            logger.info(
                "pandoc 降级转换成功: %s (%d 字符, %d 张图片)",
                docx_path.name, len(md_text), len(images),
            )
            return md_text, images

    raise ParseError(
        message=f"文档转换失败: {docx_path.name}",
        detail="markitdown 和 pandoc 均无法转换此文件",
    )

def _try_markitdown(docx_path: Path) -> str | None:
    """
    用 markitdown 转换 .docx → Markdown。

    markitdown 是微软开源的 Python 库，支持多种格式转换。
    它内部使用 python-docx 读取文档结构，然后输出 Markdown。

    为什么用 try/except 包裹？
      markitdown 对某些 .docx 格式可能报错（如含有特殊 OLE 对象），
      我们不希望一个文件的失败阻断整个导入流程。
    """
    try:
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert(str(docx_path))
        text = result.text_content

        # 转换产出为空视为失败（markitdown 有时对损坏文件返回空串）
        if not text or not text.strip():
            logger.warning("markitdown 转换产出为空: %s", docx_path.name)
            return None

        return text

    except Exception as e:
        logger.warning("markitdown 转换失败: %s — %s", docx_path.name, e)
        return None
def _try_pandoc(docx_path: Path, image_dir: Path) -> str | None:
    """
    用 pandoc 转换 .docx → Markdown。

    pandoc 是命令行工具（非 Python 包），通过子进程调用。
    --extract-media 参数让 pandoc 将 .docx 内嵌的图片
    解压到指定目录，并在 Markdown 中生成相对路径引用。

    参数说明：
      -f docx          输入格式：Word 文档
      -t markdown      输出格式：Markdown
      --wrap=none      不自动换行（保留原始段落结构）
      --extract-media  图片导出目录
    """
    # 先检查 pandoc 是否安装
    if not shutil.which("pandoc"):
        logger.warning("pandoc 未安装，跳过降级转换")
        return None

    try:
        result = subprocess.run(
            [
                "pandoc",
                str(docx_path),
                "-f", "docx",
                "-t", "markdown",
                "--wrap=none",
                f"--extract-media={image_dir}",
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 大文件可能需要较长时间
        )

        if result.returncode != 0:
            logger.warning(
                "pandoc 转换失败 (exit=%d): %s — %s",
                result.returncode, docx_path.name, result.stderr[:200],
            )
            return None

        text = result.stdout
        if not text or not text.strip():
            logger.warning("pandoc 转换产出为空: %s", docx_path.name)
            return None

        return text

    except subprocess.TimeoutExpired:
        logger.warning("pandoc 转换超时: %s", docx_path.name)
        return None
    except Exception as e:
        logger.warning("pandoc 转换异常: %s — %s", docx_path.name, e)
        return None

def _collect_images(image_dir: Path) -> list[Path]:
    """
    收集目录下所有图片文件。

    markitdown 和 pandoc 导出的图片可能在不同的子目录结构中，
    用 rglob 递归搜索所有图片文件。

    IMAGE_EXTENSIONS 定义在 config.py 中，
    是一个 frozenset: {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    """
    from knowledge.core.config import IMAGE_EXTENSIONS

    if not image_dir.exists():
        return []
    
    images = [
        p for p in image_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(images)