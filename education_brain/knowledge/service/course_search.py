import re

from knowledge.core.clients import get_mongo_db

MATCH_LEVEL_PRIORITY = {
    "title": 0,
    "description": 1,
    "category": 2,
    "module": 3,
    "": 4,
}


def _build_base_query(*, audience: str, goal: str) -> dict:
    filters: list[dict] = []

    if audience:
        filters.append({"audience": audience})

    if goal:
        filters.append({"goal_tags": goal})

    if not filters:
        return {}
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def _merge_query(base_query: dict, extra_query: dict) -> dict:
    if not base_query:
        return extra_query
    if not extra_query:
        return base_query
    return {"$and": [base_query, extra_query]}


def _load_related_data(db, series: dict, *, matched_modules: list[str] | None = None, match_level: str = "") -> dict:
    series_code = series["series_code"]
    enriched = dict(series)
    enriched["match_level"] = match_level
    enriched["matched_modules"] = matched_modules or []
    enriched["modules"] = list(
        db["course_module"]
        .find({"series_code": series_code}, {"_id": 0})
        .sort("sort_order", 1)
    )
    enriched["related_documents"] = list(
        db["source_mapping"].find(
            {"series_code": series_code},
            {"_id": 0, "source_file": 1, "doc_id": 1, "mapping_type": 1, "series_code": 1},
        )
    )
    return enriched


def _search_courses_with_keyword(db, *, base_query: dict, keyword: str) -> list[dict]:
    escaped_keyword = re.escape(keyword.strip())
    regex = {"$regex": escaped_keyword, "$options": "i"}
    results: list[dict] = []
    seen_codes: set[str] = set()

    for field, match_level in (
        ("title", "title"),
        ("description", "description"),
        ("category_path", "category"),
    ):
        query = _merge_query(base_query, {field: regex})
        for series in db["course_series"].find(query, {"_id": 0}):
            series_code = series["series_code"]
            if series_code in seen_codes:
                continue
            seen_codes.add(series_code)
            results.append(_load_related_data(db, series, match_level=match_level))

    module_query = {
        "$or": [
            {"module_title": regex},
            {"module_desc": regex},
        ]
    }
    grouped_modules: dict[str, list[dict]] = {}
    for module in db["course_module"].find(module_query, {"_id": 0}):
        grouped_modules.setdefault(module["series_code"], []).append(module)

    module_codes = [code for code in grouped_modules if code not in seen_codes]
    if not module_codes:
        return results

    series_query = _merge_query(base_query, {"series_code": {"$in": module_codes}})
    module_series = {
        series["series_code"]: series
        for series in db["course_series"].find(series_query, {"_id": 0})
    }
    for series_code in module_codes:
        series = module_series.get(series_code)
        if not series:
            continue
        matched_modules = grouped_modules[series_code]
        matched_modules.sort(key=lambda item: item.get("sort_order", 0))
        results.append(
            _load_related_data(
                db,
                series,
                match_level="module",
                matched_modules=[module.get("module_title", "") for module in matched_modules if module.get("module_title")],
            )
        )

    results.sort(key=lambda item: MATCH_LEVEL_PRIORITY.get(item.get("match_level", ""), 99))
    return results


def search_courses(
    *,
    keyword: str = "",
    audience: str = "",
    goal: str = "",
    page: int = 1,
    size: int = 20,
) -> dict:
    db = get_mongo_db()
    base_query = _build_base_query(audience=audience, goal=goal)

    if keyword.strip():
        all_items = _search_courses_with_keyword(
            db,
            base_query=base_query,
            keyword=keyword,
        )
    else:
        query = base_query
        all_items = [
            _load_related_data(db, series)
            for series in db["course_series"].find(query, {"_id": 0})
        ]

    skip = (page - 1) * size
    total = len(all_items)
    series_list = all_items[skip:skip + size]

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": series_list,
    }
