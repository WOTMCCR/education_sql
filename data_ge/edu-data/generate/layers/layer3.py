"""Layer3: question bank, marketing, and conversion preparation data."""

from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS, SEEDS_DIR
from ..db import db
from ..insert_support import insert_dict_rows
from .base import BaseGenerator
from .validations import validate_layer3

EXPOSURE_SCENES = (
    "recommendation",
    "search",
    "activity",
    "category",
    "learning_center",
)
VISIT_SOURCES = (
    "recommendation",
    "search_result",
    "activity_page",
    "favorite_list",
    "shopping_cart",
    "direct_access",
)
SEARCH_SOURCES = ("home_page", "course_list_page", "category_page", "learning_center")
FAVORITE_SOURCES = ("series_detail", "search_result", "recommendation", "activity_page")
CART_SOURCES = ("series_detail", "search_result", "recommendation", "activity_page")
CONSULT_CHANNELS = ("phone", "online_chat", "wechat", "offline_visit")
RECEIVE_SOURCES = (
    "coupon_center",
    "activity_page",
    "series_detail",
    "order_settlement",
    "consultation",
)
DEVICE_TYPES = ("ios", "android", "web", "wechat_mini_program")


class Layer3Generator(BaseGenerator):
    layer = 3
    layer_name = "题库、营销与转化准备"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]) + 3)
        self.now = self.local_now()
        self.today = self.now.date()
        self.platform_coupon_start = self.fetch_platform_coupon_start()

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        counts["question_bank"] = self.generate_question_banks()
        counts["question"] = self.generate_questions()
        counts["session_homework_question_rel"] = self.generate_homework_questions()
        counts["session_exam_question_rel"] = self.generate_exam_questions()
        counts["coupon"] = self.generate_coupons()
        counts["coupon_category_rel"] = self.generate_coupon_category_rels()
        counts["coupon_series_rel"] = self.generate_coupon_series_rels()
        counts["series_exposure_log"] = self.generate_exposure_logs()
        counts["series_visit_log"] = self.generate_visit_logs()
        counts["series_search_log"] = self.generate_search_logs()
        counts["series_favorite"] = self.generate_favorites()
        counts["shopping_cart_item"] = self.generate_cart_items()
        counts["consultation_record"] = self.generate_consultations()
        counts["coupon_receive_record"] = self.generate_coupon_receives()
        self.refresh_coupon_receive_counters()

        self.log_table_counts(counts)
        for check in validate_layer3():
            self.log(f"  [OK] validation: {check}")

    def clear_layer_tables(self) -> None:
        tables = list(reversed(LAYERS[self.layer]["tables"]))
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for table in tables:
                db.execute(f"TRUNCATE TABLE `{table}`")
        finally:
            db.execute("SET FOREIGN_KEY_CHECKS = 1")

    def insert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        return insert_dict_rows(table_name, rows)

    def random_datetime(
        self, start: datetime | date, end: datetime | date | None = None
    ) -> datetime:
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if end is None:
            end = self.now
        elif isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())
        if end < start:
            end = start
        seconds = max(0, int((end - start).total_seconds()))
        return start + timedelta(seconds=self.random.randint(0, seconds))

    def bounded_delay_datetime(
        self,
        base: datetime,
        max_days: int,
        min_minutes: int = 0,
    ) -> datetime:
        start = base + timedelta(minutes=min_minutes)
        end = min(self.now, base + timedelta(days=max_days))
        if end < start:
            end = start
        return self.random_datetime(start, end)

    def fetch_platform_coupon_start(self) -> datetime:
        row = db.fetch_one("SELECT MIN(created_at) AS min_created_at FROM org_institution")
        min_created_at = row["min_created_at"] if row else None
        return min_created_at or (self.now - timedelta(days=730))

    def load_seed_rows(self, filename: str) -> list[dict[str, str]]:
        path = SEEDS_DIR / "3_question" / filename
        with path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def generate_question_banks(self) -> int:
        institutions = self.fetch_institutions()
        categories = self.fetch_by_code("dim_course_category", "category_code")
        seed_rows = self.load_seed_rows("question_bank.csv")
        rows: list[dict[str, Any]] = []
        for institution in institutions:
            for seed in seed_rows:
                category = categories[seed["category_level3_code"]]
                created_at = self.random_datetime(institution["created_at"])
                rows.append(
                    {
                        "institution_id": institution["id"],
                        "category_id": category["id"],
                        "bank_code": seed["question_bank_code"],
                        "bank_name": seed["question_bank_name"],
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(created_at),
                    }
                )
        return self.insert_rows("question_bank", rows)

    def generate_questions(self) -> int:
        seed_rows = self.load_seed_rows("question.csv")
        questions_by_bank: dict[str, list[dict[str, str]]] = {}
        for seed in seed_rows:
            questions_by_bank.setdefault(seed["question_bank_code"], []).append(seed)

        question_types = self.fetch_by_code("dim_question_type", "type_code")
        banks = self.fetch_question_banks()
        rows: list[dict[str, Any]] = []
        for bank in banks:
            for seed in questions_by_bank.get(bank["bank_code"], []):
                created_at = self.random_datetime(bank["created_at"])
                options_json = seed["options_json"].strip() or None
                rows.append(
                    {
                        "bank_id": bank["id"],
                        "question_code": seed["question_code"],
                        "question_type_id": question_types[seed["question_type_code"]]["id"],
                        "stem": seed["stem"],
                        "options_json": options_json,
                        "answer_text": seed["answer_text"],
                        "analysis_text": seed["analysis_text"] or None,
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(created_at),
                    }
                )
        return self.insert_rows("question", rows)

    def generate_homework_questions(self) -> int:
        homeworks = self.fetch_homeworks_with_category()
        questions = self.fetch_questions_by_institution_and_category()
        rows: list[dict[str, Any]] = []
        for homework in homeworks:
            candidates = questions[(homework["institution_id"], homework["category_id"])]
            selected = self.pick_questions(candidates, 5)
            for index, question in enumerate(selected, start=1):
                created_at = self.random_datetime(
                    max(homework["created_at"], question["created_at"])
                )
                rows.append(
                    {
                        "homework_id": homework["id"],
                        "question_id": question["id"],
                        "sort_no": index,
                        "score": Decimal("20.00"),
                        "created_at": created_at,
                        "updated_at": self.random_datetime(created_at),
                    }
                )
        return self.insert_rows("session_homework_question_rel", rows)

    def generate_exam_questions(self) -> int:
        exams = self.fetch_exams_with_category()
        questions = self.fetch_questions_by_institution_and_category()
        rows: list[dict[str, Any]] = []
        for exam in exams:
            candidates = questions[(exam["institution_id"], exam["category_id"])]
            selected = self.pick_questions(candidates, 10)
            score = Decimal(str(exam["total_score"])) / Decimal(len(selected))
            for index, question in enumerate(selected, start=1):
                created_at = self.random_datetime(
                    max(exam["created_at"], question["created_at"])
                )
                rows.append(
                    {
                        "exam_id": exam["id"],
                        "question_id": question["id"],
                        "sort_no": index,
                        "score": score.quantize(Decimal("0.01")),
                        "created_at": created_at,
                        "updated_at": self.random_datetime(created_at),
                    }
                )
        return self.insert_rows("session_exam_question_rel", rows)

    def generate_coupons(self) -> int:
        institutions = self.fetch_institutions()
        rows: list[dict[str, Any]] = []
        platform_count = int(GENERATION_DEFAULTS["platform_coupons"])
        institution_count = int(GENERATION_DEFAULTS["institution_coupons"])

        for index in range(1, platform_count + 1):
            rows.append(self.build_coupon_row(None, "platform", index))
        for institution in institutions:
            for index in range(1, institution_count + 1):
                rows.append(self.build_coupon_row(institution, "institution", index))
        return self.insert_rows("coupon", rows)

    def build_coupon_row(
        self,
        institution: dict[str, Any] | None,
        issuer_scope: str,
        index: int,
    ) -> dict[str, Any]:
        coupon_type = "cash" if index % 2 else "discount"
        created_floor = (
            institution["created_at"]
            if institution
            else self.platform_coupon_start
        )
        created_at = self.random_datetime(created_floor, self.now - timedelta(days=30))
        valid_from = created_at + timedelta(days=self.random.randint(1, 10))
        valid_to = self.now + timedelta(days=self.random.choice((30, 60, 90, 120)))
        amount = Decimal(str(self.random.choice((50, 80, 100, 150, 200))))
        rate = Decimal(str(self.random.choice(("0.80", "0.85", "0.90", "0.95"))))
        prefix = "PLAT" if institution is None else f"INS{institution['id']:03d}"
        return {
            "institution_id": None if institution is None else institution["id"],
            "issuer_scope": issuer_scope,
            "coupon_code": f"CP{prefix}{index:03d}",
            "coupon_name": (
                f"{'平台' if institution is None else institution['institution_name']}"
                f"{'满减券' if coupon_type == 'cash' else '折扣券'}{index:02d}"
            ),
            "coupon_type": coupon_type,
            "discount_amount": amount if coupon_type == "cash" else None,
            "discount_rate": rate if coupon_type == "discount" else None,
            "threshold_amount": amount * Decimal("5") if coupon_type == "cash" else Decimal("0"),
            "total_count": self.random.choice((1000, 2000, 5000, 10000)),
            "per_user_limit": 1,
            "receive_count": 0,
            "used_count": 0,
            "yn": 1,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "created_at": created_at,
            "updated_at": self.random_datetime(created_at),
        }

    def generate_coupon_category_rels(self) -> int:
        coupons = self.fetch_coupons()
        categories = self.fetch_leaf_categories()
        rows: list[dict[str, Any]] = []
        for coupon in coupons:
            category = categories[coupon["id"] % len(categories)]
            created_at = self.random_datetime(coupon["created_at"])
            rows.append(
                {
                    "coupon_id": coupon["id"],
                    "category_id": category["id"],
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at),
                }
            )
        return self.insert_rows("coupon_category_rel", rows)

    def generate_coupon_series_rels(self) -> int:
        coupons = self.fetch_coupons()
        series_by_institution = self.fetch_series_by_institution()
        all_series = [series for rows in series_by_institution.values() for series in rows]
        rows: list[dict[str, Any]] = []
        for coupon in coupons:
            candidates = (
                series_by_institution[coupon["institution_id"]]
                if coupon["institution_id"] is not None
                else all_series
            )
            series = candidates[coupon["id"] % len(candidates)]
            created_at = self.random_datetime(max(coupon["created_at"], series["created_at"]))
            rows.append(
                {
                    "coupon_id": coupon["id"],
                    "series_id": series["id"],
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at),
                }
            )
        return self.insert_rows("coupon_series_rel", rows)

    def generate_exposure_logs(self) -> int:
        users = self.fetch_student_users()
        series_rows = self.fetch_series()
        count = int(GENERATION_DEFAULTS["exposure_logs"])
        rows: list[dict[str, Any]] = []
        for index in range(count):
            user = users[index % len(users)]
            series = series_rows[self.random.randrange(len(series_rows))]
            created_at = self.bounded_delay_datetime(
                max(user["created_at"], series["created_at"]),
                max_days=120,
            )
            rows.append(
                {
                    "user_id": user["id"],
                    "series_id": series["id"],
                    "exposure_scene": self.random.choice(EXPOSURE_SCENES),
                    "position_no": self.random.randint(1, 30),
                    "device_type": self.random.choice(DEVICE_TYPES),
                    "exposed_at": created_at + timedelta(seconds=self.random.randint(0, 60)),
                    "created_at": created_at,
                }
            )
        return self.insert_rows("series_exposure_log", rows)

    def generate_visit_logs(self) -> int:
        exposures = self.fetch_exposure_logs()
        rows: list[dict[str, Any]] = []
        for exposure in exposures[::2]:
            enter_at = exposure["exposed_at"] + timedelta(seconds=self.random.randint(5, 300))
            stay_seconds = self.random.randint(10, 1800)
            leave_at = enter_at + timedelta(seconds=stay_seconds)
            rows.append(
                {
                    "user_id": exposure["user_id"],
                    "series_id": exposure["series_id"],
                    "ref_exposure_id": exposure["id"],
                    "visit_source": self.visit_source_from_scene(exposure["exposure_scene"]),
                    "stay_seconds": stay_seconds,
                    "enter_at": enter_at,
                    "leave_at": leave_at,
                    "created_at": enter_at,
                }
            )
        return self.insert_rows("series_visit_log", rows)

    def generate_search_logs(self) -> int:
        users = self.fetch_student_users()
        series_rows = self.fetch_series()
        keywords = self.fetch_search_keywords()
        count = int(GENERATION_DEFAULTS["search_logs"])
        rows: list[dict[str, Any]] = []
        for index in range(count):
            user = users[(index * 7) % len(users)]
            clicked = series_rows[(index * 11) % len(series_rows)]
            created_at = self.bounded_delay_datetime(
                max(user["created_at"], clicked["created_at"]),
                max_days=90,
            )
            has_click = index % 4 != 0
            rows.append(
                {
                    "user_id": user["id"],
                    "keyword_text": keywords[index % len(keywords)],
                    "search_source": self.random.choice(SEARCH_SOURCES),
                    "result_count": self.random.randint(1, 80),
                    "clicked_series_id": clicked["id"] if has_click else None,
                    "searched_at": created_at + timedelta(seconds=self.random.randint(0, 60)),
                    "created_at": created_at,
                }
            )
        return self.insert_rows("series_search_log", rows)

    def generate_favorites(self) -> int:
        users = self.fetch_student_users()
        series_rows = self.fetch_series()
        count = min(int(GENERATION_DEFAULTS["favorites"]), len(users) * len(series_rows))
        used_pairs: set[tuple[int, int]] = set()
        rows: list[dict[str, Any]] = []
        index = 0
        while len(rows) < count:
            user = users[index % len(users)]
            series = series_rows[(index * 17) % len(series_rows)]
            index += 1
            pair = (user["id"], series["id"])
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            created_at = self.bounded_delay_datetime(
                max(user["created_at"], series["created_at"]),
                max_days=150,
            )
            rows.append(
                {
                    "user_id": user["id"],
                    "series_id": series["id"],
                    "favorite_source": self.random.choice(FAVORITE_SOURCES),
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at),
                }
            )
        return self.insert_rows("series_favorite", rows)

    def generate_cart_items(self) -> int:
        users = self.fetch_student_users()
        cohorts = self.fetch_cohorts()
        count = min(int(GENERATION_DEFAULTS["cart_items"]), len(users) * len(cohorts))
        used_pairs: set[tuple[int, int]] = set()
        rows: list[dict[str, Any]] = []
        index = 0
        while len(rows) < count:
            user = users[index % len(users)]
            cohort = cohorts[(index * 19) % len(cohorts)]
            index += 1
            pair = (user["id"], cohort["id"])
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            created_at = self.bounded_delay_datetime(
                max(user["created_at"], cohort["created_at"]),
                max_days=60,
            )
            added_at = min(
                self.now,
                created_at + timedelta(minutes=self.random.randint(0, 120)),
            )
            removed_at = None
            if index % 5 == 0:
                removed_at = min(
                    self.now,
                    added_at + timedelta(days=self.random.randint(1, 15)),
                )
            updated_floor = removed_at or created_at
            rows.append(
                {
                    "user_id": user["id"],
                    "cohort_id": cohort["id"],
                    "unit_price": cohort["sale_price"],
                    "cart_source": self.random.choice(CART_SOURCES),
                    "added_at": added_at,
                    "removed_at": removed_at,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(updated_floor),
                }
            )
        return self.insert_rows("shopping_cart_item", rows)

    def generate_consultations(self) -> int:
        users = self.fetch_student_users()
        cohorts = self.fetch_cohorts()
        consultants = self.fetch_consultants_by_institution()
        channels = self.fetch_channels()
        count = int(GENERATION_DEFAULTS["consultations"])
        rows: list[dict[str, Any]] = []
        for index in range(count):
            user = users[(index * 5) % len(users)]
            cohort = cohorts[(index * 13) % len(cohorts)]
            consultant = consultants[cohort["institution_id"]][
                index % len(consultants[cohort["institution_id"]])
            ]
            channel = channels[index % len(channels)]
            created_at = self.bounded_delay_datetime(
                max(user["created_at"], cohort["created_at"]),
                max_days=45,
            )
            rows.append(
                {
                    "user_id": user["id"],
                    "cohort_id": cohort["id"],
                    "consultant_user_id": consultant["user_id"],
                    "source_channel_id": channel["id"],
                    "consult_channel": self.random.choice(CONSULT_CHANNELS),
                    "contact_mobile": user["mobile"],
                    "consult_content": f"咨询{cohort['cohort_name']}的课程安排和报名优惠。",
                    "consulted_at": created_at + timedelta(minutes=self.random.randint(0, 60)),
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at),
                }
            )
        return self.insert_rows("consultation_record", rows)

    def generate_coupon_receives(self) -> int:
        coupons = self.fetch_coupons()
        users = self.fetch_student_users()
        count = int(GENERATION_DEFAULTS["coupon_receives"])
        rows: list[dict[str, Any]] = []
        if not coupons or not users:
            return 0
        max_pairs = len(coupons) * len(users)
        target_count = min(count, max_pairs)
        for index in range(target_count):
            coupon = coupons[index % len(coupons)]
            user = users[(index // len(coupons)) % len(users)]
            created_at = self.random_datetime(
                max(coupon["created_at"], user["created_at"]),
                self.now,
            )
            received_at = max(created_at, coupon["valid_from"])
            if received_at > coupon["valid_to"]:
                received_at = coupon["valid_from"]
            if received_at > self.now:
                received_at = self.now
            status = "unused"
            expired_at = coupon["valid_to"]
            updated_at = self.random_datetime(received_at, self.now)
            rows.append(
                {
                    "coupon_id": coupon["id"],
                    "user_id": user["id"],
                    "receive_no": f"RCV{index + 1:010d}",
                    "receive_source": self.random.choice(RECEIVE_SOURCES),
                    "receive_status": status,
                    "yn": 1,
                    "received_at": received_at,
                    "used_at": None,
                    "expired_at": expired_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
        return self.insert_rows("coupon_receive_record", rows)

    def refresh_coupon_receive_counters(self) -> None:
        db.execute(
            """
            UPDATE coupon AS c
            LEFT JOIN (
                SELECT
                    coupon_id,
                    COUNT(*) AS receive_count,
                    SUM(receive_status = 'used') AS used_count
                FROM coupon_receive_record
                GROUP BY coupon_id
            ) AS r ON r.coupon_id = c.id
            SET
                c.receive_count = COALESCE(r.receive_count, 0),
                c.used_count = COALESCE(r.used_count, 0),
                c.updated_at = GREATEST(c.updated_at, COALESCE(
                    (
                        SELECT MAX(updated_at)
                        FROM coupon_receive_record
                        WHERE coupon_id = c.id
                    ),
                    c.updated_at
                ))
            """
        )

    def pick_questions(
        self, candidates: list[dict[str, Any]], count: int
    ) -> list[dict[str, Any]]:
        if len(candidates) <= count:
            return candidates
        offset = self.random.randrange(len(candidates))
        return [candidates[(offset + index) % len(candidates)] for index in range(count)]

    def visit_source_from_scene(self, scene: str) -> str:
        mapping = {
            "recommendation": "recommendation",
            "search": "search_result",
            "activity": "activity_page",
            "category": "recommendation",
            "learning_center": "direct_access",
        }
        return mapping[scene]

    def fetch_by_code(self, table_name: str, code_column: str) -> dict[str, dict[str, Any]]:
        rows = db.fetch_all(f"SELECT * FROM `{table_name}` ORDER BY id")
        return {str(row[code_column]): row for row in rows}

    def fetch_institutions(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_institution ORDER BY id")

    def fetch_question_banks(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM question_bank ORDER BY institution_id, id")

    def fetch_leaf_categories(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT c.*
            FROM dim_course_category AS c
            LEFT JOIN dim_course_category AS child ON child.parent_id = c.id
            WHERE child.id IS NULL
            ORDER BY c.id
            """
        )

    def fetch_questions_by_institution_and_category(
        self,
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT
                q.*,
                b.institution_id,
                b.category_id
            FROM `question` AS q
            JOIN question_bank AS b ON b.id = q.bank_id
            ORDER BY b.institution_id, b.category_id, q.id
            """
        )
        result: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault((row["institution_id"], row["category_id"]), []).append(row)
        return result

    def fetch_homeworks_with_category(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                hw.*,
                c.institution_id,
                rel.category_id
            FROM session_homework AS hw
            JOIN series_cohort_session AS ss ON ss.id = hw.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series_category_rel AS rel ON rel.series_id = c.series_id
            ORDER BY hw.id
            """
        )

    def fetch_exams_with_category(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                exam.*,
                c.institution_id,
                rel.category_id
            FROM session_exam AS exam
            JOIN series_cohort_session AS ss ON ss.id = exam.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series_category_rel AS rel ON rel.series_id = c.series_id
            ORDER BY exam.id
            """
        )

    def fetch_coupons(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM coupon ORDER BY id")

    def fetch_series(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM series ORDER BY id")

    def fetch_series_by_institution(self) -> dict[int, list[dict[str, Any]]]:
        rows = self.fetch_series()
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_cohorts(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT *
            FROM series_cohort
            WHERE created_at <= %s
            ORDER BY id
            """,
            (self.now,),
        )

    def fetch_student_users(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                u.id,
                u.mobile,
                u.created_at,
                sp.id AS student_id
            FROM student_profile AS sp
            JOIN sys_user AS u ON u.id = sp.user_id
            ORDER BY u.id
            """
        )

    def fetch_exposure_logs(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM series_exposure_log ORDER BY id")

    def fetch_search_keywords(self) -> list[str]:
        rows = db.fetch_all(
            """
            SELECT DISTINCT series_name
            FROM series
            ORDER BY series_name
            LIMIT 200
            """
        )
        keywords = [row["series_name"].split("·")[0] for row in rows]
        return keywords or ["课程"]

    def fetch_consultants_by_institution(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT s.*
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE r.role_category IN ('sales', 'service')
            ORDER BY s.institution_id, s.id
            """
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_channels(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM dim_channel ORDER BY id")
