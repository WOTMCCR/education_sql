"""Generation configuration."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SEEDS_DIR = ROOT_DIR / "seeds"

load_dotenv(ROOT_DIR / ".env")

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ["DB_PORT"]),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "charset": "utf8mb4",
    "autocommit": False,
}

LAYERS = {
    1: {
        "name": "基础维度与组织主数据",
        "tables": [
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
        ],
    },
    2: {
        "name": "课程供给主数据",
        "tables": [
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
        ],
    },
    3: {
        "name": "题库、营销与转化准备",
        "tables": [
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
        ],
    },
    4: {
        "name": "交易与履约闭环",
        "tables": [
            "order",
            "order_item",
            "payment_record",
            "refund_request",
            "student_cohort_rel",
        ],
    },
    5: {
        "name": "学习、互动与服务过程",
        "tables": [
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
        ],
    },
    6: {
        "name": "经营衍生结果",
        "tables": [
            "teacher_compensation_bill",
            "teacher_compensation_item",
            "channel_commission_bill",
            "channel_commission_item",
            "risk_alert_event",
            "risk_disposal_record",
            "ugc_moderation_task",
        ],
    },
    7: {
        "name": "最终验收",
        "tables": [],
    },
}

GENERATION_PROFILES = {
    "smoke": {
        "seed": 1001,
        "batch_size": 2000,
        "users": 800,
        "staff_per_campus": 8,
        "series_template_limit": 36,
        "cohorts_per_series": 2,
        "courses_per_cohort": 2,
        "sessions_per_course": 4,
        "platform_coupons": 8,
        "institution_coupons": 4,
        "exposure_logs": 3000,
        "search_logs": 1200,
        "favorites": 1200,
        "cart_items": 1200,
        "consultations": 600,
        "coupon_receives": 1800,
        "orders": 900,
        "extra_refund_request_ratio": 0.1,
        "video_play_ratio": 0.35,
        "discussion_topic_ratio": 0.18,
        "review_ratio": 0.3,
        "service_ticket_ratio": 0.16,
        "ugc_moderation_target": 180,
        "risk_alert_target": 220,
    },
    "full": {
        "seed": 1001,
        "batch_size": 5000,
        "users": 100000,
        "staff_per_campus": 14,
        "series_template_limit": 0,
        "cohorts_per_series": 3,
        "courses_per_cohort": 2,
        "sessions_per_course": 4,
        "platform_coupons": 20,
        "institution_coupons": 8,
        "exposure_logs": 80000,
        "search_logs": 30000,
        "favorites": 30000,
        "cart_items": 30000,
        "consultations": 12000,
        "coupon_receives": 50000,
        "orders": 80000,
        "extra_refund_request_ratio": 0.1,
        "video_play_ratio": 0.4,
        "discussion_topic_ratio": 0.15,
        "review_ratio": 0.28,
        "service_ticket_ratio": 0.12,
        "ugc_moderation_target": 6000,
        "risk_alert_target": 9000,
    },
}

GENERATION_DEFAULTS = dict(GENERATION_PROFILES["full"])


@contextmanager
def generation_profile(profile: str):
    original = dict(GENERATION_DEFAULTS)
    GENERATION_DEFAULTS.clear()
    GENERATION_DEFAULTS.update(GENERATION_PROFILES[profile])
    try:
        yield GENERATION_DEFAULTS
    finally:
        GENERATION_DEFAULTS.clear()
        GENERATION_DEFAULTS.update(original)
