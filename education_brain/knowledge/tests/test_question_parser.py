# knowledge/tests/test_question_parser.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "数据" / "题目资料.md"

def test_parse_questions():
    from knowledge.processor.question_parser import parse_questions

    banks, items = parse_questions(DATA_FILE)

    print(f"题库数: {len(banks)}")
    print(f"题目数: {len(items)}")

    # PLAN.md 验证点: 73 个题库, 1752 道题
    assert len(banks) == 73, f"期望 73 个题库，实际 {len(banks)}"
    assert len(items) == 1752, f"期望 1752 个题目，实际 {len(items)}"

    # 抽查: 第一个单选题
    q1 = items[0]
    print(f"\n第一题: {q1.question_code}")
    print(f"  题型: {q1.question_type}")
    print(f"  题干: {q1.stem[:50]}...")
    print(f"  选项数: {len(q1.options)}")
    print(f"  answer_key: {q1.answer_key}")


    # 抽查: 找一个多选题
    multi = next(q for q in items if q.question_type == "多选题")
    print(f"\n多选题: {multi.question_code}")
    print(f"  answer_key: {multi.answer_key}")
    assert "," in multi.answer_key, "多选答案应该用逗号分隔"

    # 抽查: 找一个简答题
    essay = next(q for q in items if q.question_type == "简答题")
    print(f"\n简答题: {essay.question_code}")
    print(f"  answer_key: '{essay.answer_key}' (应为空)")
    print(f"  reference_answer: {essay.reference_answer[:50]}...")
    assert essay.answer_key == "", "简答题不应有 answer_key"
    assert essay.reference_answer, "简答题应有 reference_answer"

    # 质量标记统计
    flagged = [q for q in items if q.quality_flags]
    print(f"\n有质量标记的题目: {len(flagged)}")
    for q in flagged[:5]:
        print(f"  {q.question_code}: {q.quality_flags}")

    # 每个题都有 raw_block
    for q in items:
        assert q.raw_block, f"{q.question_code} 缺少 raw_block"

    print("\n✓ 全部通过")

if __name__ == "__main__":
    test_parse_questions()