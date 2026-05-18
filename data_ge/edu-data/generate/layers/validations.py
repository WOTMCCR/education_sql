"""Layer validation checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..db import db


def _count(sql: str, params: Any | None = None) -> int:
    row = db.fetch_one(sql, params)
    if row is None:
        return 0
    return int(next(iter(row.values())))


def validate_layer1() -> list[str]:
    checks: list[str] = []

    layer1_tables = (
        "dim_channel",
        "dim_course_category",
        "dim_question_type",
        "dim_learner_identity",
        "dim_grade",
        "dim_education_level",
        "dim_learning_goal",
        "sys_user",
        "org_institution",
        "org_campus",
        "org_department",
        "org_staff_role",
        "staff_profile",
        "org_institution_manager",
        "org_campus_manager",
        "org_department_manager",
        "org_classroom",
        "student_profile",
    )
    empty_tables = [
        table_name
        for table_name in layer1_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer1 contains empty table(s): {names}")
    checks.append("all Layer1 tables contain data")

    orphan_course_categories = _count(
        """
        SELECT COUNT(*)
        FROM dim_course_category AS child
        LEFT JOIN dim_course_category AS parent ON parent.id = child.parent_id
        WHERE child.parent_id IS NOT NULL
          AND parent.id IS NULL
        """
    )
    if orphan_course_categories:
        raise ValueError("dim_course_category contains orphan parent_id rows")
    checks.append("dim_course_category parent tree is closed")

    orphan_grades = _count(
        """
        SELECT COUNT(*)
        FROM dim_grade AS child
        LEFT JOIN dim_grade AS parent ON parent.id = child.parent_id
        WHERE child.parent_id IS NOT NULL
          AND parent.id IS NULL
        """
    )
    if orphan_grades:
        raise ValueError("dim_grade contains orphan parent_id rows")
    checks.append("dim_grade parent tree is closed")

    invalid_staff_role = _count(
        """
        SELECT COUNT(*)
        FROM staff_profile AS s
        JOIN org_staff_role AS r ON r.id = s.staff_role_id
        WHERE r.institution_id <> s.institution_id
        """
    )
    if invalid_staff_role:
        raise ValueError("staff_profile has role rows from another institution")
    checks.append("staff_profile role institution is consistent")

    invalid_staff_org = _count(
        """
        SELECT COUNT(*)
        FROM staff_profile AS s
        LEFT JOIN org_campus AS c ON c.id = s.campus_id
        LEFT JOIN org_department AS d ON d.id = s.dept_id
        WHERE (s.campus_id IS NOT NULL AND c.institution_id <> s.institution_id)
           OR (s.dept_id IS NOT NULL AND d.institution_id <> s.institution_id)
           OR (
               s.dept_id IS NOT NULL
               AND (
                   (d.campus_id IS NULL AND s.campus_id IS NOT NULL)
                   OR (d.campus_id IS NOT NULL AND d.campus_id <> s.campus_id)
               )
           )
        """
    )
    if invalid_staff_org:
        raise ValueError("staff_profile has inconsistent campus or department")
    checks.append("staff_profile campus and department are consistent")

    invalid_institution_manager = _count(
        """
        SELECT COUNT(*)
        FROM org_institution_manager AS m
        JOIN staff_profile AS s ON s.id = m.staff_id
        WHERE s.institution_id <> m.institution_id
        """
    )
    if invalid_institution_manager:
        raise ValueError("org_institution_manager has inconsistent staff institution")
    checks.append("institution managers belong to their institution")

    invalid_campus_manager = _count(
        """
        SELECT COUNT(*)
        FROM org_campus_manager AS m
        JOIN org_campus AS c ON c.id = m.campus_id
        JOIN staff_profile AS s ON s.id = m.staff_id
        WHERE s.institution_id <> c.institution_id
          OR s.campus_id <> c.id
        """
    )
    if invalid_campus_manager:
        raise ValueError("org_campus_manager has inconsistent staff campus")
    checks.append("campus managers belong to their campus")

    invalid_department_manager = _count(
        """
        SELECT COUNT(*)
        FROM org_department_manager AS m
        JOIN org_department AS d ON d.id = m.department_id
        JOIN staff_profile AS s ON s.id = m.staff_id
        WHERE s.institution_id <> d.institution_id
           OR (
               d.campus_id IS NULL
               AND s.campus_id IS NOT NULL
           )
           OR (
               d.campus_id IS NOT NULL
               AND s.campus_id <> d.campus_id
           )
        """
    )
    if invalid_department_manager:
        raise ValueError("org_department_manager has inconsistent staff organization")
    checks.append("department managers belong to their department organization")

    invalid_classrooms = _count(
        """
        SELECT COUNT(*)
        FROM org_classroom AS r
        LEFT JOIN org_campus AS c ON c.id = r.campus_id
        WHERE (
            r.room_type = 'physical'
            AND (r.campus_id IS NULL OR r.max_capacity IS NULL)
        )
        OR (
            r.campus_id IS NOT NULL
            AND c.institution_id <> r.institution_id
        )
        """
    )
    if invalid_classrooms:
        raise ValueError("org_classroom has invalid room type or campus relation")
    checks.append("classroom room type and campus rules are consistent")

    invalid_students = _count(
        """
        SELECT COUNT(*)
        FROM student_profile AS sp
        JOIN dim_learner_identity AS li ON li.id = sp.learner_identity_id
        WHERE (
            li.identity_code = 'in_school_student'
            AND (sp.grade_id IS NULL OR sp.education_level_id IS NOT NULL)
        )
        OR (
            li.identity_code <> 'in_school_student'
            AND (sp.education_level_id IS NULL OR sp.grade_id IS NOT NULL)
        )
        """
    )
    if invalid_students:
        raise ValueError("student_profile identity and education fields mismatch")
    checks.append("student_profile identity profile fields are consistent")

    identity_mismatch = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT u.id
            FROM sys_user AS u
            LEFT JOIN staff_profile AS s ON s.user_id = u.id
            LEFT JOIN student_profile AS sp ON sp.user_id = u.id
            GROUP BY u.id
            HAVING COUNT(DISTINCT s.id) + COUNT(DISTINCT sp.id) <> 1
        ) AS invalid_users
        """
    )
    if identity_mismatch:
        raise ValueError("sys_user identity coverage is not exactly one profile")
    checks.append("each sys_user has exactly one staff or student profile")

    return checks


