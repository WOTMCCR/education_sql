# knowledge/tests/test_catalog_parser.py
"""快速验证课程目录解析器"""

from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "数据" / "课程介绍.md"


def test_parse_catalog():
    from knowledge.processor.catalog_parser import parse_catalog

    if not DATA_FILE.exists():
        pytest.skip(f"Fixture file is not present in this checkout: {DATA_FILE}")

    series_list, module_list = parse_catalog(DATA_FILE)

    # PLAN.md 验证点: 219 个系列, 657 个模块
    print(f"系列数: {len(series_list)}")
    print(f"模块数: {len(module_list)}")

    # 抽查第一个系列
    s0 = series_list[0]
    print(f"\n第一个系列: {s0.title}")
    print(f"  编码: {s0.series_code}")
    print(f"  分类: {s0.category_path}")
    print(f"  人群: {s0.audience}")
    print(f"  描述: {s0.description}")
    print(f"  目标: {s0.goal_tags}")

    # 抽查第一个模块
    m0 = module_list[0]
    print(f"\n第一个模块: {m0.module_title}")
    print(f"  编码: {m0.module_code}")
    print(f"  课时: {m0.lesson_count}, 学时: {m0.study_hours}")
    print(f"  排序: {m0.sort_order}")
    print(f"  描述: {m0.module_desc}")

    # 抽查最后一个系列
    s_last = series_list[-1]
    print(f"\n最后一个系列: {s_last.title}")
    print(f"  编码: {s_last.series_code}")

    assert len(series_list) == 219, f"期望 219 个系列，实际 {len(series_list)}"
    assert len(module_list) == 657, f"期望 657 个模块，实际 {len(module_list)}"

    # 每个系列都有 series_code
    for s in series_list:
        assert s.series_code, f"系列 '{s.title}' 缺少 series_code"

    # 每个模块都有 module_code 和 series_code
    for m in module_list:
        assert m.module_code, f"模块 '{m.module_title}' 缺少 module_code"
        assert m.series_code, f"模块 '{m.module_title}' 缺少 series_code"

    print("\n✓ 全部通过")


if __name__ == "__main__":
    test_parse_catalog()
