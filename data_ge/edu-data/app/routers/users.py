"""User and student profile APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from ..database import fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import not_found
from ..response import ok
from ..utils import format_date, format_datetime

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me")
def get_me(current_user_id: Annotated[int, Depends(get_current_user_id)]):
    row = fetch_one(
        """
        SELECT
            id,
            nickname,
            real_name,
            mobile,
            email,
            gender,
            avatar_url,
            birthday
        FROM sys_user
        WHERE id = %s AND yn = 1
        """,
        (current_user_id,),
    )
    if row is None:
        raise not_found("USER_NOT_FOUND_OR_DISABLED", "当前用户不存在或已停用")
    return ok(
        {
            "userId": row["id"],
            "nickname": row["nickname"],
            "realName": row["real_name"],
            "mobile": row["mobile"],
            "email": row["email"],
            "gender": row["gender"],
            "avatarUrl": row["avatar_url"],
            "birthday": format_date(row["birthday"]),
        }
    )


@router.get("/me/student-profile")
def get_student_profile(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = fetch_one(
        """
        SELECT
            sp.id AS student_id,
            li.identity_code,
            li.identity_name,
            lg.goal_code,
            lg.goal_name,
            el.level_code,
            el.level_name,
            g.grade_code,
            g.grade_name,
            sp.school_name,
            sp.profile_note
        FROM student_profile AS sp
        JOIN dim_learner_identity AS li ON li.id = sp.learner_identity_id
        JOIN dim_learning_goal AS lg ON lg.id = sp.learning_goal_id
        LEFT JOIN dim_education_level AS el ON el.id = sp.education_level_id
        LEFT JOIN dim_grade AS g ON g.id = sp.grade_id
        WHERE sp.user_id = %s AND sp.yn = 1
        """,
        (current_user_id,),
    )
    if row is None:
        raise not_found("STUDENT_PROFILE_NOT_FOUND", "当前用户没有学员档案")
    return ok(
        {
            "studentId": row["student_id"],
            "learnerIdentity": {
                "code": row["identity_code"],
                "name": row["identity_name"],
            },
            "learningGoal": {
                "code": row["goal_code"],
                "name": row["goal_name"],
            },
            "educationLevel": {
                "code": row["level_code"],
                "name": row["level_name"],
            }
            if row["level_code"]
            else None,
            "grade": {
                "code": row["grade_code"],
                "name": row["grade_name"],
            }
            if row["grade_code"]
            else None,
            "schoolName": row["school_name"],
            "profileNote": row["profile_note"],
        }
    )


@router.get("/me/learning-summary")
def get_learning_summary(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    student = fetch_one(
        """
        SELECT id
        FROM student_profile
        WHERE user_id = %s AND yn = 1
        """,
        (current_user_id,),
    )
    if student is None:
        raise not_found("STUDENT_PROFILE_NOT_FOUND", "当前用户没有学员档案")

    counts = fetch_one(
        """
        SELECT
            SUM(enroll_status = 'active') AS active_count,
            SUM(enroll_status = 'completed') AS completed_count,
            SUM(enroll_status IN ('cancelled', 'refunded')) AS closed_count
        FROM student_cohort_rel
        WHERE user_id = %s
        """,
        (current_user_id,),
    )
    recent_records = _fetch_recent_learning_records(current_user_id)
    return ok(
        {
            "activeCohortCount": int((counts or {}).get("active_count") or 0),
            "completedCohortCount": int((counts or {}).get("completed_count") or 0),
            "cancelledOrRefundedCohortCount": int(
                (counts or {}).get("closed_count") or 0
            ),
            "recentLearningRecords": recent_records,
        }
    )


def _fetch_recent_learning_records(current_user_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        (
            SELECT
                'video' AS record_type,
                video.video_title AS title,
                play.updated_at AS occurred_at
            FROM session_video_play AS play
            JOIN session_video AS video ON video.id = play.video_id
            WHERE play.user_id = %s
        )
        UNION ALL
        (
            SELECT
                'homework' AS record_type,
                homework.homework_name AS title,
                submission.updated_at AS occurred_at
            FROM session_homework_submission AS submission
            JOIN session_homework AS homework ON homework.id = submission.homework_id
            WHERE submission.user_id = %s
        )
        UNION ALL
        (
            SELECT
                'exam' AS record_type,
                exam.exam_name AS title,
                submission.updated_at AS occurred_at
            FROM session_exam_submission AS submission
            JOIN session_exam AS exam ON exam.id = submission.exam_id
            WHERE submission.user_id = %s
        )
        ORDER BY occurred_at DESC
        LIMIT 10
        """,
        (current_user_id, current_user_id, current_user_id),
    )
    return [
        {
            "type": row["record_type"],
            "title": row["title"],
            "occurredAt": format_datetime(row["occurred_at"]),
        }
        for row in rows
    ]

