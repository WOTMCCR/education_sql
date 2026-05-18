from knowledge.service import chat_formatter
from knowledge.service.chat_formatter import format_answer_response, format_search_response


def test_format_search_response_keeps_backward_compatible_answer():
    response = format_search_response(
        task_id="task-1",
        intent="course_intro",
        items=[{"title": "Python 基础"}],
        summary="找到 1 门课程",
    )

    assert response.result_type == "search_result"
    assert response.summary == "找到 1 门课程"
    assert response.answer == "找到 1 门课程"
    assert response.items == [{"title": "Python 基础"}]
    assert response.citations == []


def test_format_answer_response_separates_answer_and_citations():
    response = format_answer_response(
        task_id="task-2",
        intent="knowledge",
        answer="这是回答",
        citations=[{"index": 1, "doc_title": "PyTorch 指南"}],
    )

    assert response.result_type == "answer"
    assert response.answer == "这是回答"
    assert response.summary == ""
    assert response.items == []
    assert response.citations == [{"index": 1, "doc_title": "PyTorch 指南"}]


def test_build_course_search_summary_uses_assistant_tone_for_direct_match():
    summary = chat_formatter.build_course_search_summary(
        keyword="Python",
        items=[
            {
                "title": "Python 基础",
                "description": "覆盖语法、函数和常用库",
                "audience": ["零基础", "转行"],
                "match_level": "title",
            }
        ],
    )

    assert summary.startswith("先给你找到")
    assert "Python" in summary
    assert "Python 基础" in summary
    assert "适合人群：零基础、转行" in summary


def test_build_course_search_summary_no_result_suggests_next_action():
    summary = chat_formatter.build_course_search_summary(keyword="大模型开发", items=[])

    assert "没找到完全匹配" in summary
    assert "换个关键词" in summary or "试试" in summary


def test_build_question_search_summary_acknowledges_requested_type():
    summary = chat_formatter.build_question_search_summary(
        keyword="Python",
        question_type="多选题",
        items=[
            {
                "question_type": "多选题",
                "stem": "关于递归，哪些说法是正确的？",
            }
        ],
    )

    assert summary.startswith("先给你")
    assert "多选题" in summary
    assert "关于递归，哪些说法是正确的？" in summary


def test_build_question_search_summary_no_result_suggests_relaxing_filters():
    summary = chat_formatter.build_question_search_summary(
        keyword="大模型开发",
        question_type="多选题",
        items=[],
    )

    assert "当前没检到" in summary
    assert "单选" in summary or "判断" in summary or "只搜关键词" in summary