def validate_layer2() -> list[str]:
    checks: list[str] = []

    layer2_tables = (
        "series",
        "series_category_rel",
        "series_cohort",
        "series_cohort_course",
        "series_cohort_session",
        "session_teacher_rel",
        "session_asset",
        "session_video",
        "session_video_chapter",
        "session_homework",
        "session_exam",
    )
    empty_tables = [
        table_name
        for table_name in layer2_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer2 contains empty table(s): {names}")
    checks.append("all Layer2 tables contain data")

    invalid_series = _count(
        """
        SELECT COUNT(*)
        FROM series AS s
        JOIN org_institution AS i ON i.id = s.institution_id
        JOIN sys_user AS u ON u.id = s.created_by
        WHERE s.updated_at < s.created_at
           OR s.created_at < i.created_at
           OR s.created_at < u.created_at
        """
    )
    if invalid_series:
        raise ValueError("series has invalid time ordering")
    checks.append("series time ordering is valid")

    invalid_series_category = _count(
        """
        SELECT COUNT(*)
        FROM series_category_rel AS rel
        JOIN series AS s ON s.id = rel.series_id
        JOIN dim_course_category AS c ON c.id = rel.category_id
        LEFT JOIN dim_course_category AS child ON child.parent_id = c.id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < s.created_at
           OR child.id IS NOT NULL
        """
    )
    if invalid_series_category:
        raise ValueError("series_category_rel has invalid timing or non-leaf category")
    checks.append("series category relations point to leaf categories")

    invalid_cohorts = _count(
        """
        SELECT COUNT(*)
        FROM series_cohort AS c
        JOIN series AS s ON s.id = c.series_id
        LEFT JOIN org_campus AS campus ON campus.id = c.campus_id
        JOIN staff_profile AS staff ON staff.id = c.head_teacher_id
        JOIN org_staff_role AS role ON role.id = staff.staff_role_id
        WHERE c.updated_at < c.created_at
           OR c.created_at < s.created_at
           OR c.sale_price <= 0
           OR c.institution_id <> s.institution_id
           OR staff.institution_id <> c.institution_id
           OR role.role_category <> 'academic'
           OR c.start_date < DATE(c.created_at)
           OR (
               s.delivery_mode = 'offline_face_to_face'
               AND (
                   c.campus_id IS NULL
                   OR campus.institution_id <> c.institution_id
                   OR staff.campus_id <> c.campus_id
               )
           )
           OR (
               s.delivery_mode IN ('online_live', 'online_recorded')
               AND c.campus_id IS NOT NULL
           )
           OR (
               s.delivery_mode IN ('online_live', 'offline_face_to_face')
               AND (c.end_date IS NULL OR c.start_date > c.end_date)
           )
           OR (
               s.delivery_mode = 'online_recorded'
               AND c.end_date IS NOT NULL
           )
        """
    )
    if invalid_cohorts:
        raise ValueError("series_cohort has invalid organization or time relation")
    checks.append("cohort organization and date rules are valid")

    invalid_courses = _count(
        """
        SELECT COUNT(*)
        FROM series_cohort_course AS cc
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        WHERE cc.updated_at < cc.created_at
           OR cc.created_at < c.created_at
           OR cc.start_date > cc.end_date
           OR cc.start_date < c.start_date
           OR (
               c.end_date IS NOT NULL
               AND cc.end_date > c.end_date
           )
        """
    )
    if invalid_courses:
        raise ValueError("series_cohort_course has invalid time relation")
    checks.append("cohort course module dates are valid")

    invalid_sessions = _count(
        """
        SELECT COUNT(*)
        FROM series_cohort_session AS ss
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN series AS s ON s.id = c.series_id
        LEFT JOIN org_classroom AS room ON room.id = ss.room_id
        WHERE ss.updated_at < ss.created_at
           OR ss.created_at < cc.created_at
           OR ss.teaching_date < cc.start_date
           OR ss.teaching_date > cc.end_date
           OR (
               ss.room_id IS NOT NULL
               AND room.institution_id <> c.institution_id
           )
           OR (
               s.delivery_mode = 'offline_face_to_face'
               AND (
                   ss.room_id IS NULL
                   OR room.room_type <> 'physical'
                   OR ss.start_time IS NULL
                   OR ss.end_time IS NULL
                   OR ss.start_time >= ss.end_time
               )
           )
           OR (
               s.delivery_mode = 'online_live'
               AND (
                   ss.room_id IS NULL
                   OR room.room_type <> 'live'
                   OR ss.start_time IS NULL
                   OR ss.end_time IS NULL
                   OR ss.start_time >= ss.end_time
               )
           )
           OR (
               s.delivery_mode = 'online_recorded'
               AND (
                   ss.room_id IS NOT NULL
                   OR ss.checkin_required <> 0
                   OR ss.start_time IS NOT NULL
                   OR ss.end_time IS NOT NULL
               )
           )
        """
    )
    if invalid_sessions:
        raise ValueError("series_cohort_session has invalid time or room relation")
    checks.append("session time and room rules are valid")

    invalid_teachers = _count(
        """
        SELECT COUNT(*)
        FROM session_teacher_rel AS rel
        JOIN series_cohort_session AS ss ON ss.id = rel.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN staff_profile AS staff ON staff.id = rel.teacher_id
        JOIN org_staff_role AS role ON role.id = staff.staff_role_id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < ss.created_at
           OR rel.created_at < staff.created_at
           OR staff.institution_id <> c.institution_id
           OR role.role_category <> 'teacher'
        """
    )
    if invalid_teachers:
        raise ValueError("session_teacher_rel has invalid teacher relation")
    checks.append("session teachers belong to the right institution and role")

    invalid_assets = _count(
        """
        SELECT COUNT(*)
        FROM session_asset AS a
        JOIN series_cohort_session AS ss ON ss.id = a.session_id
        JOIN sys_user AS u ON u.id = a.uploader_user_id
        WHERE a.updated_at < a.created_at
           OR a.created_at < ss.created_at
           OR a.created_at < u.created_at
           OR a.file_size < 0
        """
    )
    if invalid_assets:
        raise ValueError("session_asset has invalid time or file size")
    checks.append("session assets have valid timing and file metadata")

    invalid_videos = _count(
        """
        SELECT COUNT(*)
        FROM session_video AS v
        JOIN session_asset AS a ON a.id = v.asset_id
        WHERE v.updated_at < v.created_at
           OR v.created_at < a.created_at
           OR a.material_category <> 'video'
           OR a.file_type NOT IN ('mp4', 'mov', 'avi', 'mkv')
           OR v.duration_seconds <= 0
           OR v.bitrate_kbps <= 0
        """
    )
    if invalid_videos:
        raise ValueError("session_video has invalid asset or metadata")
    checks.append("session videos are backed by valid video assets")

    invalid_chapters = _count(
        """
        SELECT COUNT(*)
        FROM session_video_chapter AS chapter
        JOIN session_video AS video ON video.id = chapter.video_id
        WHERE chapter.updated_at < chapter.created_at
           OR chapter.created_at < video.created_at
           OR chapter.start_second < 0
           OR chapter.start_second >= chapter.end_second
           OR chapter.end_second > video.duration_seconds
        """
    )
    if invalid_chapters:
        raise ValueError("session_video_chapter has invalid time range")
    checks.append("video chapter ranges are valid")

    invalid_homeworks = _count(
        """
        SELECT COUNT(*)
        FROM session_homework AS hw
        JOIN series_cohort_session AS ss ON ss.id = hw.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN series AS s ON s.id = c.series_id
        JOIN staff_profile AS staff ON staff.id = hw.created_by
        WHERE hw.updated_at < hw.created_at
           OR hw.created_at < ss.created_at
           OR staff.institution_id <> c.institution_id
           OR hw.due_at < hw.created_at
           OR s.delivery_mode = 'online_recorded'
        """
    )
    if invalid_homeworks:
        raise ValueError("session_homework has invalid creator or time relation")
    checks.append("homework creator and due time rules are valid")

    invalid_exams = _count(
        """
        SELECT COUNT(*)
        FROM session_exam AS exam
        JOIN series_cohort_session AS ss ON ss.id = exam.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN series AS s ON s.id = c.series_id
        JOIN staff_profile AS staff ON staff.id = exam.created_by
        WHERE exam.updated_at < exam.created_at
           OR exam.created_at < ss.created_at
           OR staff.institution_id <> c.institution_id
           OR s.delivery_mode = 'online_recorded'
           OR exam.total_score <= 0
           OR exam.pass_score < 0
           OR exam.pass_score > exam.total_score
           OR exam.duration_minutes <= 0
           OR exam.window_start_at > exam.deadline_at
           OR TIMESTAMPDIFF(MINUTE, exam.window_start_at, exam.deadline_at)
                < exam.duration_minutes
           OR (
               exam.publish_status = 'published'
               AND exam.publish_at IS NULL
           )
           OR (
               exam.publish_at IS NOT NULL
               AND exam.publish_at < exam.created_at
           )
        """
    )
    if invalid_exams:
        raise ValueError("session_exam has invalid creator, score, or time relation")
    checks.append("exam creator, score, and window rules are valid")

    return checks


def validate_layer3() -> list[str]:
    checks: list[str] = []

    layer3_tables = (
        "question_bank",
        "question",
        "session_homework_question_rel",
        "session_exam_question_rel",
        "coupon",
        "coupon_category_rel",
        "coupon_series_rel",
        "series_exposure_log",
        "series_visit_log",
        "series_search_log",
        "series_favorite",
        "shopping_cart_item",
        "consultation_record",
        "coupon_receive_record",
    )
    empty_tables = [
        table_name
        for table_name in layer3_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer3 contains empty table(s): {names}")
    checks.append("all Layer3 tables contain data")

    invalid_banks = _count(
        """
        SELECT COUNT(*)
        FROM question_bank AS b
        JOIN org_institution AS i ON i.id = b.institution_id
        JOIN dim_course_category AS c ON c.id = b.category_id
        LEFT JOIN dim_course_category AS child ON child.parent_id = c.id
        WHERE b.updated_at < b.created_at
           OR b.created_at < i.created_at
           OR child.id IS NOT NULL
        """
    )
    if invalid_banks:
        raise ValueError("question_bank has invalid timing or non-leaf category")
    checks.append("question banks point to leaf categories")

    invalid_questions = _count(
        """
        SELECT COUNT(*)
        FROM `question` AS q
        JOIN question_bank AS b ON b.id = q.bank_id
        JOIN dim_question_type AS qt ON qt.id = q.question_type_id
        WHERE q.updated_at < q.created_at
           OR q.created_at < b.created_at
           OR (
               qt.type_code IN ('single_choice', 'multiple_choice', 'true_false')
               AND q.options_json IS NULL
           )
           OR (
               qt.type_code = 'short_answer'
               AND q.options_json IS NOT NULL
           )
        """
    )
    if invalid_questions:
        raise ValueError("question has invalid timing or option shape")
    checks.append("questions match their question type option rules")

    invalid_homework_questions = _count(
        """
        SELECT COUNT(*)
        FROM session_homework_question_rel AS rel
        JOIN session_homework AS hw ON hw.id = rel.homework_id
        JOIN series_cohort_session AS ss ON ss.id = hw.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN `question` AS q ON q.id = rel.question_id
        JOIN question_bank AS b ON b.id = q.bank_id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < hw.created_at
           OR rel.created_at < q.created_at
           OR rel.score <= 0
           OR b.institution_id <> c.institution_id
        """
    )
    if invalid_homework_questions:
        raise ValueError("session_homework_question_rel has invalid score or institution")
    checks.append("homework question relations match institution and score rules")

    invalid_exam_questions = _count(
        """
        SELECT COUNT(*)
        FROM session_exam_question_rel AS rel
        JOIN session_exam AS exam ON exam.id = rel.exam_id
        JOIN series_cohort_session AS ss ON ss.id = exam.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN `question` AS q ON q.id = rel.question_id
        JOIN question_bank AS b ON b.id = q.bank_id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < exam.created_at
           OR rel.created_at < q.created_at
           OR rel.score <= 0
           OR b.institution_id <> c.institution_id
        """
    )
    if invalid_exam_questions:
        raise ValueError("session_exam_question_rel has invalid score or institution")
    invalid_exam_score_sum = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                exam.id,
                exam.total_score,
                SUM(rel.score) AS question_score
            FROM session_exam AS exam
            JOIN session_exam_question_rel AS rel ON rel.exam_id = exam.id
            GROUP BY exam.id, exam.total_score
            HAVING ABS(question_score - exam.total_score) > 0.01
        ) AS invalid_exam
        """
    )
    if invalid_exam_score_sum:
        raise ValueError("session_exam_question_rel score sum does not match exam total")
    checks.append("exam question relations match institution and score rules")

    invalid_coupons = _count(
        """
        SELECT COUNT(*)
        FROM coupon AS c
        LEFT JOIN org_institution AS i ON i.id = c.institution_id
        WHERE c.updated_at < c.created_at
           OR (c.issuer_scope = 'platform' AND c.institution_id IS NOT NULL)
           OR (c.issuer_scope = 'institution' AND c.institution_id IS NULL)
           OR (c.institution_id IS NOT NULL AND c.created_at < i.created_at)
           OR (c.coupon_type = 'cash' AND (c.discount_amount IS NULL OR c.discount_rate IS NOT NULL))
           OR (c.coupon_type = 'discount' AND (c.discount_rate IS NULL OR c.discount_amount IS NOT NULL))
           OR (c.discount_amount IS NOT NULL AND c.discount_amount <= 0)
           OR (c.discount_rate IS NOT NULL AND (c.discount_rate <= 0 OR c.discount_rate >= 1))
           OR c.threshold_amount < 0
           OR c.per_user_limit <= 0
           OR c.total_count < c.receive_count
           OR c.receive_count < c.used_count
           OR c.valid_from > c.valid_to
           OR c.valid_from < c.created_at
        """
    )
    if invalid_coupons:
        raise ValueError("coupon has invalid issuer, amount, or time relation")
    checks.append("coupons have valid issuer, amount, and time rules")

    invalid_coupon_category = _count(
        """
        SELECT COUNT(*)
        FROM coupon_category_rel AS rel
        JOIN coupon AS c ON c.id = rel.coupon_id
        JOIN dim_course_category AS category ON category.id = rel.category_id
        LEFT JOIN dim_course_category AS child ON child.parent_id = category.id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < c.created_at
           OR child.id IS NOT NULL
        """
    )
    if invalid_coupon_category:
        raise ValueError("coupon_category_rel has invalid timing or non-leaf category")
    checks.append("coupon category relations point to leaf categories")

    invalid_coupon_series = _count(
        """
        SELECT COUNT(*)
        FROM coupon_series_rel AS rel
        JOIN coupon AS c ON c.id = rel.coupon_id
        JOIN series AS s ON s.id = rel.series_id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < c.created_at
           OR rel.created_at < s.created_at
           OR (
               c.institution_id IS NOT NULL
               AND c.institution_id <> s.institution_id
           )
        """
    )
    if invalid_coupon_series:
        raise ValueError("coupon_series_rel has invalid timing or institution")
    checks.append("coupon series relations match timing and institution rules")

    invalid_exposures = _count(
        """
        SELECT COUNT(*)
        FROM series_exposure_log AS log
        JOIN sys_user AS u ON u.id = log.user_id
        JOIN series AS s ON s.id = log.series_id
        WHERE log.created_at < u.created_at
           OR log.created_at < s.created_at
           OR log.exposed_at < log.created_at
           OR log.position_no <= 0
        """
    )
    if invalid_exposures:
        raise ValueError("series_exposure_log has invalid time or position")
    checks.append("exposure logs have valid timing and positions")

    invalid_visits = _count(
        """
        SELECT COUNT(*)
        FROM series_visit_log AS log
        JOIN sys_user AS u ON u.id = log.user_id
        JOIN series AS s ON s.id = log.series_id
        LEFT JOIN series_exposure_log AS e ON e.id = log.ref_exposure_id
        WHERE log.created_at < u.created_at
           OR log.created_at < s.created_at
           OR (log.ref_exposure_id IS NOT NULL AND e.series_id <> log.series_id)
           OR (log.ref_exposure_id IS NOT NULL AND e.user_id <> log.user_id)
           OR log.enter_at < log.created_at
           OR (log.leave_at IS NOT NULL AND log.leave_at < log.enter_at)
           OR log.stay_seconds < 0
        """
    )
    if invalid_visits:
        raise ValueError("series_visit_log has invalid timing or exposure relation")
    checks.append("visit logs are consistent with source exposures")

    invalid_searches = _count(
        """
        SELECT COUNT(*)
        FROM series_search_log AS log
        JOIN sys_user AS u ON u.id = log.user_id
        LEFT JOIN series AS s ON s.id = log.clicked_series_id
        WHERE log.created_at < u.created_at
           OR (log.clicked_series_id IS NOT NULL AND log.created_at < s.created_at)
           OR log.searched_at < log.created_at
           OR log.result_count < 0
           OR (log.clicked_series_id IS NOT NULL AND log.result_count <= 0)
        """
    )
    if invalid_searches:
        raise ValueError("series_search_log has invalid timing or result relation")
    checks.append("search logs have valid timing and result rules")

    invalid_favorites = _count(
        """
        SELECT COUNT(*)
        FROM series_favorite AS fav
        JOIN sys_user AS u ON u.id = fav.user_id
        JOIN series AS s ON s.id = fav.series_id
        WHERE fav.updated_at < fav.created_at
           OR fav.created_at < u.created_at
           OR fav.created_at < s.created_at
        """
    )
    if invalid_favorites:
        raise ValueError("series_favorite has invalid time relation")
    checks.append("favorites have valid time relations")

    invalid_cart_items = _count(
        """
        SELECT COUNT(*)
        FROM shopping_cart_item AS item
        JOIN sys_user AS u ON u.id = item.user_id
        JOIN series_cohort AS c ON c.id = item.cohort_id
        WHERE item.updated_at < item.created_at
           OR item.created_at < u.created_at
           OR item.created_at < c.created_at
           OR item.unit_price < 0
           OR item.added_at < item.created_at
           OR (item.removed_at IS NOT NULL AND item.removed_at < item.added_at)
        """
    )
    if invalid_cart_items:
        raise ValueError("shopping_cart_item has invalid time or price")
    checks.append("cart items have valid time and price rules")

    invalid_consultations = _count(
        """
        SELECT COUNT(*)
        FROM consultation_record AS consult
        JOIN sys_user AS u ON u.id = consult.user_id
        JOIN series_cohort AS c ON c.id = consult.cohort_id
        JOIN staff_profile AS staff ON staff.user_id = consult.consultant_user_id
        WHERE consult.updated_at < consult.created_at
           OR consult.created_at < u.created_at
           OR consult.created_at < c.created_at
           OR staff.institution_id <> c.institution_id
           OR consult.consulted_at < consult.created_at
        """
    )
    if invalid_consultations:
        raise ValueError("consultation_record has invalid consultant or timing")
    checks.append("consultations have valid consultant and timing rules")

    invalid_receives = _count(
        """
        SELECT COUNT(*)
        FROM coupon_receive_record AS r
        JOIN coupon AS c ON c.id = r.coupon_id
        JOIN sys_user AS u ON u.id = r.user_id
        WHERE r.updated_at < r.created_at
           OR r.created_at < c.created_at
           OR r.created_at < u.created_at
           OR r.received_at < r.created_at
           OR r.expired_at <= r.received_at
           OR (r.used_at IS NOT NULL AND r.used_at < r.received_at)
           OR (r.used_at IS NOT NULL AND r.used_at > r.expired_at)
           OR (r.receive_status = 'unused' AND r.used_at IS NOT NULL)
           OR (r.receive_status = 'used' AND r.used_at IS NULL)
           OR (r.receive_status = 'expired' AND (r.used_at IS NOT NULL OR r.expired_at > r.updated_at))
        """
    )
    if invalid_receives:
        raise ValueError("coupon_receive_record has invalid status or timing")
    checks.append("coupon receive records have valid status and timing rules")

    invalid_receive_limits = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT r.coupon_id, r.user_id, COUNT(*) AS receive_total, c.per_user_limit
            FROM coupon_receive_record AS r
            JOIN coupon AS c ON c.id = r.coupon_id
            GROUP BY r.coupon_id, r.user_id, c.per_user_limit
            HAVING COUNT(*) > c.per_user_limit
        ) AS over_limit
        """
    )
    if invalid_receive_limits:
        raise ValueError("coupon_receive_record exceeds per-user receive limits")
    checks.append("coupon receive records respect per-user receive limits")

    invalid_coupon_counters = _count(
        """
        SELECT COUNT(*)
        FROM coupon AS c
        LEFT JOIN (
            SELECT
                coupon_id,
                COUNT(*) AS receive_count,
                SUM(receive_status = 'used') AS used_count
            FROM coupon_receive_record
            GROUP BY coupon_id
        ) AS r ON r.coupon_id = c.id
        WHERE c.receive_count <> COALESCE(r.receive_count, 0)
           OR c.used_count <> COALESCE(r.used_count, 0)
        """
    )
    if invalid_coupon_counters:
        raise ValueError("coupon receive counters do not match receive records")
    checks.append("coupon receive counters match receive records")

    return checks


