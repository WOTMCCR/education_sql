"""Interaction and review APIs."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id, get_optional_current_user_id
from ..errors import bad_request, conflict, not_found
from ..response import ok
from ..utils import count_total, format_datetime, local_now, make_no, offset_limit

router = APIRouter(prefix="/api/v1", tags=["interactions"])


class CohortReviewCreateRequest(BaseModel):
    scoreOverall: int = Field(description="综合评分，取值范围 1 到 5。")
    scoreTeacher: int = Field(description="教师评分，取值范围 1 到 5。")
    scoreContent: int = Field(description="内容评分，取值范围 1 到 5。")
    scoreService: int = Field(description="服务评分，取值范围 1 到 5。")
    reviewTags: list[str] = Field(default_factory=list, description="评价标签。")
    reviewContent: str | None = Field(default=None, description="评价内容。")
    anonymousFlag: int = Field(default=0, description="是否匿名。可选值：0 非匿名、1 匿名。")


def validate_scores(body: CohortReviewCreateRequest) -> None:
    values = [body.scoreOverall, body.scoreTeacher, body.scoreContent, body.scoreService]
    if any(score < 1 or score > 5 for score in values):
        raise bad_request("INVALID_SCORE", "评分必须在 1 到 5 之间")
    if body.anonymousFlag not in {0, 1}:
        raise bad_request("INVALID_ANONYMOUS_FLAG", "anonymousFlag 只能为 0 或 1")


def ensure_cohort_rel(cohort_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM student_cohort_rel
        WHERE cohort_id = %s
          AND user_id = %s
          AND enroll_status NOT IN ('cancelled', 'refunded')
        """,
        (cohort_id, current_user_id),
    )
    if row is None:
        raise not_found("COHORT_REL_NOT_FOUND", "当前用户没有该班次的有效履约关系")
    return row


def review_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reviewId": row["id"],
        "scoreOverall": row["score_overall"],
        "reviewTags": json.loads(row["review_tags"] or "[]"),
        "reviewContent": row["review_content"],
        "reviewedAt": format_datetime(row["reviewed_at"]),
    }


@router.post("/cohorts/{cohort_id}/reviews")
def create_cohort_review(
    body: Annotated[CohortReviewCreateRequest, Body(description="提交班次评价请求体。")],
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    validate_scores(body)
    rel = ensure_cohort_rel(cohort_id, current_user_id)
    exists = fetch_one(
        """
        SELECT id
        FROM cohort_review
        WHERE cohort_id = %s AND student_id = %s AND yn = 1
        """,
        (cohort_id, rel["student_id"]),
    )
    if exists:
        raise conflict("REVIEW_EXISTS", "同一用户对同一班次只允许一条有效评价")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO cohort_review (
                institution_id, cohort_id, user_id, student_id, review_no,
                score_overall, score_teacher, score_content, score_service,
                review_tags, review_content, anonymous_flag, yn,
                reviewed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1,
                %s, %s, %s)
            """,
            (
                rel["institution_id"],
                cohort_id,
                current_user_id,
                rel["student_id"],
                make_no("RV"),
                body.scoreOverall,
                body.scoreTeacher,
                body.scoreContent,
                body.scoreService,
                json.dumps(body.reviewTags, ensure_ascii=False),
                body.reviewContent,
                body.anonymousFlag,
                now,
                now,
                now,
            ),
        )
        review_id = cursor.lastrowid
    row = fetch_one("SELECT review_no FROM cohort_review WHERE id = %s", (review_id,))
    return ok({"reviewId": review_id, "reviewNo": row["review_no"] if row else None})


@router.get("/cohorts/{cohort_id}/reviews")
def list_cohort_reviews(
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int | None, Depends(get_optional_current_user_id)] = None,
    only_mine: Annotated[bool, Query(alias="onlyMine", description="是否只查询当前用户自己的评价。")] = False,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    if only_mine and current_user_id is None:
        raise bad_request("MISSING_USER_ID", "onlyMine=true 时必须传 X-User-Id")
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["cohort_id = %s", "yn = 1"]
    params: list[Any] = [cohort_id]
    if only_mine:
        conditions.append("user_id = %s")
        params.append(current_user_id)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM cohort_review
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT *
        FROM cohort_review
        WHERE {" AND ".join(conditions)}
        ORDER BY reviewed_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [review_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )
