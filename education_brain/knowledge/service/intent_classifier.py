"""意图分类。

当前版本收束为三类顶层意图：
- course_intro
- question_search
- knowledge

规则层只识别后端路径真正不同的两类结构化查询，
其余知识类问题统一落到 knowledge。
"""

import json
import logging
import re

from knowledge.core.config import get_settings
from knowledge.core.llm import chat_completion_text
from knowledge.models.intent import IntentResult
from knowledge.prompt.query_prompt import (
    INTENT_NORMALIZE_SYSTEM_PROMPT,
    INTENT_NORMALIZE_USER_PROMPT,
    INTENT_SYSTEM_PROMPT,
    INTENT_USER_PROMPT,
)

logger = logging.getLogger(__name__)

VALID_INTENTS = frozenset({
    "course_intro", "question_search", "knowledge",
})

# ── 关键词规则表 ──
# 每条规则: (intent, 正则模式列表)
# 匹配顺序 = 列表顺序，命中即返回
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("question_search", [
        r"(练习题|习题|试题|题库|编程题|选择题|判断题|简答题|多选题|单选题|填空题)",
        r"(题目|题库)",
        r"(做题|刷题|出题)",
        r"\bquestion(s)?\b",
    ]),
    ("course_intro", [
        r"^.+(课程|训练营|课|班)$",
        r"(有哪些|有没有|有啥|推荐|介绍).*(课程|课|班)",
        r"课程.*(推荐|介绍|查询|有哪些)",
        r"适合.*(课程|课|班|人群)",
        r"(在校生|职场人|求职者).*(课|学)",
        r"(零基础|入门|进阶).*(课程|课|班)",
        r"\bcourse(s)?\b",
    ]),
    ("knowledge", [
        r"(对比|比较).*(优劣|优缺点|区别|差异|不同)",
        r"(优劣|优缺点|区别|差异|不同).*(对比|比较)",
        r"(原理|机制|本质|思路|原因|为什么|为何|公式)",
        r"(什么是|解释一下|如何|怎么).+",
        r"\b(compare|comparison|why|difference|how)\b",
    ]),
]

_QUESTION_TYPE_PATTERNS = [
    "选择题",
    "单选题",
    "多选题",
    "判断题",
    "编程题",
    "简答题",
    "填空题",
]

_COURSE_STOPWORDS = [
    "有哪些", "有没有", "有啥", "有什么", "什么", "推荐", "介绍", "相关", "课程", "课", "班", "适合", "学习路线",
    "for", "course", "courses",
]
_QUESTION_STOPWORDS = [
    "有没有", "给我看看", "给我找", "查一下", "查找", "搜索", "关于", "相关", "的",
    "题目", "题库", "练习题", "习题", "试题", "刷题", "做题",
    "当前", "目前", "现在", "都有哪些", "有哪些", "都有什么", "有什么",
    "所有", "全部", "列出", "显示", "列表",
    "有吗", "有没有", "有没", "能不能", "可以吗",
    "给我几道", "给我几题", "来几道", "来几题", "几道", "几题",
    "课程", "课", "这门",
]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ，,。！？?!.")


def _strip_stopwords(text: str, stopwords: list[str]) -> str:
    value = text
    for token in sorted(stopwords, key=len, reverse=True):
        if re.fullmatch(r"[A-Za-z_]+", token):
            pattern = rf"\b{re.escape(token)}\b"
        else:
            pattern = re.escape(token)
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(related|about)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[的相关吗呢吧呀请给我看查找搜索一下里都有]", " ", value)
    return _normalize_whitespace(value)


def _extract_course_slots(query: str) -> dict[str, str]:
    keyword = _strip_stopwords(query, _COURSE_STOPWORDS)
    return {"keyword": keyword} if keyword else {}


def _extract_question_slots(query: str) -> dict[str, str]:
    slots: dict[str, str] = {}
    keyword_query = query
    for pattern in _QUESTION_TYPE_PATTERNS:
        if pattern in query:
            slots["question_type"] = pattern
            keyword_query = keyword_query.replace(pattern, " ")
            break
    keyword = _strip_stopwords(keyword_query, _QUESTION_STOPWORDS)
    if keyword:
        slots["keyword"] = keyword
    return slots


def _extract_slots(intent: str, query: str) -> dict[str, str]:
    if intent == "course_intro":
        return _extract_course_slots(query)
    if intent == "question_search":
        return _extract_question_slots(query)
    return {}


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_llm_result(payload: str | None) -> IntentResult | None:
    if not payload:
        return None
    cleaned = _strip_markdown_fences(payload)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM 返回非 JSON，fallback knowledge: %r", payload)
        return None

    intent = str(data.get("intent", "")).strip().lower()
    if intent not in VALID_INTENTS:
        logger.warning("LLM 返回无效意图 %r，fallback knowledge", intent)
        return None

    raw_slots = data.get("slots", {})
    slots = {
        str(key): str(value).strip()
        for key, value in raw_slots.items()
        if str(value).strip()
    } if isinstance(raw_slots, dict) else {}

    return IntentResult(intent=intent, slots=slots, confidence="llm")