def validate_layer4() -> list[str]:
    checks: list[str] = []

    layer4_tables = (
        "order",
        "order_item",
        "payment_record",
        "refund_request",
        "student_cohort_rel",
    )
    empty_tables = [
        table_name
        for table_name in layer4_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer4 contains empty table(s): {names}")
    checks.append("all Layer4 tables contain data")

    invalid_orders = _count(
        """
        SELECT COUNT(*)
        FROM `order` AS o
        JOIN org_institution AS i ON i.id = o.institution_id
        JOIN sys_user AS u ON u.id = o.user_id
        JOIN student_profile AS sp ON sp.id = o.student_id
        LEFT JOIN coupon_receive_record AS cr ON cr.id = o.coupon_receive_record_id
        LEFT JOIN coupon AS c ON c.id = cr.coupon_id
        WHERE o.updated_at < o.created_at
           OR o.created_at < i.created_at
           OR o.created_at < u.created_at
           OR sp.user_id <> o.user_id
           OR (
               o.coupon_receive_record_id IS NOT NULL
               AND cr.user_id <> o.user_id
           )
           OR (
               o.coupon_receive_record_id IS NOT NULL
               AND c.institution_id IS NOT NULL
               AND c.institution_id <> o.institution_id
           )
           OR o.total_amount < 0
           OR o.discount_amount < 0
           OR o.discount_amount > o.total_amount
           OR ABS(o.payable_amount - (o.total_amount - o.discount_amount)) > 0.01
           OR (o.paid_amount IS NOT NULL AND o.paid_amount < 0)
           OR (o.refund_amount IS NOT NULL AND o.refund_amount < 0)
           OR (
               o.refund_amount IS NOT NULL
               AND (o.paid_amount IS NULL OR o.refund_amount > o.paid_amount)
           )
           OR (o.paid_at IS NOT NULL AND o.paid_at < o.created_at)
           OR (o.cancel_at IS NOT NULL AND o.cancel_at < o.created_at)
           OR (o.paid_at IS NOT NULL AND o.cancel_at IS NOT NULL)
           OR (
               o.order_status = 'pending'
               AND (
                   o.paid_at IS NOT NULL
                   OR o.cancel_at IS NOT NULL
                   OR o.paid_amount IS NOT NULL
                   OR o.refund_amount IS NOT NULL
               )
           )
           OR (
               o.order_status = 'paid'
               AND (
                   o.paid_at IS NULL
                   OR o.cancel_at IS NOT NULL
                   OR ABS(o.paid_amount - o.payable_amount) > 0.01
                   OR o.refund_amount IS NOT NULL
               )
           )
           OR (
               o.order_status = 'completed'
               AND (
                   o.paid_at IS NULL
                   OR o.cancel_at IS NOT NULL
                   OR ABS(o.paid_amount - o.payable_amount) > 0.01
                   OR o.refund_amount IS NOT NULL
               )
           )
           OR (
               o.order_status = 'cancelled'
               AND (
                   o.cancel_at IS NULL
                   OR o.paid_at IS NOT NULL
                   OR o.paid_amount IS NOT NULL
                   OR o.refund_amount IS NOT NULL
               )
           )
           OR (
               o.order_status = 'partial_refunded'
               AND (
                   o.paid_at IS NULL
                   OR ABS(o.paid_amount - o.payable_amount) > 0.01
                   OR o.refund_amount <= 0
                   OR o.refund_amount >= o.paid_amount
               )
           )
           OR (
               o.order_status = 'refunded'
               AND (
                   o.paid_at IS NULL
                   OR ABS(o.paid_amount - o.payable_amount) > 0.01
                   OR ABS(o.refund_amount - o.paid_amount) > 0.01
               )
           )
        """
    )
    if invalid_orders:
        raise ValueError("order has invalid amount, status, or time relation")
    checks.append("orders have valid amount, status, and time rules")

    invalid_order_items = _count(
        """
        SELECT COUNT(*)
        FROM order_item AS item
        JOIN `order` AS o ON o.id = item.order_id
        JOIN sys_user AS u ON u.id = item.user_id
        JOIN student_profile AS sp ON sp.id = item.student_id
        JOIN series_cohort AS c ON c.id = item.cohort_id
        WHERE item.updated_at < item.created_at
           OR item.created_at < o.created_at
           OR item.created_at < u.created_at
           OR item.created_at < c.created_at
           OR item.institution_id <> o.institution_id
           OR item.institution_id <> c.institution_id
           OR item.user_id <> o.user_id
           OR item.student_id <> o.student_id
           OR sp.user_id <> item.user_id
           OR item.unit_price < 0
           OR item.discount_amount < 0
           OR item.discount_amount > item.unit_price
           OR ABS(item.payable_amount - (item.unit_price - item.discount_amount)) > 0.01
           OR item.service_period_days <= 0
           OR (
               o.order_status = 'cancelled'
               AND item.order_item_status <> 'cancelled'
           )
           OR (
               o.order_status = 'refunded'
               AND item.order_item_status <> 'refunded'
           )
        """
    )
    if invalid_order_items:
        raise ValueError("order_item has invalid amount, status, or relation")
    checks.append("order items match order and cohort relations")

    invalid_order_item_sums = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                o.id,
                o.total_amount,
                o.discount_amount,
                o.payable_amount,
                SUM(item.unit_price) AS item_total_amount,
                SUM(item.discount_amount) AS item_discount_amount,
                SUM(item.payable_amount) AS item_payable_amount
            FROM `order` AS o
            JOIN order_item AS item ON item.order_id = o.id
            GROUP BY
                o.id,
                o.total_amount,
                o.discount_amount,
                o.payable_amount
            HAVING ABS(item_total_amount - total_amount) > 0.01
                OR ABS(item_discount_amount - discount_amount) > 0.01
                OR ABS(item_payable_amount - payable_amount) > 0.01
        ) AS invalid_orders
        """
    )
    if invalid_order_item_sums:
        raise ValueError("order item sums do not match order amounts")
    checks.append("order item amount sums match order amounts")

    invalid_payments = _count(
        """
        SELECT COUNT(*)
        FROM payment_record AS p
        JOIN `order` AS o ON o.id = p.order_id
        WHERE p.updated_at < p.created_at
           OR p.created_at < o.created_at
           OR p.institution_id <> o.institution_id
           OR p.amount < 0
           OR ABS(p.amount - o.payable_amount) > 0.01
           OR (p.refund_amount IS NOT NULL AND p.refund_amount < 0)
           OR (p.refund_amount IS NOT NULL AND p.refund_amount > p.amount)
           OR (p.paid_at IS NOT NULL AND p.paid_at < p.created_at)
           OR (p.refund_at IS NOT NULL AND p.refund_at < p.created_at)
           OR (p.refund_at IS NOT NULL AND (p.paid_at IS NULL OR p.refund_at < p.paid_at))
           OR (
               p.payment_status = 'pending'
               AND (
                   p.paid_at IS NOT NULL
                   OR p.refund_at IS NOT NULL
                   OR p.refund_amount IS NOT NULL
               )
           )
           OR (
               p.payment_status = 'paid'
               AND (
                   p.paid_at IS NULL
                   OR p.refund_at IS NOT NULL
                   OR p.refund_amount IS NOT NULL
               )
           )
           OR (
               p.payment_status = 'failed'
               AND (
                   p.paid_at IS NOT NULL
                   OR p.refund_at IS NOT NULL
                   OR p.refund_amount IS NOT NULL
               )
           )
           OR (
               p.payment_status = 'partial_refunded'
               AND (
                   p.paid_at IS NULL
                   OR p.refund_at IS NULL
                   OR p.refund_amount <= 0
                   OR p.refund_amount >= p.amount
               )
           )
           OR (
               p.payment_status = 'refunded'
               AND (
                   p.paid_at IS NULL
                   OR p.refund_at IS NULL
                   OR ABS(p.refund_amount - p.amount) > 0.01
               )
           )
           OR (
               o.order_status IN ('paid', 'completed')
               AND p.payment_status <> 'paid'
           )
           OR (
               o.order_status = 'partial_refunded'
               AND p.payment_status <> 'partial_refunded'
           )
           OR (
               o.order_status = 'refunded'
               AND p.payment_status <> 'refunded'
           )
           OR (
               o.order_status = 'pending'
               AND p.payment_status NOT IN ('pending', 'failed')
           )
           OR (
               o.order_status = 'cancelled'
               AND p.payment_status <> 'failed'
           )
        """
    )
    if invalid_payments:
        raise ValueError("payment_record has invalid status, amount, or time relation")
    checks.append("payment records match order status and amount rules")

    invalid_refunds = _count(
        """
        SELECT COUNT(*)
        FROM refund_request AS r
        JOIN `order` AS o ON o.id = r.order_id
        JOIN order_item AS item ON item.id = r.order_item_id
        JOIN payment_record AS p ON p.id = r.payment_id
        JOIN sys_user AS u ON u.id = r.user_id
        JOIN student_profile AS sp ON sp.id = r.student_id
        LEFT JOIN staff_profile AS approver
            ON approver.user_id = r.approver_user_id
            AND approver.institution_id = r.institution_id
        WHERE r.updated_at < r.created_at
           OR r.created_at < o.created_at
           OR r.created_at < u.created_at
           OR r.institution_id <> o.institution_id
           OR r.institution_id <> item.institution_id
           OR r.user_id <> o.user_id
           OR r.student_id <> o.student_id
           OR sp.user_id <> r.user_id
           OR item.order_id <> r.order_id
           OR p.order_id <> r.order_id
           OR p.payment_status NOT IN ('paid', 'partial_refunded', 'refunded')
           OR r.refund_type NOT IN (
               'personal_reason',
               'course_unsatisfied',
               'schedule_conflict',
               'duplicate_purchase'
           )
           OR r.apply_amount <= 0
           OR (r.approved_amount IS NOT NULL AND r.approved_amount < 0)
           OR (r.approved_amount IS NOT NULL AND r.approved_amount > r.apply_amount)
           OR r.applied_at < r.created_at
           OR (r.approved_at IS NOT NULL AND r.approved_at < r.applied_at)
           OR (
               r.refunded_at IS NOT NULL
               AND (r.approved_at IS NULL OR r.refunded_at < r.approved_at)
           )
           OR (
               r.refund_status = 'pending'
               AND (
                   r.approved_amount IS NOT NULL
                   OR r.approved_at IS NOT NULL
                   OR r.refunded_at IS NOT NULL
                   OR r.approver_user_id IS NOT NULL
               )
           )
           OR (
               r.refund_status = 'approved'
               AND (
                   r.approved_amount IS NULL
                   OR r.approved_at IS NULL
                   OR r.refunded_at IS NOT NULL
                   OR r.approver_user_id IS NULL
                   OR approver.id IS NULL
               )
           )
           OR (
               r.refund_status = 'rejected'
               AND (
                   r.approved_amount <> 0
                   OR r.approved_at IS NULL
                   OR r.refunded_at IS NOT NULL
                   OR r.approver_user_id IS NULL
                   OR approver.id IS NULL
               )
           )
           OR (
               r.refund_status = 'refunded'
               AND (
                   r.approved_amount IS NULL
                   OR r.approved_at IS NULL
                   OR r.refunded_at IS NULL
                   OR r.approver_user_id IS NULL
                   OR approver.id IS NULL
               )
           )
        """
    )
    if invalid_refunds:
        raise ValueError("refund_request has invalid relation, amount, or status")
    checks.append("refund requests match payment and order item rules")

    invalid_refund_sums = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                item.id,
                item.payable_amount,
                SUM(CASE
                    WHEN r.refund_status IN ('approved', 'refunded')
                    THEN r.approved_amount
                    ELSE 0
                END) AS approved_refund_amount
            FROM order_item AS item
            JOIN refund_request AS r ON r.order_item_id = item.id
            GROUP BY item.id, item.payable_amount
            HAVING approved_refund_amount > item.payable_amount
        ) AS invalid_items
        """
    )
    if invalid_refund_sums:
        raise ValueError("approved refund amount exceeds order item payable amount")
    checks.append("refund approved amount stays within order item payable amount")

    invalid_student_cohorts = _count(
        """
        SELECT COUNT(*)
        FROM student_cohort_rel AS rel
        JOIN order_item AS item ON item.id = rel.order_item_id
        JOIN series_cohort AS c ON c.id = rel.cohort_id
        JOIN student_profile AS sp ON sp.id = rel.student_id
        WHERE rel.updated_at < rel.created_at
           OR rel.created_at < item.created_at
           OR rel.created_at < c.created_at
           OR rel.institution_id <> c.institution_id
           OR rel.institution_id <> item.institution_id
           OR rel.user_id <> item.user_id
           OR rel.student_id <> item.student_id
           OR rel.cohort_id <> item.cohort_id
           OR sp.user_id <> rel.user_id
           OR rel.enroll_at < rel.created_at
           OR (rel.completed_at IS NOT NULL AND rel.completed_at < rel.enroll_at)
           OR (rel.cancelled_at IS NOT NULL AND rel.cancelled_at < rel.enroll_at)
           OR (rel.completed_at IS NOT NULL AND rel.cancelled_at IS NOT NULL)
           OR (
               rel.enroll_status = 'active'
               AND (rel.completed_at IS NOT NULL OR rel.cancelled_at IS NOT NULL)
           )
           OR (
               rel.enroll_status = 'completed'
               AND (rel.completed_at IS NULL OR rel.cancelled_at IS NOT NULL)
           )
           OR (
               rel.enroll_status IN ('cancelled', 'refunded')
               AND (rel.cancelled_at IS NULL OR rel.completed_at IS NOT NULL)
           )
        """
    )
    if invalid_student_cohorts:
        raise ValueError("student_cohort_rel has invalid fulfillment relation")
    checks.append("student cohort fulfillment relations are valid")

    missing_fulfillment = _count(
        """
        SELECT COUNT(*)
        FROM order_item AS item
        JOIN `order` AS o ON o.id = item.order_id
        LEFT JOIN student_cohort_rel AS rel ON rel.order_item_id = item.id
        WHERE o.order_status IN ('paid', 'completed', 'partial_refunded', 'refunded')
          AND rel.id IS NULL
        """
    )
    if missing_fulfillment:
        raise ValueError("successful order items are missing student_cohort_rel")
    checks.append("all successful order items have fulfillment relations")

    invalid_coupon_usage = _count(
        """
        SELECT COUNT(*)
        FROM `order` AS o
        JOIN coupon_receive_record AS r ON r.id = o.coupon_receive_record_id
        WHERE (
            o.order_status IN ('paid', 'completed', 'partial_refunded', 'refunded')
            AND (r.receive_status <> 'used' OR r.used_at <> o.paid_at)
        )
        OR (
            o.order_status IN ('pending', 'cancelled')
            AND r.receive_status <> 'unused'
        )
        """
    )
    if invalid_coupon_usage:
        raise ValueError("coupon receive usage does not match order status")
    checks.append("coupon receive usage matches paid and unpaid order states")

    invalid_coupon_counters = _count(
        """
        SELECT COUNT(*)
        FROM coupon AS c
        LEFT JOIN (
            SELECT
                coupon_id,
                SUM(receive_status = 'used') AS used_count
            FROM coupon_receive_record
            GROUP BY coupon_id
        ) AS r ON r.coupon_id = c.id
        WHERE c.used_count <> COALESCE(r.used_count, 0)
        """
    )
    if invalid_coupon_counters:
        raise ValueError("coupon used_count does not match receive records")
    checks.append("coupon used counters match receive records")

    invalid_cohort_counts = _count(
        """
        SELECT COUNT(*)
        FROM series_cohort AS c
        LEFT JOIN (
            SELECT
                cohort_id,
                COUNT(*) AS current_student_count
            FROM student_cohort_rel
            WHERE enroll_status = 'active'
            GROUP BY cohort_id
        ) AS rel ON rel.cohort_id = c.id
        WHERE c.current_student_count <> COALESCE(rel.current_student_count, 0)
        """
    )
    if invalid_cohort_counts:
        raise ValueError("series_cohort current_student_count is not refreshed")
    checks.append("cohort current student counters match active fulfillments")

    return checks


