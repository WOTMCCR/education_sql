import re

from knowledge.core.clients import get_mongo_db


QUESTION_TYPE_ALIASES: dict[str, list[str]] = {
    "选择题": ["选择题", "单选题", "多选题"],
    "单选题": ["单选题"],
    "多选题": ["多选题"],
    "判断题": ["判断题"],
    "填空题": ["填空题"],
    "简答题": ["简答题"],
    "编程题": ["编程题"],
}


def expand_question_types(question_type: str) -> list[str]:
    if not question_type:
        return []
    return QUESTION_TYPE_ALIASES.get(question_type, [question_type])


def search_questions(
    *,
    keyword: str = "",
    bank_code: str = "",
    question_type: str = "",
    page: int = 1,
    size: int = 20,
) -> dict:
    db = get_mongo_db()
    filters: list[dict] = []

    if bank_code:
        filters.append({"bank_code": bank_code})

    if question_type:
        aliases = expand_question_types(question_type)
        if len(aliases) == 1:
            filters.append({"question_type": aliases[0]})
        else:
            filters.append({"question_type": {"$in": aliases}})

    if keyword:
        filters.append({"stem": {"$regex": re.escape(keyword.strip()), "$options": "i"}})

    if not filters:
        query = {}
    elif len(filters) == 1:
        query = filters[0]
    else:
        query = {"$and": filters}

    skip = (page - 1) * size
    total = db["question_item"].count_documents(query)
    items = list(
        db["question_item"]
        .find(query, {"_id": 0})
        .skip(skip)
        .limit(size)
    )

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }
