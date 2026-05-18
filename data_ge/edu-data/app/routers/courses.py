"""Course, cohort, and search APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from ..dependencies import get_optional_current_user_id
from ..database import execute, fetch_all, fetch_one
from ..errors import not_found
from ..response import ok
from ..utils import (
    count_total,
    format_date,
    format_time,
    json_list,
    local_now,
    offset_limit,
)

router = APIRouter(prefix="/api/v1", tags=["courses"])


@router.get("/series")
def list_series(
    keyword: Annotated[str | None, Query(description="课程名称关键字。")] = None,
    category_id: Annotated[
        int | None,
        Query(alias="categoryId", description="课程分类 ID；分类数量较多，不在接口文档中展开枚举。"),
    ] = None,
    learning_goal_code: Annotated[
        str | None,
        Query(
            alias="learningGoalCode",
            description=(
                "学习目标编码。可选值：score_improvement、school_sync、"
                "exam_preparation、postgraduate_exam、certificate_exam、"
                "skill_improvement、job_hunting、promotion、career_switch、"
                "interest_learning、other。"
            ),
        ),
    ] = None,
    delivery_mode_code: Annotated[
        str | None,
        Query(
            alias="deliveryModeCode",
            description="授课方式编码。可选值：online_recorded、online_live、offline_face_to_face。",
        ),
    ] = None,
    current_user_id: Annotated[int | None, Depends(get_optional_current_user_id)] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["s.sale_status = 'on_sale'"]
    params: list[Any] = []
    if keyword:
        conditions.append("s.series_name LIKE %s")
        params.append(f"%{keyword}%")
    if category_id is not None:
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM series_category_rel AS rel
                WHERE rel.series_id = s.id AND rel.category_id = %s
            )
            """
        )
        params.append(category_id)
    if learning_goal_code:
        conditions.append("JSON_CONTAINS(s.target_learning_goal_codes, JSON_QUOTE(%s))")
        params.append(learning_goal_code)
    if delivery_mode_code:
        conditions.append("s.delivery_mode = %s")
        params.append(delivery_mode_code)

    total = count_total(
        f"""
        SELECT COUNT(DISTINCT s.id) AS total
        FROM series AS s
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            s.id,
            s.series_name,
            s.cover_url,
            s.delivery_mode,
            s.sale_status,
            COALESCE(AVG(r.score_overall), 0) AS avg_score,
            COUNT(r.id) AS review_count
        FROM series AS s
        LEFT JOIN series_cohort AS c ON c.series_id = s.id
        LEFT JOIN cohort_review AS r ON r.cohort_id = c.id AND r.yn = 1
        WHERE {" AND ".join(conditions)}
        GROUP BY s.id
        ORDER BY avg_score DESC, review_count DESC, s.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    if current_user_id is not None and keyword and keyword.strip():
        now = local_now()
        execute(
            """
            INSERT INTO series_search_log (
                user_id, keyword_text, search_source, result_count,
                clicked_series_id, searched_at, created_at
            ) VALUES (%s, %s, 'course_list_page', %s, NULL, %s, %s)
            """,
            (current_user_id, keyword.strip(), total, now, now),
        )
    return ok(
        {
            "list": [_series_list_item(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/series/{series_id}")
def get_series_detail(
    series_id: Annotated[int, Path(description="课程系列 ID。")],
):
    row = fetch_one(
        """
        SELECT
            s.*,
            COALESCE(AVG(r.score_overall), 0) AS avg_score,
            COUNT(r.id) AS review_count
        FROM series AS s
        LEFT JOIN series_cohort AS c ON c.series_id = s.id
        LEFT JOIN cohort_review AS r ON r.cohort_id = c.id AND r.yn = 1
        WHERE s.id = %s
        GROUP BY s.id
        """,
        (series_id,),
    )
    if row is None or row["sale_status"] != "on_sale":
        raise not_found("SERIES_NOT_FOUND", "课程不存在或未上架")
    return ok(
        {
            "seriesId": row["id"],
            "seriesName": row["series_name"],
            "description": row["description"],
            "deliveryModeCode": row["delivery_mode"],
            "targetLearnerIdentityCodes": json_list(row["target_learner_identity_codes"]),
            "targetLearningGoalCodes": json_list(row["target_learning_goal_codes"]),
            "targetGradeCodes": json_list(row["target_grade_codes"]),
            "saleStatusCode": row["sale_status"],
            "avgScore": float(row["avg_score"] or 0),
            "reviewCount": int(row["review_count"] or 0),
        }
    )


@router.get("/series/{series_id}/cohorts")
def list_series_cohorts(
    series_id: Annotated[int, Path(description="课程系列 ID。")],
):
    rows = fetch_all(
        """
        SELECT
            c.id,
            c.cohort_name,
            c.sale_price,
            s.delivery_mode,
            campus.campus_name,
            u.real_name AS head_teacher_name,
            c.start_date,
            c.end_date,
            c.max_student_count,
            c.current_student_count
        FROM series_cohort AS c
        JOIN series AS s ON s.id = c.series_id
        LEFT JOIN org_campus AS campus ON campus.id = c.campus_id
        LEFT JOIN staff_profile AS staff ON staff.id = c.head_teacher_id
        LEFT JOIN sys_user AS u ON u.id = staff.user_id
        WHERE c.series_id = %s
          AND c.yn = 1
          AND c.current_student_count < c.max_student_count
        ORDER BY c.start_date ASC, c.id ASC
        """,
        (series_id,),
    )
    return ok(
        [
            {
                "cohortId": row["id"],
                "cohortName": row["cohort_name"],
                "salePrice": float(row["sale_price"]),
                "campusName": (
                    row["campus_name"]
                    if row["delivery_mode"] == "offline_face_to_face"
                    else None
                ),
                "headTeacherName": row["head_teacher_name"],
                "startDate": format_date(row["start_date"]),
                "endDate": format_date(row["end_date"]),
                "maxStudentCount": row["max_student_count"],
                "currentStudentCount": row["current_student_count"],
            }
            for row in rows
        ]
    )


@router.get("/cohorts/{cohort_id}")
def get_cohort_detail(
    cohort_id: Annotated[int, Path(description="班次 ID。")],
):
    cohort = fetch_one(
        """
        SELECT
            c.*,
            u.real_name AS head_teacher_name
        FROM series_cohort AS c
        LEFT JOIN staff_profile AS staff ON staff.id = c.head_teacher_id
        LEFT JOIN sys_user AS u ON u.id = staff.user_id
        WHERE c.id = %s
        """,
        (cohort_id,),
    )
    if cohort is None:
        raise not_found("COHORT_NOT_FOUND", "班次不存在")
    modules = fetch_all(
        """
        SELECT id, module_name, stage_no, lesson_count
        FROM series_cohort_course
        WHERE cohort_id = %s
        ORDER BY stage_no ASC, id ASC
        """,
        (cohort_id,),
    )
    sessions = fetch_all(
        """
        SELECT
            session.id,
            session.session_title,
            session.teaching_date,
            session.start_time,
            session.end_time
        FROM series_cohort_session AS session
        JOIN series_cohort_course AS course
          ON course.id = session.series_cohort_course_id
        WHERE course.cohort_id = %s
        ORDER BY session.teaching_date ASC, session.start_time ASC, session.id ASC
        """,
        (cohort_id,),
    )
    return ok(
        {
            "cohortId": cohort["id"],
            "cohortName": cohort["cohort_name"],
            "salePrice": float(cohort["sale_price"]),
            "startDate": format_date(cohort["start_date"]),
            "endDate": format_date(cohort["end_date"]),
            "headTeacherName": cohort["head_teacher_name"],
            "currentStudentCount": cohort["current_student_count"],
            "modules": [
                {
                    "cohortCourseId": row["id"],
                    "moduleName": row["module_name"],
                    "stageNo": row["stage_no"],
                    "lessonCount": row["lesson_count"],
                }
                for row in modules
            ],
            "sessions": [
                {
                    "sessionId": row["id"],
                    "sessionTitle": row["session_title"],
                    "teachingDate": format_date(row["teaching_date"]),
                    "startTime": format_time(row["start_time"]),
                    "endTime": format_time(row["end_time"]),
                }
                for row in sessions
            ],
        }
    )


def _series_list_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "seriesId": row["id"],
        "seriesName": row["series_name"],
        "coverUrl": row["cover_url"],
        "deliveryModeCode": row["delivery_mode"],
        "saleStatusCode": row["sale_status"],
        "avgScore": float(row["avg_score"] or 0),
        "reviewCount": int(row["review_count"] or 0),
    }
