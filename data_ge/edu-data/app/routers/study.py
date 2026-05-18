"""Session, video, homework, and exam APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from ..database import fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import not_found
from ..response import ok
from ..utils import (
    count_total,
    format_date,
    format_datetime,
    format_time,
    local_now,
    money,
    offset_limit,
)

router = APIRouter(prefix="/api/v1", tags=["study"])

HOMEWORK_STATUS_EXPR = """
CASE
    WHEN sub.id IS NOT NULL THEN sub.submit_status
    WHEN hw.due_at < %s THEN 'expired_unsubmitted'
    ELSE 'pending'
END
"""


def ensure_session_access(session_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT session.*
        FROM series_cohort_session AS session
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        JOIN student_cohort_rel AS rel ON rel.cohort_id = course.cohort_id
        WHERE session.id = %s
          AND rel.user_id = %s
          AND rel.enroll_status NOT IN ('cancelled', 'refunded')
        """,
        (session_id, current_user_id),
    )
    if row is None:
        raise not_found("SESSION_NOT_FOUND", "课次不存在或当前用户无权访问")
    return row


def ensure_video_access(video_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT video.*, asset.file_url
        FROM session_video AS video
        JOIN session_asset AS asset ON asset.id = video.asset_id
        JOIN series_cohort_session AS session ON session.id = asset.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        JOIN student_cohort_rel AS rel ON rel.cohort_id = course.cohort_id
        WHERE video.id = %s
          AND rel.user_id = %s
          AND rel.enroll_status NOT IN ('cancelled', 'refunded')
        """,
        (video_id, current_user_id),
    )
    if row is None:
        raise not_found("VIDEO_NOT_FOUND", "视频不存在或当前用户无权访问")
    return row


def homework_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "homeworkId": row["id"],
        "homeworkName": row["homework_name"],
        "cohortId": row["cohort_id"],
        "sessionId": row["session_id"],
        "dueAt": format_datetime(row["due_at"]),
        "homeworkStatus": row["homework_status"],
        "submissionId": row["submission_id"],
        "submittedAt": format_datetime(row["submitted_at"]),
        "correctedAt": format_datetime(row["corrected_at"]),
        "totalScore": money(row["total_score"]),
    }


def homework_submission_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submissionId": row["id"],
        "homeworkId": row["homework_id"],
        "homeworkName": row["homework_name"],
        "submitStatus": row["submit_status"],
        "correctionStatus": row["correction_status"],
        "totalScore": money(row["total_score"]),
        "submittedAt": format_datetime(row["submitted_at"]),
        "correctedAt": format_datetime(row["corrected_at"]),
    }


def exam_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "examId": row["id"],
        "examName": row["exam_name"],
        "cohortId": row["cohort_id"],
        "sessionId": row["session_id"],
        "windowStartAt": format_datetime(row["window_start_at"]),
        "deadlineAt": format_datetime(row["deadline_at"]),
        "durationMinutes": row["duration_minutes"],
        "attemptStatus": row["attempt_status"],
        "submissionId": row["submission_id"],
        "scoreValue": money(row["score_value"]),
    }


def exam_submission_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submissionId": row["id"],
        "examId": row["exam_id"],
        "examName": row["exam_name"],
        "attemptStatus": row["attempt_status"],
        "scoreValue": money(row["score_value"]),
        "startAt": format_datetime(row["start_at"]),
        "submitAt": format_datetime(row["submit_at"]),
    }


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: Annotated[int, Path(description="课次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    session = ensure_session_access(session_id, current_user_id)
    teachers = fetch_all(
        """
        SELECT staff.id, u.real_name
        FROM session_teacher_rel AS rel
        JOIN staff_profile AS staff ON staff.id = rel.teacher_id
        JOIN sys_user AS u ON u.id = staff.user_id
        WHERE rel.session_id = %s
        ORDER BY rel.sort_no ASC, rel.id ASC
        """,
        (session_id,),
    )
    return ok(
        {
            "sessionId": session["id"],
            "sessionTitle": session["session_title"],
            "teachingDate": format_date(session["teaching_date"]),
            "startTime": format_time(session["start_time"]),
            "endTime": format_time(session["end_time"]),
            "teachingStatusCode": session["teaching_status"],
            "teachers": [
                {"staffId": row["id"], "teacherName": row["real_name"]}
                for row in teachers
            ],
        }
    )


@router.get("/videos/{video_id}")
def get_video_detail(
    video_id: Annotated[int, Path(description="视频 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = ensure_video_access(video_id, current_user_id)
    return ok(
        {
            "videoId": row["id"],
            "videoTitle": row["video_title"],
            "durationSeconds": row["duration_seconds"],
            "resolutionLabel": row["resolution_label"],
            "fileUrl": row["file_url"],
        }
    )


@router.get("/videos/{video_id}/chapters")
def list_video_chapters(
    video_id: Annotated[int, Path(description="视频 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    ensure_video_access(video_id, current_user_id)
    rows = fetch_all(
        """
        SELECT chapter_no, chapter_title, start_second, end_second
        FROM session_video_chapter
        WHERE video_id = %s
        ORDER BY chapter_no ASC
        """,
        (video_id,),
    )
    return ok(
        [
            {
                "chapterNo": row["chapter_no"],
                "chapterTitle": row["chapter_title"],
                "startSecond": row["start_second"],
                "endSecond": row["end_second"],
            }
            for row in rows
        ]
    )


@router.get("/me/video-history")
def list_my_video_history(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    total = count_total(
        """
        SELECT COUNT(*) AS total
        FROM session_video_play AS play
        WHERE play.user_id = %s
        """,
        (current_user_id,),
    )
    rows = fetch_all(
        """
        SELECT
            play.video_id,
            video.video_title,
            play.last_position_seconds,
            play.progress_percent,
            play.updated_at
        FROM session_video_play AS play
        JOIN session_video AS video ON video.id = play.video_id
        WHERE play.user_id = %s
        ORDER BY play.updated_at DESC, play.id DESC
        LIMIT %s OFFSET %s
        """,
        (current_user_id, limit, offset),
    )
    return ok(
        {
            "list": [
                {
                    "videoId": row["video_id"],
                    "videoTitle": row["video_title"],
                    "lastPositionSeconds": row["last_position_seconds"],
                    "progressPercent": float(row["progress_percent"]),
                    "updatedAt": format_datetime(row["updated_at"]),
                }
                for row in rows
            ],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/me/homeworks")
def list_my_homeworks(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="作业状态。可选值：pending、submitted、expired_unsubmitted。"),
    ] = None,
    cohort_id: Annotated[int | None, Query(alias="cohortId", description="班次 ID。")] = None,
    due_before: Annotated[
        str | None,
        Query(alias="dueBefore", description="截止时间上限，格式：YYYY-MM-DD HH:mm:ss。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    now = local_now()
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["rel.user_id = %s", "rel.enroll_status NOT IN ('cancelled', 'refunded')"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append(f"{HOMEWORK_STATUS_EXPR} = %s")
        params.append(now)
        params.append(status)
    if cohort_id is not None:
        conditions.append("course.cohort_id = %s")
        params.append(cohort_id)
    if due_before:
        conditions.append("hw.due_at <= %s")
        params.append(due_before)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM student_cohort_rel AS rel
        JOIN series_cohort_course AS course ON course.cohort_id = rel.cohort_id
        JOIN series_cohort_session AS session ON session.series_cohort_course_id = course.id
        JOIN session_homework AS hw ON hw.session_id = session.id
        LEFT JOIN session_homework_submission AS sub
          ON sub.homework_id = hw.id AND sub.student_id = rel.student_id
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    select_params: list[Any] = [now, current_user_id]
    if status:
        select_params.extend([now, status])
    if cohort_id is not None:
        select_params.append(cohort_id)
    if due_before:
        select_params.append(due_before)
    rows = fetch_all(
        f"""
        SELECT
            hw.id,
            hw.homework_name,
            course.cohort_id,
            hw.session_id,
            hw.due_at,
            sub.id AS submission_id,
            {HOMEWORK_STATUS_EXPR} AS homework_status,
            sub.submitted_at,
            sub.corrected_at,
            sub.total_score
        FROM student_cohort_rel AS rel
        JOIN series_cohort_course AS course ON course.cohort_id = rel.cohort_id
        JOIN series_cohort_session AS session ON session.series_cohort_course_id = course.id
        JOIN session_homework AS hw ON hw.session_id = session.id
        LEFT JOIN session_homework_submission AS sub
          ON sub.homework_id = hw.id AND sub.student_id = rel.student_id
        WHERE {" AND ".join(conditions)}
        ORDER BY hw.due_at ASC, hw.id ASC
        LIMIT %s OFFSET %s
        """,
        tuple(select_params + [limit, offset]),
    )
    return ok(
        {
            "list": [homework_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/homeworks/{homework_id}")
def get_homework_detail(
    homework_id: Annotated[int, Path(description="作业 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = fetch_one(
        """
        SELECT hw.*
        FROM session_homework AS hw
        JOIN series_cohort_session AS session ON session.id = hw.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        JOIN student_cohort_rel AS rel ON rel.cohort_id = course.cohort_id
        WHERE hw.id = %s
          AND rel.user_id = %s
          AND rel.enroll_status NOT IN ('cancelled', 'refunded')
        """,
        (homework_id, current_user_id),
    )
    if row is None:
        raise not_found("HOMEWORK_NOT_FOUND", "作业不存在或当前用户无权访问")
    return ok(
        {
            "homeworkId": row["id"],
            "homeworkName": row["homework_name"],
            "dueAt": format_datetime(row["due_at"]),
            "createdAt": format_datetime(row["created_at"]),
        }
    )


@router.get("/me/homework-submissions")
def list_my_homework_submissions(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="作业提交状态。可选值：submitted、expired_unsubmitted。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["sub.user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("sub.submit_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM session_homework_submission AS sub
        JOIN session_homework AS hw ON hw.id = sub.homework_id
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            sub.*, hw.homework_name
        FROM session_homework_submission AS sub
        JOIN session_homework AS hw ON hw.id = sub.homework_id
        WHERE {" AND ".join(conditions)}
        ORDER BY sub.submitted_at DESC, sub.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [homework_submission_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/me/exams")
def list_my_exams(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="考试状态。可选值：not_started、in_progress、submitted、absent、timeout。"),
    ] = None,
    cohort_id: Annotated[int | None, Query(alias="cohortId", description="班次 ID。")] = None,
    deadline_before: Annotated[
        str | None,
        Query(alias="deadlineBefore", description="截止时间上限，格式：YYYY-MM-DD HH:mm:ss。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["rel.user_id = %s", "rel.enroll_status NOT IN ('cancelled', 'refunded')"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("COALESCE(sub.attempt_status, 'not_started') = %s")
        params.append(status)
    if cohort_id is not None:
        conditions.append("course.cohort_id = %s")
        params.append(cohort_id)
    if deadline_before:
        conditions.append("exam.deadline_at <= %s")
        params.append(deadline_before)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM student_cohort_rel AS rel
        JOIN series_cohort_course AS course ON course.cohort_id = rel.cohort_id
        JOIN series_cohort_session AS session ON session.series_cohort_course_id = course.id
        JOIN session_exam AS exam ON exam.session_id = session.id
        LEFT JOIN session_exam_submission AS sub
          ON sub.exam_id = exam.id AND sub.student_id = rel.student_id
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            exam.id,
            exam.exam_name,
            course.cohort_id,
            exam.session_id,
            exam.window_start_at,
            exam.deadline_at,
            exam.duration_minutes,
            sub.id AS submission_id,
            COALESCE(sub.attempt_status, 'not_started') AS attempt_status,
            sub.score_value
        FROM student_cohort_rel AS rel
        JOIN series_cohort_course AS course ON course.cohort_id = rel.cohort_id
        JOIN series_cohort_session AS session ON session.series_cohort_course_id = course.id
        JOIN session_exam AS exam ON exam.session_id = session.id
        LEFT JOIN session_exam_submission AS sub
          ON sub.exam_id = exam.id AND sub.student_id = rel.student_id
        WHERE {" AND ".join(conditions)}
        ORDER BY exam.deadline_at ASC, exam.id ASC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {"list": [exam_payload(row) for row in rows], "pageNo": page_no, "pageSize": page_size, "total": total}
    )


@router.get("/exams/{exam_id}")
def get_exam_detail(
    exam_id: Annotated[int, Path(description="考试 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = fetch_one(
        """
        SELECT exam.*
        FROM session_exam AS exam
        JOIN series_cohort_session AS session ON session.id = exam.session_id
        JOIN series_cohort_course AS course ON course.id = session.series_cohort_course_id
        JOIN student_cohort_rel AS rel ON rel.cohort_id = course.cohort_id
        WHERE exam.id = %s
          AND rel.user_id = %s
          AND rel.enroll_status NOT IN ('cancelled', 'refunded')
        """,
        (exam_id, current_user_id),
    )
    if row is None:
        raise not_found("EXAM_NOT_FOUND", "考试不存在或当前用户无权访问")
    return ok(
        {
            "examId": row["id"],
            "examName": row["exam_name"],
            "totalScore": money(row["total_score"]),
            "passScore": money(row["pass_score"]),
            "durationMinutes": row["duration_minutes"],
            "windowStartAt": format_datetime(row["window_start_at"]),
            "deadlineAt": format_datetime(row["deadline_at"]),
        }
    )


@router.get("/me/exam-submissions")
def list_my_exam_submissions(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="考试作答状态。可选值：not_started、in_progress、submitted、absent、timeout。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["sub.user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("sub.attempt_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM session_exam_submission AS sub
        JOIN session_exam AS exam ON exam.id = sub.exam_id
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            sub.*, exam.exam_name
        FROM session_exam_submission AS sub
        JOIN session_exam AS exam ON exam.id = sub.exam_id
        WHERE {" AND ".join(conditions)}
        ORDER BY sub.submit_at DESC, sub.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [exam_submission_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )
