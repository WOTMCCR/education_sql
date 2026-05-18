# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import db_cursor, fetch_all, fetch_one
from app.main import app


class SampleData:
    @property
    def user_with_student(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT sp.user_id, sp.id AS student_id
            FROM student_profile AS sp
            WHERE sp.yn = 1
            ORDER BY sp.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"user_id": int(row["user_id"]), "student_id": int(row["student_id"])}

    @property
    def on_sale_series(self) -> dict[str, object]:
        row = fetch_one(
            """
            SELECT id, series_name
            FROM series
            WHERE sale_status = 'on_sale'
            ORDER BY id
            LIMIT 1
            """
        )
        assert row is not None
        return row

    @property
    def on_sale_series_with_cohort(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT s.id AS series_id, c.id AS cohort_id
            FROM series AS s
            JOIN series_cohort AS c ON c.series_id = s.id
            WHERE s.sale_status = 'on_sale' AND c.yn = 1
            ORDER BY s.id, c.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"series_id": int(row["series_id"]), "cohort_id": int(row["cohort_id"])}

    @property
    def active_rel(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT user_id, student_id, cohort_id, institution_id
            FROM student_cohort_rel
            WHERE enroll_status NOT IN ('cancelled', 'refunded')
            ORDER BY id
            LIMIT 1
            """
        )
        assert row is not None
        return {
            "user_id": int(row["user_id"]),
            "student_id": int(row["student_id"]),
            "cohort_id": int(row["cohort_id"]),
            "institution_id": int(row["institution_id"]),
        }

    @property
    def consultation_context(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT
                sp.user_id,
                sp.id AS student_id,
                rel.cohort_id,
                ch.id AS source_channel_id
            FROM student_profile AS sp
            JOIN student_cohort_rel AS rel
              ON rel.student_id = sp.id
             AND rel.enroll_status NOT IN ('cancelled', 'refunded')
            JOIN dim_channel AS ch ON ch.yn = 1
            ORDER BY rel.id, ch.id
            LIMIT 1
            """
        )
        assert row is not None
        return {
            "user_id": int(row["user_id"]),
            "student_id": int(row["student_id"]),
            "cohort_id": int(row["cohort_id"]),
            "source_channel_id": int(row["source_channel_id"]),
        }

    @property
    def alternative_channel_id(self) -> int:
        ctx = self.consultation_context
        row = fetch_one(
            """
            SELECT id
            FROM dim_channel
            WHERE yn = 1
              AND id <> %s
            ORDER BY id
            LIMIT 1
            """,
            (ctx["source_channel_id"],),
        )
        assert row is not None
        return int(row["id"])

    @property
    def available_coupon_for_user(self) -> dict[str, int]:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT sp.user_id, COUNT(record.id) AS receive_total
                FROM student_profile AS sp
                LEFT JOIN coupon_receive_record AS record
                  ON record.user_id = sp.user_id
                WHERE sp.yn = 1
                GROUP BY sp.user_id, sp.id
                ORDER BY receive_total ASC, sp.id ASC
                LIMIT 50
                """
            )
            users = cursor.fetchall()
            cursor.execute(
                """
                SELECT coupon.id AS coupon_id
                FROM coupon
                WHERE coupon.yn = 1
                  AND coupon.valid_from <= NOW()
                  AND coupon.valid_to >= NOW()
                  AND coupon.receive_count < coupon.total_count
                  AND coupon.per_user_limit = 1
                ORDER BY coupon.id
                """
            )
            coupons = cursor.fetchall()
            row = None
            if users and coupons:
                user_ids = [int(user["user_id"]) for user in users]
                coupon_ids = [int(coupon["coupon_id"]) for coupon in coupons]
                user_placeholders = ", ".join(["%s"] * len(user_ids))
                coupon_placeholders = ", ".join(["%s"] * len(coupon_ids))
                cursor.execute(
                    f"""
                    SELECT record.user_id, record.coupon_id
                    FROM coupon_receive_record AS record
                    WHERE record.user_id IN ({user_placeholders})
                      AND record.coupon_id IN ({coupon_placeholders})
                    """,
                    tuple(user_ids + coupon_ids),
                )
                received_pairs = {
                    (int(receive["user_id"]), int(receive["coupon_id"]))
                    for receive in cursor.fetchall()
                }
                for user_id in user_ids:
                    for coupon_id in coupon_ids:
                        if (user_id, coupon_id) not in received_pairs:
                            row = {"user_id": user_id, "coupon_id": coupon_id}
                            break
                    if row is not None:
                        break
            if row is None:
                cursor.execute(
                    """
                    SELECT sp.user_id, coupon.id AS coupon_id
                    FROM student_profile AS sp
                    JOIN coupon
                      ON coupon.yn = 1
                     AND coupon.valid_from <= NOW()
                     AND coupon.valid_to >= NOW()
                     AND coupon.receive_count < coupon.total_count
                    WHERE sp.yn = 1
                      AND coupon.per_user_limit = 1
                      AND NOT EXISTS (
                            SELECT 1
                            FROM coupon_receive_record AS record
                            WHERE record.user_id = sp.user_id
                              AND record.coupon_id = coupon.id
                        )
                    ORDER BY sp.id, coupon.id
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
        assert row is not None
        return {"user_id": int(row["user_id"]), "coupon_id": int(row["coupon_id"])}

    @property
    def inapplicable_coupon_order_context(self) -> dict[str, int]:
        receives = fetch_all(
            """
            SELECT
                record.id AS coupon_receive_record_id,
                record.coupon_id,
                record.user_id,
                sp.id AS student_id
            FROM coupon_receive_record AS record
            JOIN student_profile AS sp
              ON sp.user_id = record.user_id
             AND sp.yn = 1
            WHERE record.receive_status = 'unused'
              AND record.expired_at >= NOW()
            ORDER BY record.id
            LIMIT 100
            """
        )
        cohorts = fetch_all(
            """
            SELECT id AS cohort_id, series_id
            FROM series_cohort
            WHERE yn = 1
            ORDER BY id
            LIMIT 200
            """
        )
        coupon_series = fetch_all(
            """
            SELECT coupon_id, series_id
            FROM coupon_series_rel
            WHERE coupon_id IN (
                SELECT coupon_id
                FROM (
                    SELECT record.coupon_id
                    FROM coupon_receive_record AS record
                    WHERE record.receive_status = 'unused'
                      AND record.expired_at >= NOW()
                    ORDER BY record.id
                    LIMIT 100
                ) AS limited_receives
            )
            """
        )
        coupon_categories = fetch_all(
            """
            SELECT coupon_id, category_id
            FROM coupon_category_rel
            WHERE coupon_id IN (
                SELECT coupon_id
                FROM (
                    SELECT record.coupon_id
                    FROM coupon_receive_record AS record
                    WHERE record.receive_status = 'unused'
                      AND record.expired_at >= NOW()
                    ORDER BY record.id
                    LIMIT 100
                ) AS limited_receives
            )
            """
        )
        series_categories = fetch_all(
            """
            SELECT series_id, category_id
            FROM series_category_rel
            WHERE series_id IN (
                SELECT series_id
                FROM (
                    SELECT series_id
                    FROM series_cohort
                    WHERE yn = 1
                    ORDER BY id
                    LIMIT 200
                ) AS limited_cohorts
            )
            """
        )

        coupon_series_map: dict[int, set[int]] = {}
        for row in coupon_series:
            coupon_series_map.setdefault(int(row["coupon_id"]), set()).add(int(row["series_id"]))

        coupon_category_map: dict[int, set[int]] = {}
        for row in coupon_categories:
            coupon_category_map.setdefault(int(row["coupon_id"]), set()).add(
                int(row["category_id"])
            )

        series_category_map: dict[int, set[int]] = {}
        for row in series_categories:
            series_category_map.setdefault(int(row["series_id"]), set()).add(
                int(row["category_id"])
            )

        for receive in receives:
            coupon_id = int(receive["coupon_id"])
            applicable_series = coupon_series_map.get(coupon_id, set())
            applicable_categories = coupon_category_map.get(coupon_id, set())
            for cohort in cohorts:
                series_id = int(cohort["series_id"])
                series_ok = not applicable_series or series_id in applicable_series
                category_ok = (
                    not applicable_categories
                    or bool(series_category_map.get(series_id, set()) & applicable_categories)
                )
                if not (series_ok and category_ok):
                    return {
                        "user_id": int(receive["user_id"]),
                        "student_id": int(receive["student_id"]),
                        "cohort_id": int(cohort["cohort_id"]),
                        "coupon_receive_record_id": int(receive["coupon_receive_record_id"]),
                    }

        raise AssertionError("No inapplicable coupon order context found")

    @property
    def review_context(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT rel.user_id, rel.student_id, rel.cohort_id
            FROM student_cohort_rel AS rel
            WHERE rel.enroll_status NOT IN ('cancelled', 'refunded')
              AND NOT EXISTS (
                    SELECT 1
                    FROM cohort_review AS review
                    WHERE review.cohort_id = rel.cohort_id
                      AND review.student_id = rel.student_id
                      AND review.yn = 1
                )
            ORDER BY rel.id
            LIMIT 1
            """
        )
        assert row is not None
        return {
            "user_id": int(row["user_id"]),
            "student_id": int(row["student_id"]),
            "cohort_id": int(row["cohort_id"]),
        }

    @property
    def ticket_context(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT oi.user_id, oi.student_id, oi.id AS order_item_id
            FROM order_item AS oi
            WHERE oi.order_item_status IN ('paid', 'completed')
            ORDER BY oi.id
            LIMIT 1
            """
        )
        assert row is not None
        return {
            "user_id": int(row["user_id"]),
            "student_id": int(row["student_id"]),
            "order_item_id": int(row["order_item_id"]),
        }

    @property
    def closed_unsurveyed_ticket(self) -> dict[str, int] | None:
        row = fetch_one(
            """
            SELECT t.id AS ticket_id, t.user_id
            FROM service_ticket AS t
            LEFT JOIN service_ticket_satisfaction_survey AS s
              ON s.ticket_id = t.id AND s.yn = 1
            WHERE t.ticket_status = 'closed'
              AND t.yn = 1
              AND s.id IS NULL
            ORDER BY t.id
            LIMIT 1
            """
        )
        if row is None:
            return None
        return {"ticket_id": int(row["ticket_id"]), "user_id": int(row["user_id"])}

    @property
    def accessible_session(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT session.id AS session_id, rel.user_id
            FROM series_cohort_session AS session
            JOIN series_cohort_course AS course
              ON course.id = session.series_cohort_course_id
            JOIN student_cohort_rel AS rel
              ON rel.cohort_id = course.cohort_id
             AND rel.enroll_status NOT IN ('cancelled', 'refunded')
            ORDER BY session.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"session_id": int(row["session_id"]), "user_id": int(row["user_id"])}

    @property
    def accessible_video(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT video.id AS video_id, rel.user_id
            FROM session_video AS video
            JOIN session_asset AS asset ON asset.id = video.asset_id
            JOIN series_cohort_session AS session ON session.id = asset.session_id
            JOIN series_cohort_course AS course
              ON course.id = session.series_cohort_course_id
            JOIN student_cohort_rel AS rel
              ON rel.cohort_id = course.cohort_id
             AND rel.enroll_status NOT IN ('cancelled', 'refunded')
            ORDER BY video.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"video_id": int(row["video_id"]), "user_id": int(row["user_id"])}

    @property
    def accessible_homework(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT hw.id AS homework_id, rel.user_id
            FROM session_homework AS hw
            JOIN series_cohort_session AS session ON session.id = hw.session_id
            JOIN series_cohort_course AS course
              ON course.id = session.series_cohort_course_id
            JOIN student_cohort_rel AS rel
              ON rel.cohort_id = course.cohort_id
             AND rel.enroll_status NOT IN ('cancelled', 'refunded')
            ORDER BY hw.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"homework_id": int(row["homework_id"]), "user_id": int(row["user_id"])}

    @property
    def accessible_exam(self) -> dict[str, int]:
        row = fetch_one(
            """
            SELECT exam.id AS exam_id, rel.user_id
            FROM session_exam AS exam
            JOIN series_cohort_session AS session ON session.id = exam.session_id
            JOIN series_cohort_course AS course
              ON course.id = session.series_cohort_course_id
            JOIN student_cohort_rel AS rel
              ON rel.cohort_id = course.cohort_id
             AND rel.enroll_status NOT IN ('cancelled', 'refunded')
            ORDER BY exam.id
            LIMIT 1
            """
        )
        assert row is not None
        return {"exam_id": int(row["exam_id"]), "user_id": int(row["user_id"])}


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def samples() -> SampleData:
    return SampleData()


@pytest.fixture()
def db():
    return {
        "fetch_one": fetch_one,
        "fetch_all": fetch_all,
        "cursor": db_cursor,
    }


def headers(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


@pytest.fixture()
def user_headers():
    return headers
