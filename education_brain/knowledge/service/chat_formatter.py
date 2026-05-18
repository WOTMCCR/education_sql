from knowledge.models.chat import ChatResponse


def build_course_search_summary(*, keyword: str, items: list[dict]) -> str:
    if not items:
        keyword_text = keyword or "这个方向"
        return (
            f"这次没找到完全匹配 {keyword_text} 的课程。"
            "你可以试试换个关键词，或者只搜更宽一点的方向词，我再帮你继续筛。"
        )

    direct_match_levels = {"title", "description", "category"}
    has_direct_match = any(item.get("match_level") in direct_match_levels for item in items)

    if keyword:
        if has_direct_match:
            intro = f"先给你找到 {len(items)} 门和 {keyword} 直接相关的课程："
        else:
            intro = f"没找到完全同名的 {keyword} 课程，不过先给你整理了 {len(items)} 门包含相关内容的课程："
    else:
        intro = f"先给你整理了 {len(items)} 门可参考的课程："

    lines = [intro, ""]
    for item in items:
        lines.append(f"**{item.get('title', '')}**")
        if item.get("description"):
            lines.append(f"  {item['description']}")
        if item.get("audience"):
            audience = item["audience"]
            audience_text = "、".join(audience) if isinstance(audience, list) else str(audience)
            lines.append(f"  适合人群：{audience_text}")
        if item.get("match_level") == "module" and item.get("matched_modules"):
            lines.append(f"  匹配模块：{'、'.join(item['matched_modules'])}")

    return "\n".join(lines)


def build_question_search_summary(*, keyword: str, question_type: str, items: list[dict]) -> str:
    if not items:
        requested_type = question_type or "题目"
        keyword_hint = f"“{keyword}”" if keyword else "当前条件"
        return (
            f"当前没检到 {keyword_hint} 对应的{requested_type}。"
            "你可以试试只搜关键词，或者换成单选题/多选题/判断题再查一次。"
        )

    type_text = question_type or "题目"
    if keyword:
        intro = f"先给你 {len(items)} 道和 {keyword} 相关的{type_text}："
    else:
        intro = f"先给你 {len(items)} 道{type_text}："

    lines = [intro]
    for question in items:
        lines.append(f"**[{question.get('question_type', '')}]** {question.get('stem', '')[:100]}")
    return "\n".join(lines)


def format_search_response(
    *,
    task_id: str,
    intent: str,
    items: list[dict],
    summary: str,
    citations: list[dict] | None = None,
) -> ChatResponse:
    return ChatResponse(
        task_id=task_id,
        intent=intent,
        result_type="search_result",
        items=items,
        summary=summary,
        answer=summary,
        citations=citations or [],
    )


def format_answer_response(
    *,
    task_id: str,
    intent: str,
    answer: str,
    citations: list[dict] | None = None,
) -> ChatResponse:
    return ChatResponse(
        task_id=task_id,
        intent=intent,
        result_type="answer",
        answer=answer,
        citations=citations or [],
    )