def validate_layer5(now: datetime | None = None) -> list[str]:
    checks: list[str] = []
    if now is None:
        now = datetime.now().astimezone().replace(tzinfo=None, microsecond=0)
    today = now.date()

    layer5_tables = (
        "session_attendance",
        "session_video_play",
        "session_video_play_event",
        "session_homework_submission",
        "session_exam_submission",
        "cohort_discussion_topic",
        "cohort_discussion_post",
        "cohort_review",
        "service_ticket",
        "service_ticket_follow_record",
        "service_ticket_satisfaction_survey",
    )
    empty_tables = [
        table_name
        for table_name in layer5_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer5 contains empty table(s): {names}")
    checks.append("all Layer5 tables contain data")

    invalid_attendance = _count(
        """
        SELECT COUNT(*)
        FROM session_attendance AS a
        JOIN series_cohort_session AS ss ON ss.id = a.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = a.cohort_id
        JOIN student_cohort_rel AS rel
            ON rel.cohort_id = a.cohort_id
           AND rel.student_id = a.student_id
        JOIN student_profile AS sp ON sp.id = a.student_id
        WHERE a.updated_at < a.created_at
           OR a.created_at < ss.created_at
           OR a.institution_id <> c.institution_id
           OR c.id <> cc.cohort_id
           OR sp.user_id <> a.user_id
           OR rel.user_id <> a.user_id
           OR rel.enroll_status IN ('cancelled', 'refunded')
           OR (a.checkin_time IS NOT NULL AND a.checkin_time < a.created_at)
           OR (a.attendance_status = 'pending' AND a.checkin_time IS NOT NULL)
           OR (a.attendance_status = 'present' AND a.checkin_time IS NULL)
           OR (a.attendance_status = 'late' AND a.checkin_time IS NULL)
           OR (a.attendance_status = 'leave' AND (a.leave_type IS NULL OR a.checkin_time IS NOT NULL))
           OR (a.attendance_status = 'absent' AND a.checkin_time IS NOT NULL)
        """
    )
    if invalid_attendance:
        raise ValueError("session_attendance has invalid relation, status, or time")
    missing_attendance = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                ss.id AS session_id,
                rel.student_id
            FROM series_cohort_session AS ss
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series AS s ON s.id = c.series_id
            JOIN student_cohort_rel AS rel ON rel.cohort_id = c.id
            WHERE s.delivery_mode IN ('online_live', 'offline_face_to_face')
              AND ss.created_at <= %s
              AND ss.teaching_date <= %s
              AND rel.enroll_status IN ('active', 'completed')
        ) AS expected
        LEFT JOIN session_attendance AS a
            ON a.session_id = expected.session_id
           AND a.student_id = expected.student_id
        WHERE a.id IS NULL
        """,
        (now, today),
    )
    if missing_attendance:
        raise ValueError("session_attendance does not cover all effective cohort learners")
    checks.append("attendance covers all effective learners and respects status rules")

    invalid_video_play = _count(
        """
        SELECT COUNT(*)
        FROM session_video_play AS play
        JOIN session_video AS v ON v.id = play.video_id
        JOIN session_asset AS a ON a.id = v.asset_id
        JOIN series_cohort_session AS ss ON ss.id = a.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN student_cohort_rel AS rel
            ON rel.cohort_id = c.id
           AND rel.student_id = play.student_id
        JOIN student_profile AS sp ON sp.id = play.student_id
        WHERE play.updated_at < play.created_at
           OR play.created_at < v.created_at
           OR play.institution_id <> c.institution_id
           OR sp.user_id <> play.user_id
           OR rel.user_id <> play.user_id
           OR rel.enroll_status IN ('cancelled', 'refunded')
           OR play.last_position_seconds < 0
           OR play.last_position_seconds > v.duration_seconds
           OR play.watched_seconds < 0
           OR play.progress_percent < 0
           OR play.progress_percent > 100
           OR play.started_at < play.created_at
           OR (play.ended_at IS NOT NULL AND play.ended_at < play.started_at)
           OR (play.completed_flag = 1 AND (play.ended_at IS NULL OR play.progress_percent <> 100))
           OR (play.completed_flag = 0 AND play.progress_percent >= 100)
        """
    )
    if invalid_video_play:
        raise ValueError("session_video_play has invalid relation, progress, or time")
    checks.append("video play sessions respect fulfillment and progress rules")

    invalid_video_events = _count(
        """
        SELECT COUNT(*)
        FROM session_video_play_event AS event
        JOIN session_video_play AS play ON play.id = event.play_session_id
        JOIN session_video AS v ON v.id = play.video_id
        WHERE event.created_at < play.created_at
           OR event.position_seconds < 0
           OR event.position_seconds > v.duration_seconds
           OR event.playback_rate <= 0
           OR event.event_time < event.created_at
           OR event.event_time < play.started_at
           OR (play.ended_at IS NOT NULL AND event.event_time > play.ended_at)
           OR (
               event.event_type = 'complete'
               AND event.position_seconds <> v.duration_seconds
           )
        """
    )
    if invalid_video_events:
        raise ValueError("session_video_play_event has invalid timing or event position")
    checks.append("video play events stay within the play session time window")

    invalid_homework_submission = _count(
        """
        SELECT COUNT(*)
        FROM session_homework_submission AS sub
        JOIN session_homework AS hw ON hw.id = sub.homework_id
        JOIN series_cohort_session AS ss ON ss.id = sub.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN student_cohort_rel AS rel
            ON rel.cohort_id = c.id
           AND rel.student_id = sub.student_id
        JOIN student_profile AS sp ON sp.id = sub.student_id
        LEFT JOIN staff_profile AS teacher ON teacher.id = sub.corrected_by
        WHERE sub.updated_at < sub.created_at
           OR sub.created_at < hw.created_at
           OR sub.created_at < ss.created_at
           OR sub.institution_id <> c.institution_id
           OR hw.session_id <> sub.session_id
           OR sp.user_id <> sub.user_id
           OR rel.user_id <> sub.user_id
           OR rel.enroll_status IN ('cancelled', 'refunded')
           OR (sub.submitted_at IS NOT NULL AND sub.submitted_at < sub.created_at)
           OR (sub.corrected_at IS NOT NULL AND (sub.submitted_at IS NULL OR sub.corrected_at < sub.submitted_at))
           OR (sub.corrected_by IS NOT NULL AND teacher.institution_id <> sub.institution_id)
           OR (sub.total_score IS NOT NULL AND sub.total_score < 0)
           OR (
               sub.submit_status = 'submitted'
               AND (sub.submitted_at IS NULL OR sub.submitted_at > hw.due_at)
           )
           OR (
               sub.submit_status = 'expired_unsubmitted'
               AND (
                   sub.submitted_at IS NOT NULL
                   OR sub.corrected_at IS NOT NULL
                   OR sub.corrected_by IS NOT NULL
                   OR sub.total_score IS NOT NULL
                   OR sub.correction_status <> 'pending'
               )
           )
           OR (
               sub.correction_status = 'pending'
               AND (
                   sub.corrected_at IS NOT NULL
                   OR sub.corrected_by IS NOT NULL
                   OR sub.total_score IS NOT NULL
               )
           )
           OR (
               sub.correction_status = 'corrected'
               AND (
                   sub.corrected_at IS NULL
                   OR sub.corrected_by IS NULL
                   OR sub.total_score IS NULL
               )
           )
        """
    )
    if invalid_homework_submission:
        raise ValueError("session_homework_submission has invalid status, relation, or time")
    missing_homework_submission = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                hw.id AS homework_id,
                rel.student_id
            FROM session_homework AS hw
            JOIN series_cohort_session AS ss ON ss.id = hw.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN student_cohort_rel AS rel ON rel.cohort_id = c.id
            WHERE hw.created_at <= %s
              AND hw.due_at <= %s
              AND rel.enroll_status IN ('active', 'completed')
        ) AS expected
        LEFT JOIN session_homework_submission AS sub
            ON sub.homework_id = expected.homework_id
           AND sub.student_id = expected.student_id
        WHERE sub.id IS NULL
        """,
        (now, now),
    )
    if missing_homework_submission:
        raise ValueError("session_homework_submission does not cover all effective learners")
    checks.append("homework submissions cover all effective learners and terminal states")

    invalid_exam_submission = _count(
        """
        SELECT COUNT(*)
        FROM session_exam_submission AS sub
        JOIN session_exam AS exam ON exam.id = sub.exam_id
        JOIN series_cohort_session AS ss ON ss.id = exam.session_id
        JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
        JOIN series_cohort AS c ON c.id = cc.cohort_id
        JOIN student_cohort_rel AS rel
            ON rel.cohort_id = c.id
           AND rel.student_id = sub.student_id
        JOIN student_profile AS sp ON sp.id = sub.student_id
        WHERE sub.updated_at < sub.created_at
           OR sub.created_at < exam.created_at
           OR sub.institution_id <> c.institution_id
           OR sp.user_id <> sub.user_id
           OR rel.user_id <> sub.user_id
           OR rel.enroll_status IN ('cancelled', 'refunded')
           OR (sub.start_at IS NOT NULL AND (sub.start_at < sub.created_at OR sub.start_at < exam.window_start_at OR sub.start_at > exam.deadline_at))
           OR (sub.submit_at IS NOT NULL AND (sub.start_at IS NULL OR sub.submit_at < sub.start_at OR sub.submit_at > exam.deadline_at))
           OR (sub.duration_seconds IS NOT NULL AND sub.duration_seconds < 0)
           OR (sub.submit_at IS NOT NULL AND (sub.duration_seconds IS NULL OR sub.duration_seconds > exam.duration_minutes * 60))
           OR (sub.score_value IS NOT NULL AND (sub.score_value < 0 OR sub.score_value > exam.total_score))
           OR (
               sub.attempt_status = 'submitted'
               AND (sub.start_at IS NULL OR sub.submit_at IS NULL OR sub.duration_seconds IS NULL)
           )
           OR (
               sub.attempt_status = 'absent'
               AND (
                   sub.start_at IS NOT NULL
                   OR sub.submit_at IS NOT NULL
                   OR sub.duration_seconds IS NOT NULL
                   OR sub.score_value IS NOT NULL
               )
           )
           OR (
               sub.attempt_status = 'timeout'
               AND (
                   sub.start_at IS NULL
                   OR sub.submit_at IS NULL
                   OR sub.duration_seconds <> exam.duration_minutes * 60
               )
           )
        """
    )
    if invalid_exam_submission:
        raise ValueError("session_exam_submission has invalid status, relation, or time")
    missing_exam_submission = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                exam.id AS exam_id,
                rel.student_id
            FROM session_exam AS exam
            JOIN series_cohort_session AS ss ON ss.id = exam.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN student_cohort_rel AS rel ON rel.cohort_id = c.id
            WHERE exam.created_at <= %s
              AND exam.deadline_at <= %s
              AND rel.enroll_status IN ('active', 'completed')
        ) AS expected
        LEFT JOIN session_exam_submission AS sub
            ON sub.exam_id = expected.exam_id
           AND sub.student_id = expected.student_id
        WHERE sub.id IS NULL
        """,
        (now, now),
    )
    if missing_exam_submission:
        raise ValueError("session_exam_submission does not cover all effective learners")
    checks.append("exam submissions cover all effective learners and terminal states")

    invalid_topics = _count(
        """
        SELECT COUNT(*)
        FROM cohort_discussion_topic AS topic
        JOIN series_cohort AS c ON c.id = topic.cohort_id
        WHERE topic.updated_at < topic.created_at
           OR topic.created_at < c.created_at
           OR topic.institution_id <> c.institution_id
           OR topic.view_count < 0
           OR topic.reply_count < 0
           OR (topic.last_reply_at IS NOT NULL AND topic.last_reply_at < topic.created_at)
        """
    )
    if invalid_topics:
        raise ValueError("cohort_discussion_topic has invalid relation or stats")
    invalid_topic_stats = _count(
        """
        SELECT COUNT(*)
        FROM cohort_discussion_topic AS topic
        LEFT JOIN (
            SELECT
                topic_id,
                COUNT(*) AS reply_count,
                MAX(created_at) AS last_reply_at
            FROM cohort_discussion_post
            WHERE parent_post_id IS NULL
              AND yn = 1
            GROUP BY topic_id
        ) AS stats ON stats.topic_id = topic.id
        WHERE topic.reply_count <> COALESCE(stats.reply_count, 0)
           OR topic.last_reply_at <> stats.last_reply_at
           OR (stats.topic_id IS NULL AND topic.last_reply_at IS NOT NULL)
        """
    )
    if invalid_topic_stats:
        raise ValueError("cohort_discussion_topic reply stats are not refreshed")
    checks.append("discussion topic reply stats are consistent")

    invalid_posts = _count(
        """
        SELECT COUNT(*)
        FROM cohort_discussion_post AS post
        JOIN cohort_discussion_topic AS topic ON topic.id = post.topic_id
        LEFT JOIN cohort_discussion_post AS parent ON parent.id = post.parent_post_id
        WHERE post.updated_at < post.created_at
           OR post.created_at < topic.created_at
           OR post.institution_id <> topic.institution_id
           OR post.like_count < 0
           OR post.reply_count < 0
           OR (post.parent_post_id IS NOT NULL AND (parent.topic_id <> post.topic_id OR parent.yn <> 1))
           OR (topic.is_closed = 1 AND post.created_at > topic.updated_at)
        """
    )
    if invalid_posts:
        raise ValueError("cohort_discussion_post has invalid relation or parent linkage")
    invalid_post_stats = _count(
        """
        SELECT COUNT(*)
        FROM cohort_discussion_post AS post
        LEFT JOIN (
            SELECT
                parent_post_id,
                COUNT(*) AS reply_count
            FROM cohort_discussion_post
            WHERE parent_post_id IS NOT NULL
              AND yn = 1
            GROUP BY parent_post_id
        ) AS stats ON stats.parent_post_id = post.id
        WHERE post.reply_count <> COALESCE(stats.reply_count, 0)
        """
    )
    if invalid_post_stats:
        raise ValueError("cohort_discussion_post reply_count is not refreshed")
    checks.append("discussion post reply stats are consistent")

    invalid_reviews = _count(
        """
        SELECT COUNT(*)
        FROM cohort_review AS review
        JOIN series_cohort AS c ON c.id = review.cohort_id
        JOIN student_profile AS sp ON sp.id = review.student_id
        JOIN student_cohort_rel AS rel
            ON rel.cohort_id = review.cohort_id
           AND rel.student_id = review.student_id
        WHERE review.updated_at < review.created_at
           OR review.created_at < c.created_at
           OR review.institution_id <> c.institution_id
           OR sp.user_id <> review.user_id
           OR rel.user_id <> review.user_id
           OR rel.enroll_status IN ('cancelled', 'refunded')
           OR review.reviewed_at < review.created_at
           OR review.reviewed_at < c.start_date
           OR review.score_overall NOT BETWEEN 1 AND 5
           OR review.score_teacher NOT BETWEEN 1 AND 5
           OR review.score_content NOT BETWEEN 1 AND 5
           OR review.score_service NOT BETWEEN 1 AND 5
        """
    )
    if invalid_reviews:
        raise ValueError("cohort_review has invalid relation, score, or time")
    checks.append("cohort reviews respect fulfillment and score rules")

    invalid_tickets = _count(
        """
        SELECT COUNT(*)
        FROM service_ticket AS ticket
        JOIN order_item AS item ON item.id = ticket.order_item_id
        JOIN student_profile AS sp ON sp.id = ticket.student_id
        LEFT JOIN refund_request AS refund ON refund.id = ticket.refund_request_id
        WHERE ticket.updated_at < ticket.created_at
           OR ticket.created_at < item.created_at
           OR ticket.institution_id <> item.institution_id
           OR ticket.user_id <> item.user_id
           OR ticket.student_id <> item.student_id
           OR sp.user_id <> ticket.user_id
           OR (
               ticket.refund_request_id IS NOT NULL
               AND (refund.order_item_id <> ticket.order_item_id OR refund.user_id <> ticket.user_id)
           )
           OR (ticket.first_response_at IS NOT NULL AND ticket.first_response_at < ticket.created_at)
           OR (ticket.closed_at IS NOT NULL AND ticket.closed_at < ticket.created_at)
           OR (
               ticket.closed_at IS NOT NULL
               AND ticket.first_response_at IS NOT NULL
               AND ticket.closed_at < ticket.first_response_at
           )
           OR (ticket.ticket_status = 'pending' AND ticket.closed_at IS NOT NULL)
           OR (ticket.ticket_status = 'in_progress' AND (ticket.first_response_at IS NULL OR ticket.closed_at IS NOT NULL))
           OR (ticket.ticket_status = 'closed' AND ticket.closed_at IS NULL)
           OR (ticket.ticket_type = 'refund' AND ticket.refund_request_id IS NULL)
           OR (ticket.ticket_type <> 'refund' AND ticket.refund_request_id IS NOT NULL)
        """
    )
    if invalid_tickets:
        raise ValueError("service_ticket has invalid relation, state, or refund linkage")
    checks.append("service tickets satisfy order-item and refund linkage rules")

    invalid_follow = _count(
        """
        SELECT COUNT(*)
        FROM service_ticket_follow_record AS follow
        JOIN service_ticket AS ticket ON ticket.id = follow.ticket_id
        LEFT JOIN staff_profile AS staff
            ON staff.user_id = follow.follow_user_id
           AND staff.institution_id = ticket.institution_id
        WHERE follow.updated_at < follow.created_at
           OR follow.created_at < ticket.created_at
           OR staff.id IS NULL
           OR follow.followed_at < follow.created_at
           OR (ticket.closed_at IS NOT NULL AND follow.followed_at > ticket.closed_at)
           OR (follow.follow_type = 'refund_review' AND ticket.ticket_type <> 'refund')
           OR (follow.follow_result = 'resolved' AND ticket.ticket_status <> 'closed')
        """
    )
    if invalid_follow:
        raise ValueError("service_ticket_follow_record has invalid relation or timing")
    checks.append("ticket follow records match ticket state and staff ownership")

    invalid_survey = _count(
        """
        SELECT COUNT(*)
        FROM service_ticket_satisfaction_survey AS survey
        JOIN service_ticket AS ticket ON ticket.id = survey.ticket_id
        JOIN student_profile AS sp ON sp.id = survey.student_id
        WHERE survey.updated_at < survey.created_at
           OR survey.created_at < ticket.created_at
           OR survey.surveyed_at < survey.created_at
           OR sp.user_id <> survey.user_id
           OR survey.user_id <> ticket.user_id
           OR survey.student_id <> ticket.student_id
           OR ticket.ticket_status <> 'closed'
           OR survey.surveyed_at < ticket.closed_at
           OR (survey.score_value IS NOT NULL AND survey.score_value NOT BETWEEN 1 AND 5)
        """
    )
    if invalid_survey:
        raise ValueError("service_ticket_satisfaction_survey has invalid closure or score relation")
    checks.append("ticket satisfaction surveys only exist for closed tickets")

    return checks


def validate_layer6() -> list[str]:
    checks: list[str] = []

    layer6_tables = (
        "teacher_compensation_bill",
        "teacher_compensation_item",
        "channel_commission_bill",
        "channel_commission_item",
        "risk_alert_event",
        "risk_disposal_record",
        "ugc_moderation_task",
    )
    empty_tables = [
        table_name
        for table_name in layer6_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        names = ", ".join(empty_tables)
        raise ValueError(f"Layer6 contains empty table(s): {names}")
    checks.append("all Layer6 tables contain data")

    invalid_teacher_bill = _count(
        """
        SELECT COUNT(*)
        FROM teacher_compensation_bill AS bill
        JOIN org_institution AS inst ON inst.id = bill.institution_id
        JOIN staff_profile AS teacher ON teacher.id = bill.teacher_id
        JOIN org_staff_role AS role ON role.id = teacher.staff_role_id
        LEFT JOIN staff_profile AS approver_staff
            ON approver_staff.user_id = bill.approver_user_id
           AND approver_staff.institution_id = bill.institution_id
        WHERE bill.updated_at < bill.created_at
           OR bill.created_at < inst.created_at
           OR bill.created_at < teacher.created_at
           OR teacher.institution_id <> bill.institution_id
           OR role.role_category <> 'teacher'
           OR bill.lesson_count < 0
           OR bill.base_amount < 0
           OR bill.bonus_amount < 0
           OR bill.deduction_amount < 0
           OR bill.payable_amount <> bill.base_amount + bill.bonus_amount - bill.deduction_amount
           OR bill.payable_amount < 0
           OR (bill.approver_user_id IS NOT NULL AND approver_staff.id IS NULL)
           OR (bill.settled_at IS NOT NULL AND bill.settled_at < bill.created_at)
           OR (bill.paid_at IS NOT NULL AND (bill.settled_at IS NULL OR bill.paid_at < bill.settled_at))
           OR (
               bill.bill_status = 'pending'
               AND (
                   bill.approver_user_id IS NOT NULL
                   OR bill.settled_at IS NOT NULL
                   OR bill.paid_at IS NOT NULL
               )
           )
           OR (
               bill.bill_status = 'approved'
               AND (
                   bill.approver_user_id IS NULL
                   OR bill.settled_at IS NULL
                   OR bill.paid_at IS NOT NULL
               )
           )
           OR (
               bill.bill_status = 'paid'
               AND (
                   bill.approver_user_id IS NULL
                   OR bill.settled_at IS NULL
                   OR bill.paid_at IS NULL
               )
           )
        """
    )
    if invalid_teacher_bill:
        raise ValueError("teacher_compensation_bill has invalid relation, status, or amount")

    invalid_teacher_bill_agg = _count(
        """
        SELECT COUNT(*)
        FROM teacher_compensation_bill AS bill
        LEFT JOIN (
            SELECT
                bill_id,
                SUM(CASE WHEN item_type = 'session_fee' THEN 1 ELSE 0 END) AS lesson_count,
                SUM(CASE WHEN item_type = 'session_fee' THEN item_amount ELSE 0 END) AS base_amount,
                SUM(CASE WHEN item_type = 'bonus' THEN item_amount ELSE 0 END) AS bonus_amount,
                SUM(CASE WHEN item_type = 'deduction' THEN -item_amount ELSE 0 END) AS deduction_amount,
                SUM(item_amount) AS payable_amount
            FROM teacher_compensation_item
            GROUP BY bill_id
        ) AS agg ON agg.bill_id = bill.id
        WHERE bill.lesson_count <> COALESCE(agg.lesson_count, 0)
           OR bill.base_amount <> COALESCE(agg.base_amount, 0)
           OR bill.bonus_amount <> COALESCE(agg.bonus_amount, 0)
           OR bill.deduction_amount <> COALESCE(agg.deduction_amount, 0)
           OR bill.payable_amount <> COALESCE(agg.payable_amount, 0)
        """
    )
    if invalid_teacher_bill_agg:
        raise ValueError("teacher_compensation_bill aggregate values do not match item totals")
    checks.append("teacher compensation bills and items reconcile")

    invalid_teacher_item = _count(
        """
        SELECT COUNT(*)
        FROM teacher_compensation_item AS item
        JOIN teacher_compensation_bill AS bill ON bill.id = item.bill_id
        JOIN staff_profile AS teacher ON teacher.id = item.teacher_id
        LEFT JOIN series_cohort AS cohort ON cohort.id = item.cohort_id
        LEFT JOIN series_cohort_session AS session ON session.id = item.session_id
        LEFT JOIN series_cohort_course AS cc ON cc.id = session.series_cohort_course_id
        LEFT JOIN series_cohort AS session_cohort ON session_cohort.id = cc.cohort_id
        WHERE item.updated_at < item.created_at
           OR item.created_at < bill.created_at
           OR item.institution_id <> bill.institution_id
           OR item.teacher_id <> bill.teacher_id
           OR teacher.institution_id <> item.institution_id
           OR (item.cohort_id IS NOT NULL AND cohort.institution_id <> item.institution_id)
           OR (item.session_id IS NOT NULL AND session_cohort.institution_id <> item.institution_id)
           OR (item.session_id IS NOT NULL AND (item.cohort_id IS NULL OR session_cohort.id <> item.cohort_id))
           OR (
               item.item_type = 'session_fee'
               AND (
                   item.session_id IS NULL
                   OR item.cohort_id IS NULL
                   OR item.unit_price IS NULL
                   OR item.item_amount <> item.unit_price
               )
           )
           OR (item.item_type = 'bonus' AND item.item_amount <= 0)
           OR (item.item_type = 'deduction' AND item.item_amount >= 0)
           OR (item.item_type = 'adjustment' AND item.item_amount = 0)
           OR (item.unit_price IS NOT NULL AND item.unit_price < 0)
        """
    )
    if invalid_teacher_item:
        raise ValueError("teacher_compensation_item has invalid teacher, session, or amount rules")

    invalid_commission_bill = _count(
        """
        SELECT COUNT(*)
        FROM channel_commission_bill AS bill
        JOIN org_institution AS inst ON inst.id = bill.institution_id
        LEFT JOIN staff_profile AS approver_staff
            ON approver_staff.user_id = bill.approver_user_id
           AND approver_staff.institution_id = bill.institution_id
        WHERE bill.updated_at < bill.created_at
           OR bill.created_at < inst.created_at
           OR bill.order_count < 0
           OR bill.commission_amount < 0
           OR (bill.approver_user_id IS NOT NULL AND approver_staff.id IS NULL)
           OR (bill.settled_at IS NOT NULL AND bill.settled_at < bill.created_at)
           OR (bill.paid_at IS NOT NULL AND (bill.settled_at IS NULL OR bill.paid_at < bill.settled_at))
           OR (
               bill.bill_status = 'pending'
               AND (
                   bill.approver_user_id IS NOT NULL
                   OR bill.settled_at IS NOT NULL
                   OR bill.paid_at IS NOT NULL
               )
           )
           OR (
               bill.bill_status = 'approved'
               AND (
                   bill.approver_user_id IS NULL
                   OR bill.settled_at IS NULL
                   OR bill.paid_at IS NOT NULL
               )
           )
           OR (
               bill.bill_status = 'paid'
               AND (
                   bill.approver_user_id IS NULL
                   OR bill.settled_at IS NULL
                   OR bill.paid_at IS NULL
               )
           )
        """
    )
    if invalid_commission_bill:
        raise ValueError("channel_commission_bill has invalid relation, status, or amount")

    invalid_commission_bill_agg = _count(
        """
        SELECT COUNT(*)
        FROM channel_commission_bill AS bill
        LEFT JOIN (
            SELECT
                bill_id,
                COUNT(*) AS order_count,
                SUM(commission_amount) AS commission_amount
            FROM channel_commission_item
            GROUP BY bill_id
        ) AS agg ON agg.bill_id = bill.id
        WHERE bill.order_count <> COALESCE(agg.order_count, 0)
           OR bill.commission_amount <> COALESCE(agg.commission_amount, 0)
        """
    )
    if invalid_commission_bill_agg:
        raise ValueError("channel_commission_bill aggregate values do not match item totals")
    checks.append("channel commission bills and items reconcile")

    invalid_commission_item = _count(
        """
        SELECT COUNT(*)
        FROM channel_commission_item AS item
        JOIN channel_commission_bill AS bill ON bill.id = item.bill_id
        JOIN order_item AS oi ON oi.id = item.order_item_id
        JOIN `order` AS o ON o.id = oi.order_id
        WHERE item.updated_at < item.created_at
           OR item.created_at < bill.created_at
           OR item.created_at < oi.created_at
           OR item.institution_id <> bill.institution_id
           OR oi.institution_id <> item.institution_id
           OR o.order_source_channel_id <> bill.channel_id
           OR item.commission_rate < 0
           OR item.commission_rate > 1
           OR item.base_amount < 0
           OR item.commission_amount < 0
           OR item.commission_amount <> ROUND(item.base_amount * item.commission_rate, 2)
        """
    )
    if invalid_commission_item:
        raise ValueError("channel_commission_item has invalid order linkage or commission formula")

    invalid_risk_alert = _count(
        """
        SELECT COUNT(*)
        FROM risk_alert_event AS alert
        JOIN org_institution AS inst ON inst.id = alert.institution_id
        LEFT JOIN student_profile AS sp ON sp.id = alert.related_student_id
        LEFT JOIN series_cohort AS cohort ON cohort.id = alert.cohort_id
        LEFT JOIN series_cohort_session AS session ON session.id = alert.session_id
        LEFT JOIN series_cohort_course AS cc ON cc.id = session.series_cohort_course_id
        LEFT JOIN series_cohort AS session_cohort ON session_cohort.id = cc.cohort_id
        LEFT JOIN order_item AS oi ON oi.id = alert.order_item_id
        LEFT JOIN refund_request AS refund ON refund.id = alert.refund_request_id
        LEFT JOIN session_exam_submission AS exam_sub ON exam_sub.id = alert.related_exam_attempt_id
        LEFT JOIN cohort_discussion_topic AS topic
            ON alert.ugc_content_type = 'topic'
           AND topic.id = alert.ugc_content_id
        LEFT JOIN cohort_discussion_post AS post
            ON alert.ugc_content_type = 'post'
           AND post.id = alert.ugc_content_id
        LEFT JOIN cohort_review AS review
            ON alert.ugc_content_type = 'review'
           AND review.id = alert.ugc_content_id
        WHERE alert.updated_at < alert.created_at
           OR alert.created_at < inst.created_at
           OR alert.detected_at < alert.created_at
           OR (alert.closed_at IS NOT NULL AND alert.closed_at < alert.detected_at)
           OR (alert.related_student_id IS NOT NULL AND sp.user_id <> alert.related_user_id)
           OR (alert.cohort_id IS NOT NULL AND cohort.institution_id <> alert.institution_id)
           OR (alert.session_id IS NOT NULL AND session_cohort.institution_id <> alert.institution_id)
           OR (alert.session_id IS NOT NULL AND (alert.cohort_id IS NULL OR session_cohort.id <> alert.cohort_id))
           OR (alert.order_item_id IS NOT NULL AND oi.institution_id <> alert.institution_id)
           OR (
               alert.refund_request_id IS NOT NULL
               AND (
                   refund.institution_id <> alert.institution_id
                   OR alert.order_item_id IS NULL
                   OR refund.order_item_id <> alert.order_item_id
               )
           )
           OR (alert.related_exam_attempt_id IS NOT NULL AND exam_sub.institution_id <> alert.institution_id)
           OR (
               alert.alert_type = 'refund_anomaly'
               AND (
                   alert.refund_request_id IS NULL
                   OR alert.order_item_id IS NULL
                   OR alert.related_exam_attempt_id IS NOT NULL
                   OR alert.ugc_content_type IS NOT NULL
                   OR alert.ugc_content_id IS NOT NULL
               )
           )
           OR (
               alert.alert_type = 'learning_anomaly'
               AND alert.cohort_id IS NULL
               AND alert.session_id IS NULL
           )
           OR (
               alert.alert_type = 'exam_anomaly'
               AND (
                   alert.related_exam_attempt_id IS NULL
                   OR alert.refund_request_id IS NOT NULL
                   OR alert.ugc_content_type IS NOT NULL
                   OR alert.ugc_content_id IS NOT NULL
               )
           )
           OR (
               alert.alert_type = 'ugc_anomaly'
               AND (
                   alert.ugc_content_type IS NULL
                   OR alert.ugc_content_id IS NULL
                   OR alert.refund_request_id IS NOT NULL
                   OR alert.order_item_id IS NOT NULL
                   OR alert.related_exam_attempt_id IS NOT NULL
               )
           )
           OR (
               alert.alert_type = 'operation_anomaly'
               AND alert.related_user_id IS NULL
           )
           OR (
               alert.alert_type <> 'ugc_anomaly'
               AND (
                   alert.ugc_content_type IS NOT NULL
                   OR alert.ugc_content_id IS NOT NULL
               )
           )
           OR (alert.ugc_content_type = 'topic' AND topic.id IS NULL)
           OR (alert.ugc_content_type = 'post' AND post.id IS NULL)
           OR (alert.ugc_content_type = 'review' AND review.id IS NULL)
           OR (alert.ugc_content_type = 'topic' AND topic.institution_id <> alert.institution_id)
           OR (alert.ugc_content_type = 'post' AND post.institution_id <> alert.institution_id)
           OR (alert.ugc_content_type = 'review' AND review.institution_id <> alert.institution_id)
           OR (alert.alert_status IN ('pending', 'in_progress') AND alert.closed_at IS NOT NULL)
           OR (alert.alert_status = 'closed' AND alert.closed_at IS NULL)
        """
    )
    if invalid_risk_alert:
        raise ValueError("risk_alert_event has invalid object linkage or alert-type fields")

    invalid_disposal = _count(
        """
        SELECT COUNT(*)
        FROM risk_disposal_record AS record
        JOIN risk_alert_event AS alert ON alert.id = record.alert_id
        LEFT JOIN staff_profile AS handler
            ON handler.user_id = record.handler_user_id
           AND handler.institution_id = alert.institution_id
        WHERE record.updated_at < record.created_at
           OR record.created_at < alert.created_at
           OR record.handled_at < record.created_at
           OR handler.id IS NULL
           OR (alert.closed_at IS NOT NULL AND record.handled_at > alert.closed_at)
           OR (record.action_result = 'false_positive' AND record.action_type <> 'mark_false_positive')
        """
    )
    if invalid_disposal:
        raise ValueError("risk_disposal_record has invalid handler, action, or timing")
    checks.append("risk alerts and disposal records match business objects")

    invalid_moderation = _count(
        """
        SELECT COUNT(*)
        FROM ugc_moderation_task AS task
        JOIN org_institution AS inst ON inst.id = task.institution_id
        LEFT JOIN cohort_discussion_topic AS topic ON topic.id = task.topic_id
        LEFT JOIN cohort_discussion_post AS post ON post.id = task.post_id
        LEFT JOIN cohort_review AS review ON review.id = task.review_id
        LEFT JOIN staff_profile AS moderator
            ON moderator.user_id = task.moderator_user_id
           AND moderator.institution_id = task.institution_id
        WHERE task.updated_at < task.created_at
           OR task.created_at < inst.created_at
           OR task.submitted_at < task.created_at
           OR (task.moderated_at IS NOT NULL AND task.moderated_at < task.submitted_at)
           OR (
               task.content_type = 'topic'
               AND (
                   task.topic_id IS NULL
                   OR task.post_id IS NOT NULL
                   OR task.review_id IS NOT NULL
                   OR topic.institution_id <> task.institution_id
                   OR task.submit_user_id <> topic.creator_user_id
               )
           )
           OR (
               task.content_type = 'post'
               AND (
                   task.post_id IS NULL
                   OR task.topic_id IS NULL
                   OR task.review_id IS NOT NULL
                   OR post.institution_id <> task.institution_id
                   OR post.topic_id <> task.topic_id
                   OR task.submit_user_id <> post.author_user_id
               )
           )
           OR (
               task.content_type = 'review'
               AND (
                   task.review_id IS NULL
                   OR task.topic_id IS NOT NULL
                   OR task.post_id IS NOT NULL
                   OR review.institution_id <> task.institution_id
                   OR task.submit_user_id <> review.user_id
               )
           )
           OR (task.moderator_user_id IS NOT NULL AND moderator.id IS NULL)
           OR (
               task.moderation_status = 'pending'
               AND (
                   task.moderator_user_id IS NOT NULL
                   OR task.moderated_at IS NOT NULL
                   OR task.reject_reason IS NOT NULL
               )
           )
           OR (
               task.moderation_status = 'approved'
               AND (
                   task.moderator_user_id IS NULL
                   OR task.moderated_at IS NULL
                   OR task.reject_reason IS NOT NULL
               )
           )
           OR (
               task.moderation_status = 'rejected'
               AND (
                   task.moderator_user_id IS NULL
                   OR task.moderated_at IS NULL
                   OR task.reject_reason IS NULL
               )
           )
        """
    )
    if invalid_moderation:
        raise ValueError("ugc_moderation_task has invalid content linkage or status fields")
    checks.append("ugc moderation tasks point to real content and valid moderators")

    return checks


def validate_layer7() -> list[str]:
    checks: list[str] = []

    core_tables = (
        "series",
        "series_cohort",
        "order",
        "order_item",
        "student_cohort_rel",
        "session_attendance",
        "session_homework_submission",
        "session_exam_submission",
        "cohort_discussion_topic",
        "service_ticket",
        "teacher_compensation_bill",
        "channel_commission_bill",
        "risk_alert_event",
        "ugc_moderation_task",
    )
    empty_tables = [
        table_name
        for table_name in core_tables
        if _count(f"SELECT COUNT(*) FROM `{table_name}`") == 0
    ]
    if empty_tables:
        raise ValueError(f"Layer7 contains empty core table(s): {', '.join(empty_tables)}")
    checks.append("core business tables are all non-empty")

    duplicate_uniques = {
        "series.series_code": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, series_code
                FROM series
                GROUP BY institution_id, series_code
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "series_cohort.cohort_code": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, cohort_code
                FROM series_cohort
                GROUP BY institution_id, cohort_code
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "coupon.coupon_code": """
            SELECT COUNT(*)
            FROM (
                SELECT coupon_code
                FROM coupon
                GROUP BY coupon_code
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "coupon_receive_record.receive_no": """
            SELECT COUNT(*)
            FROM (
                SELECT receive_no
                FROM coupon_receive_record
                GROUP BY receive_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "order.order_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, order_no
                FROM `order`
                GROUP BY institution_id, order_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "payment_record.payment_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, payment_no
                FROM payment_record
                GROUP BY institution_id, payment_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "refund_request.refund_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, refund_no
                FROM refund_request
                GROUP BY institution_id, refund_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "service_ticket.ticket_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, ticket_no
                FROM service_ticket
                GROUP BY institution_id, ticket_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "teacher_compensation_bill.bill_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, bill_no
                FROM teacher_compensation_bill
                GROUP BY institution_id, bill_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "channel_commission_bill.bill_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, bill_no
                FROM channel_commission_bill
                GROUP BY institution_id, bill_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "risk_alert_event.alert_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, alert_no
                FROM risk_alert_event
                GROUP BY institution_id, alert_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
        "ugc_moderation_task.task_no": """
            SELECT COUNT(*)
            FROM (
                SELECT institution_id, task_no
                FROM ugc_moderation_task
                GROUP BY institution_id, task_no
                HAVING COUNT(*) > 1
            ) AS t
        """,
    }
    duplicate_keys = [
        name for name, sql in duplicate_uniques.items() if _count(sql) > 0
    ]
    if duplicate_keys:
        raise ValueError(f"Layer7 unique business keys duplicated: {', '.join(duplicate_keys)}")
    checks.append("business unique keys are globally stable")

    broken_cross_domain_fk = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT oi.id
            FROM order_item AS oi
            LEFT JOIN `order` AS o ON o.id = oi.order_id
            WHERE o.id IS NULL
            UNION ALL
            SELECT pay.id
            FROM payment_record AS pay
            LEFT JOIN `order` AS o ON o.id = pay.order_id
            WHERE o.id IS NULL
            UNION ALL
            SELECT refund.id
            FROM refund_request AS refund
            LEFT JOIN order_item AS oi ON oi.id = refund.order_item_id
            WHERE oi.id IS NULL
            UNION ALL
            SELECT rel.id
            FROM student_cohort_rel AS rel
            LEFT JOIN order_item AS oi ON oi.id = rel.order_item_id
            WHERE oi.id IS NULL
            UNION ALL
            SELECT att.id
            FROM session_attendance AS att
            LEFT JOIN student_profile AS sp ON sp.id = att.student_id
            WHERE sp.id IS NULL
            UNION ALL
            SELECT sub.id
            FROM session_homework_submission AS sub
            LEFT JOIN session_homework AS hw ON hw.id = sub.homework_id
            WHERE hw.id IS NULL
            UNION ALL
            SELECT sub.id
            FROM session_exam_submission AS sub
            LEFT JOIN session_exam AS exam ON exam.id = sub.exam_id
            WHERE exam.id IS NULL
            UNION ALL
            SELECT post.id
            FROM cohort_discussion_post AS post
            LEFT JOIN cohort_discussion_topic AS topic ON topic.id = post.topic_id
            WHERE topic.id IS NULL
            UNION ALL
            SELECT survey.id
            FROM service_ticket_satisfaction_survey AS survey
            LEFT JOIN service_ticket AS ticket ON ticket.id = survey.ticket_id
            WHERE ticket.id IS NULL
            UNION ALL
            SELECT item.id
            FROM teacher_compensation_item AS item
            LEFT JOIN teacher_compensation_bill AS bill ON bill.id = item.bill_id
            WHERE bill.id IS NULL
            UNION ALL
            SELECT item.id
            FROM channel_commission_item AS item
            LEFT JOIN channel_commission_bill AS bill ON bill.id = item.bill_id
            WHERE bill.id IS NULL
            UNION ALL
            SELECT record.id
            FROM risk_disposal_record AS record
            LEFT JOIN risk_alert_event AS alert ON alert.id = record.alert_id
            WHERE alert.id IS NULL
        ) AS broken
        """
    )
    if broken_cross_domain_fk:
        raise ValueError("Layer7 cross-domain foreign key closure failed")
    checks.append("cross-domain foreign keys are closed")

    invalid_global_time_order = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT id
            FROM sys_user
            WHERE updated_at < created_at
            UNION ALL
            SELECT id
            FROM org_institution
            WHERE updated_at < created_at
            UNION ALL
            SELECT id
            FROM series
            WHERE updated_at < created_at
            UNION ALL
            SELECT id
            FROM series_cohort
            WHERE updated_at < created_at
            UNION ALL
            SELECT id
            FROM `order`
            WHERE updated_at < created_at
               OR (paid_at IS NOT NULL AND paid_at < created_at)
               OR (cancel_at IS NOT NULL AND cancel_at < created_at)
            UNION ALL
            SELECT id
            FROM payment_record
            WHERE updated_at < created_at
               OR (paid_at IS NOT NULL AND paid_at < created_at)
               OR (refund_at IS NOT NULL AND refund_at < created_at)
            UNION ALL
            SELECT id
            FROM refund_request
            WHERE updated_at < created_at
               OR applied_at < created_at
               OR (approved_at IS NOT NULL AND approved_at < applied_at)
               OR (refunded_at IS NOT NULL AND refunded_at < applied_at)
            UNION ALL
            SELECT id
            FROM student_cohort_rel
            WHERE updated_at < created_at
               OR enroll_at < created_at
               OR (completed_at IS NOT NULL AND completed_at < enroll_at)
               OR (cancelled_at IS NOT NULL AND cancelled_at < enroll_at)
            UNION ALL
            SELECT id
            FROM session_video_play
            WHERE updated_at < created_at
               OR started_at < created_at
               OR (ended_at IS NOT NULL AND ended_at < started_at)
            UNION ALL
            SELECT id
            FROM service_ticket
            WHERE updated_at < created_at
               OR (first_response_at IS NOT NULL AND first_response_at < created_at)
               OR (closed_at IS NOT NULL AND closed_at < created_at)
            UNION ALL
            SELECT id
            FROM risk_alert_event
            WHERE updated_at < created_at
               OR detected_at < created_at
               OR (closed_at IS NOT NULL AND closed_at < detected_at)
        ) AS invalid_time_rows
        """
    )
    if invalid_global_time_order:
        raise ValueError("Layer7 global time ordering failed")
    checks.append("global time ordering is consistent")

    invalid_global_amount_closure = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT o.id
            FROM `order` AS o
            LEFT JOIN (
                SELECT
                    order_id,
                    SUM(discount_amount) AS discount_amount,
                    SUM(payable_amount) AS payable_amount
                FROM order_item
                GROUP BY order_id
            ) AS agg ON agg.order_id = o.id
            WHERE o.discount_amount <> COALESCE(agg.discount_amount, 0)
               OR o.payable_amount <> COALESCE(agg.payable_amount, 0)
            UNION ALL
            SELECT bill.id
            FROM teacher_compensation_bill AS bill
            LEFT JOIN (
                SELECT
                    bill_id,
                    SUM(item_amount) AS payable_amount
                FROM teacher_compensation_item
                GROUP BY bill_id
            ) AS agg ON agg.bill_id = bill.id
            WHERE bill.payable_amount <> COALESCE(agg.payable_amount, 0)
            UNION ALL
            SELECT bill.id
            FROM channel_commission_bill AS bill
            LEFT JOIN (
                SELECT
                    bill_id,
                    SUM(commission_amount) AS commission_amount
                FROM channel_commission_item
                GROUP BY bill_id
            ) AS agg ON agg.bill_id = bill.id
            WHERE bill.commission_amount <> COALESCE(agg.commission_amount, 0)
        ) AS invalid_amount_rows
        """
    )
    if invalid_global_amount_closure:
        raise ValueError("Layer7 amount closure failed")
    checks.append("amount closure holds across orders, compensation, and commission")

    invalid_fulfillment_traceback = _count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT att.id
            FROM session_attendance AS att
            LEFT JOIN student_cohort_rel AS rel
                ON rel.cohort_id = att.cohort_id
               AND rel.student_id = att.student_id
            WHERE rel.id IS NULL
               OR rel.enroll_status IN ('cancelled', 'refunded')
            UNION ALL
            SELECT play.id
            FROM session_video_play AS play
            LEFT JOIN session_video AS video ON video.id = play.video_id
            LEFT JOIN session_asset AS asset ON asset.id = video.asset_id
            LEFT JOIN series_cohort_session AS ss ON ss.id = asset.session_id
            LEFT JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            LEFT JOIN student_cohort_rel AS rel
                ON rel.cohort_id = cc.cohort_id
               AND rel.student_id = play.student_id
            WHERE rel.id IS NULL
               OR rel.enroll_status IN ('cancelled', 'refunded')
            UNION ALL
            SELECT sub.id
            FROM session_homework_submission AS sub
            LEFT JOIN session_homework AS hw ON hw.id = sub.homework_id
            LEFT JOIN series_cohort_session AS ss ON ss.id = hw.session_id
            LEFT JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            LEFT JOIN student_cohort_rel AS rel
                ON rel.cohort_id = cc.cohort_id
               AND rel.student_id = sub.student_id
            WHERE rel.id IS NULL
               OR rel.enroll_status IN ('cancelled', 'refunded')
            UNION ALL
            SELECT sub.id
            FROM session_exam_submission AS sub
            LEFT JOIN session_exam AS exam ON exam.id = sub.exam_id
            LEFT JOIN series_cohort_session AS ss ON ss.id = exam.session_id
            LEFT JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            LEFT JOIN student_cohort_rel AS rel
                ON rel.cohort_id = cc.cohort_id
               AND rel.student_id = sub.student_id
            WHERE rel.id IS NULL
               OR rel.enroll_status IN ('cancelled', 'refunded')
            UNION ALL
            SELECT review.id
            FROM cohort_review AS review
            LEFT JOIN student_cohort_rel AS rel
                ON rel.cohort_id = review.cohort_id
               AND rel.student_id = review.student_id
            WHERE rel.id IS NULL
               OR rel.enroll_status IN ('cancelled', 'refunded')
            UNION ALL
            SELECT ticket.id
            FROM service_ticket AS ticket
            LEFT JOIN order_item AS oi ON oi.id = ticket.order_item_id
            LEFT JOIN refund_request AS refund ON refund.id = ticket.refund_request_id
            WHERE (ticket.order_item_id IS NOT NULL AND oi.id IS NULL)
               OR (ticket.refund_request_id IS NOT NULL AND refund.id IS NULL)
        ) AS invalid_trace_rows
        """
    )
    if invalid_fulfillment_traceback:
        raise ValueError("Layer7 fulfillment or service traceback failed")
    checks.append("learning, review, and service records trace back to real fulfillment or orders")

    return checks
