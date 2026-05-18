"""Enrollment and learning-center APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from ..database import fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import not_found
from ..response import ok
from ..utils import count_total, format_date, format_datetime, offset_limit

router = APIRouter(prefix="/api/v1", tags=["enrollments"])


def ensure_cohort_rel(
    cohort_id: int, current_user_id: int, allow_closed: bool = False
) -> dict[str, Any]:
    conditions = ["cohort_id = %s", "user_id = %s"]
    if not allow_closed:
        conditions.append("enroll_status NOT IN ('cancelled', 'refunded')")
    row = fetch_one(
        f"SELECT * FROM student_cohort_rel WHERE {' AND '.join(conditions)}",
        (cohort_id, current_user_id),
    )
    if row is None:
        raise not_found("COHORT_REL_NOT_FOUND", "当前用户没有该班次的有效履约关系")
    return row


def counts(row: dict[str, Any] | None, total: str, first: str, second: str) -> dict[str, int]:
    data = row or {}
    return {
        "totalSessions": int(data.get(total) or 0),
        "presentCount": int(data.get(first) or 0),
        "absentCount": int(data.get(second) or 0),
    }


@router.get("/me/cohorts")
def list_my_cohorts(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="履约状态。可选值：active、completed、cancelled、refunded。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["rel.user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("rel.enroll_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM student_cohort_rel AS rel
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            rel.cohort_id,
            cohort.cohort_name,
            series.series_name,
            rel.enroll_status,
            rel.enroll_at
        FROM student_cohort_rel AS rel
        JOIN series_cohort AS cohort ON cohort.id = rel.cohort_id
        JOIN series ON series.id = cohort.series_id
        WHERE {" AND ".join(conditions)}
        ORDER BY rel.enroll_at DESC, rel.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [
                {
                    "cohortId": row["cohort_id"],
                    "cohortName": row["cohort_name"],
                    "seriesName": row["series_name"],
                    "enrollStatusCode": row["enroll_status"],
                    "enrollAt": format_datetime(row["enroll_at"]),
                }
                for row in rows
            ],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/me/cohorts/{cohort_id}")
def get_my_cohort_detail(
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    rel = ensure_cohort_rel(cohort_id, current_user_id, allow_closed=True)
    return ok(
        {
            "cohortId": rel["cohort_id"],
            "enrollStatusCode": rel["enroll_status"],
            "enrollAt": format_datetime(rel["enroll_at"]),
            "serviceEndAt": None,
            "completedAt": format_datetime(rel["completed_at"]),
        }
    )


@router.get("/me/cohorts/{cohort_id}/sessions")
def list_my_cohort_sessions(
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    rel = ensure_cohort_rel(cohort_id, current_user_id)
    rows = fetch_all(
        """
        SELECT
            session.id,
            session.session_title,
            session.teaching_date,
            att.attendance_status,
            hsub.submit_status,
            esub.attempt_status
        FROM series_cohort_session AS session
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        LEFT JOIN session_attendance AS att
          ON att.session_id = session.id AND att.student_id = %s
        LEFT JOIN session_homework AS hw ON hw.session_id = session.id
        LEFT JOIN session_homework_submission AS hsub
          ON hsub.homework_id = hw.id AND hsub.student_id = %s
        LEFT JOIN session_exam AS exam ON exam.session_id = session.id
        LEFT JOIN session_exam_submission AS esub
          ON esub.exam_id = exam.id AND esub.student_id = %s
        WHERE course.cohort_id = %s
        ORDER BY session.teaching_date ASC, session.start_time ASC, session.id ASC
        """,
        (rel["student_id"], rel["student_id"], rel["student_id"], cohort_id),
    )
    return ok(
        [
            {
                "sessionId": row["id"],
                "sessionTitle": row["session_title"],
                "teachingDate": format_date(row["teaching_date"]),
                "attendanceStatusCode": row["attendance_status"],
                "homeworkSubmitStatus": row["submit_status"],
                "examAttemptStatus": row["attempt_status"],
            }
            for row in rows
        ]
    )


@router.get("/me/cohorts/{cohort_id}/progress")
def get_my_cohort_progress(
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    rel = ensure_cohort_rel(cohort_id, current_user_id, allow_closed=True)
    student_id = rel["student_id"]
    attendance = fetch_one(
        """
        SELECT
            COUNT(*) AS total_sessions,
            SUM(attendance_status = 'present') AS present_count,
            SUM(attendance_status = 'absent') AS absent_count
        FROM session_attendance
        WHERE cohort_id = %s AND student_id = %s
        """,
        (cohort_id, student_id),
    )
    video = fetch_one(
        """
        SELECT
            COUNT(DISTINCT play.video_id) AS total_videos,
            SUM(play.completed_flag = 1) AS completed_videos,
            COALESCE(SUM(play.watched_seconds), 0) AS watched_seconds
        FROM session_video_play AS play
        JOIN session_video AS video ON video.id = play.video_id
        JOIN session_asset AS asset ON asset.id = video.asset_id
        JOIN series_cohort_session AS session ON session.id = asset.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        WHERE course.cohort_id = %s AND play.student_id = %s
        """,
        (cohort_id, student_id),
    )
    homework = fetch_one(
        """
        SELECT
            COUNT(*) AS total_homeworks,
            SUM(submit_status = 'submitted') AS submitted_count,
            SUM(correction_status = 'corrected') AS corrected_count,
            SUM(submit_status = 'expired_unsubmitted') AS expired_unsubmitted_count
        FROM session_homework_submission AS sub
        JOIN session_homework AS hw ON hw.id = sub.homework_id
        JOIN series_cohort_session AS session ON session.id = hw.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        WHERE course.cohort_id = %s AND sub.student_id = %s
        """,
        (cohort_id, student_id),
    )
    exam = fetch_one(
        """
        SELECT
            COUNT(*) AS total_exams,
            SUM(attempt_status = 'submitted') AS submitted_count,
            SUM(attempt_status = 'absent') AS absent_count
        FROM session_exam_submission AS sub
        JOIN session_exam AS exam ON exam.id = sub.exam_id
        JOIN series_cohort_session AS session ON session.id = exam.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        WHERE course.cohort_id = %s AND sub.student_id = %s
        """,
        (cohort_id, student_id),
    )
    return ok(
        {
            "enrollStatusCode": rel["enroll_status"],
            "attendance": counts(
                attendance, "total_sessions", "present_count", "absent_count"
            ),
            "video": {
                "totalVideos": int((video or {}).get("total_videos") or 0),
                "completedVideos": int((video or {}).get("completed_videos") or 0),
                "watchedSeconds": int((video or {}).get("watched_seconds") or 0),
            },
            "homework": {
                "totalHomeworks": int((homework or {}).get("total_homeworks") or 0),
                "submittedCount": int((homework or {}).get("submitted_count") or 0),
                "correctedCount": int((homework or {}).get("corrected_count") or 0),
                "expiredUnsubmittedCount": int(
                    (homework or {}).get("expired_unsubmitted_count") or 0
                ),
            },
            "exam": {
                "totalExams": int((exam or {}).get("total_exams") or 0),
                "submittedCount": int((exam or {}).get("submitted_count") or 0),
                "absentCount": int((exam or {}).get("absent_count") or 0),
            },
        }
    )
