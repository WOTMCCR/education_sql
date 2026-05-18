"""Markdown 解析器测试。"""

from knowledge.processor.markdown_parser import parse_markdown


def _print_blocks(label: str, blocks: list) -> None:
    print(f"\n=== {label} ===")
    for idx, block in enumerate(blocks):
        preview = block.content.replace("\n", "\\n")
        if len(preview) > 80:
            preview = f"{preview[:77]}..."
        print(
            f"[{idx}] kind={block.kind} "
            f"level={block.heading_level} "
            f"path={block.section_path} "
            f"lang={block.code_language or '-'} "
            f"images={block.image_paths or '-'} "
            f"content={preview}"
        )


def test_heading_levels_and_section_path():
    md = """\
# 第1章 Python基础
一些介绍文字
## 1.1 变量与类型
变量内容
### 1.1.1 整数类型
整数内容
## 1.2 控制流
控制流内容
"""

    blocks = parse_markdown(md)
    headings = [b for b in blocks if b.kind == "heading"]
    texts = [b for b in blocks if b.kind == "text"]

    assert [b.heading_level for b in headings] == [1, 2, 3, 2]
    assert [b.content for b in headings] == [
        "第1章 Python基础",
        "1.1 变量与类型",
        "1.1.1 整数类型",
        "1.2 控制流",
    ]
    assert [b.section_path for b in texts] == [
        ["第1章 Python基础"],
        ["第1章 Python基础", "1.1 变量与类型"],
        ["第1章 Python基础", "1.1 变量与类型", "1.1.1 整数类型"],
        ["第1章 Python基础", "1.2 控制流"],
    ]


def test_code_block_recognition():
    md = """\
## 示例代码

下面是一段 Python 代码：

```python
def hello():
    # 这是注释，不是 heading
    print("## 这不是标题")
    return True
```

这是代码后面的文字。

```
plain code without language
```
"""

    blocks = parse_markdown(md)
    _print_blocks("code_block_recognition", blocks)
    codes = [b for b in blocks if b.kind == "code"]
    headings = [b for b in blocks if b.kind == "heading"]
    texts = [b for b in blocks if b.kind == "text"]

    assert len(codes) == 2
    assert codes[0].code_language == "python"
    assert "def hello():" in codes[0].content
    assert 'print("## 这不是标题")' in codes[0].content
    assert codes[0].section_path == ["示例代码"]

    assert codes[1].code_language == ""
    assert "plain code without language" in codes[1].content
    assert codes[1].section_path == ["示例代码"]

    assert [b.content for b in headings] == ["示例代码"]
    assert [b.content for b in texts] == [
        "下面是一段 Python 代码：",
        "这是代码后面的文字。",
    ]


def test_table_recognition():
    md = """\
# 技术选型
下面是对比表：

| 工具 | 优势 | 劣势 |
| --- | --- | --- |
| markitdown | Python 原生 | 复杂表格弱 |
| pandoc | 质量最高 | 需要系统安装 |

表格之后的文字。
"""

    blocks = parse_markdown(md)
    tables = [b for b in blocks if b.kind == "table"]
    texts = [b for b in blocks if b.kind == "text"]

    assert len(tables) == 1
    assert tables[0].section_path == ["技术选型"]
    assert tables[0].content.splitlines() == [
        "| 工具 | 优势 | 劣势 |",
        "| --- | --- | --- |",
        "| markitdown | Python 原生 | 复杂表格弱 |",
        "| pandoc | 质量最高 | 需要系统安装 |",
    ]
    assert [b.content for b in texts] == ["下面是对比表：", "表格之后的文字。"]


def test_image_reference_extraction():
    md = """\
# 架构图
系统整体架构如下：

![整体架构](images/architecture.png)

数据流向：

![数据流](images/dataflow.jpg)
"""

    blocks = parse_markdown(md)
    _print_blocks("image_reference_extraction", blocks)
    blocks_with_images = [b for b in blocks if b.image_paths]

    assert len(blocks_with_images) == 1
    assert blocks_with_images[0].kind == "text"
    assert blocks_with_images[0].section_path == ["架构图"]
    assert blocks_with_images[0].image_paths == [
        "images/architecture.png",
        "images/dataflow.jpg",
    ]


def test_mixed_content():
    md = """\
# 深度学习基础
## 1. 神经网络
神经网络由多个层组成。

### 1.1 前向传播
前向传播的公式：

```python
def forward(x, w, b):
    return x @ w + b
```

结果如下表：

| 层 | 输入 | 输出 |
| --- | --- | --- |
| Linear | 784 | 128 |

### 1.2 反向传播
反向传播计算梯度。
"""

    blocks = parse_markdown(md)
    _print_blocks("mixed_content", blocks)
    kinds = [b.kind for b in blocks]
    code = next(b for b in blocks if b.kind == "code")
    table = next(b for b in blocks if b.kind == "table")
    last_text = [b for b in blocks if b.kind == "text"][-1]

    assert kinds == [
        "heading",
        "heading",
        "text",
        "heading",
        "text",
        "code",
        "text",
        "table",
        "heading",
        "text",
    ]
    assert code.section_path == ["深度学习基础", "1. 神经网络", "1.1 前向传播"]
    assert table.section_path == ["深度学习基础", "1. 神经网络", "1.1 前向传播"]
    assert last_text.section_path == [
        "深度学习基础",
        "1. 神经网络",
        "1.2 反向传播",
    ]


def test_unclosed_code_block():
    md = """\
# 示例

```python
def foo():
    pass
"""

    blocks = parse_markdown(md)
    codes = [b for b in blocks if b.kind == "code"]

    assert len(codes) == 1
    assert codes[0].code_language == "python"
    assert codes[0].section_path == ["示例"]
    assert "def foo():" in codes[0].content