def _parse_normalized_query_result(payload: str | None) -> dict[str, dict | str] | None:
    if not payload:
        return None

    cleaned = _strip_markdown_fences(payload)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("前置规范化返回非 JSON，回退原问题: %r", payload)
        return None

    normalized_query = _normalize_whitespace(str(data.get("normalized_query", "")))
    if not normalized_query:
        return None

    hints: dict[str, str] = {}
    raw_hints = data.get("hints", {})
    if isinstance(raw_hints, dict):
        hinted_intent = str(raw_hints.get("intent", "")).strip().lower()
        if hinted_intent in VALID_INTENTS:
            hints["intent"] = hinted_intent

        question_type = str(raw_hints.get("question_type", "")).strip()
        if question_type in _QUESTION_TYPE_PATTERNS:
            hints["question_type"] = question_type

    return {
        "normalized_query": normalized_query,
        "hints": hints,
    }


def normalize_query_for_intent(query: str) -> dict[str, dict | str]:
    normalized_query = _normalize_whitespace(query)
    if not normalized_query:
        return {"normalized_query": "", "hints": {}}

    s = get_settings()
    if not s.openai_api_key or not s.llm_model:
        return {"normalized_query": normalized_query, "hints": {}}

    rewritten = _parse_normalized_query_result(
        chat_completion_text(
            model=s.llm_model,
            messages=[
                {"role": "system", "content": INTENT_NORMALIZE_SYSTEM_PROMPT},
                {"role": "user", "content": INTENT_NORMALIZE_USER_PROMPT.format(query=normalized_query)},
            ],
            purpose="意图前置规范化",
            temperature=0.0,
            max_tokens=160,
            trigger_cooldown=False,
        )
    )
    if rewritten is not None:
        logger.info(
            "意图前置规范化完成: original=%r normalized=%r hints=%s",
            normalized_query[:50],
            rewritten["normalized_query"][:80],
            rewritten.get("hints", {}),
        )
        return rewritten

    logger.info(
        "意图前置规范化回退原问题: original=%r normalized=%r hints={}",
        normalized_query[:50],
        normalized_query[:80],
    )
    return {"normalized_query": normalized_query, "hints": {}}


def classify_intent(query: str) -> IntentResult:
    """对用户问题做意图分类并抽取基础槽位。"""
    original_query = _normalize_whitespace(query)
    rewrite_result = normalize_query_for_intent(original_query)
    normalized_query = str(rewrite_result.get("normalized_query") or original_query)
    hint_question_type = str((rewrite_result.get("hints") or {}).get("question_type", "")).strip()

    for intent, patterns in _KEYWORD_RULES:
        for pattern in patterns:
            if re.search(pattern, normalized_query, re.IGNORECASE):
                slots = _extract_slots(intent, normalized_query)
                if intent == "question_search" and hint_question_type and "question_type" not in slots:
                    slots["question_type"] = hint_question_type
                result = IntentResult(
                    intent=intent,
                    slots=slots,
                    confidence="rule",
                )
                logger.info(
                    "意图分类完成: original=%r normalized=%r intent=%s slots=%s confidence=%s",
                    original_query[:50],
                    normalized_query[:80],
                    result.intent,
                    result.slots,
                    result.confidence,
                )
                return result

    # ── 第二层：LLM fallback ──
    s = get_settings()
    if not s.openai_api_key or not s.llm_model:
        logger.info("LLM 未配置，默认 knowledge")
        return IntentResult(intent="knowledge", slots={}, confidence="default")
    
    result = _parse_llm_result(chat_completion_text(
        model=s.llm_model,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": INTENT_USER_PROMPT.format(query=normalized_query)},
        ],
        purpose="意图分类 LLM 调用",
        temperature=0.0,
        max_tokens=120,
    ))
    if result is not None:
        logger.info(
            "意图分类完成: original=%r normalized=%r intent=%s slots=%s confidence=%s",
            original_query[:50],
            normalized_query[:80],
            result.intent,
            result.slots,
            result.confidence,
        )
        return result

    fallback = IntentResult(intent="knowledge", slots={}, confidence="default")
    logger.info(
        "意图分类完成: original=%r normalized=%r intent=%s slots=%s confidence=%s",
        original_query[:50],
        normalized_query[:80],
        fallback.intent,
        fallback.slots,
        fallback.confidence,
    )
    return fallback
