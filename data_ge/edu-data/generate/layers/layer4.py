"""Layer4: transaction and fulfillment closure data."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from ..insert_support import insert_dict_rows
from .base import BaseGenerator
from .validations import validate_layer4

PAYMENT_CHANNELS = (
    "wechat_pay",
    "alipay",
    "bank_card",
    "offline_transfer",
    "public_account",
    "campus_cashier",
)
ORDER_STATUSES = (
    "pending",
    "paid",
    "completed",
    "cancelled",
    "partial_refunded",
    "refunded",
)
REFUND_REASONS = (
    "学习计划调整，申请退费。",
    "课程节奏不匹配，申请退款。",
    "重复购买同类课程，申请退费。",
    "个人时间冲突，申请退费。",
)
REFUND_TYPES = (
    "personal_reason",
    "course_unsatisfied",
    "schedule_conflict",
    "duplicate_purchase",
)
ORDER_SOURCE_DELAY_DAYS = {
    "cart": 14,
    "consultation": 7,
    "favorite": 30,
    "visit": 10,
    "search": 7,
}


class Layer4Generator(BaseGenerator):
    layer = 4
    layer_name = "交易与履约闭环"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]) + 4)
        self.now = self.local_now()
        self.today = self.now.date()
        self.linked_coupon_receive_ids: set[int] = set()
        self.used_coupon_events: list[tuple[int, datetime]] = []

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()
        self.reset_layer4_side_effects()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        order_contexts = self.build_order_contexts()
        counts["order"] = self.insert_rows(
            "order", [context["order"] for context in order_contexts]
        )
        self.attach_order_ids(order_contexts)
        counts["order_item"] = self.insert_rows(
            "order_item", [context["order_item"] for context in order_contexts]
        )
        self.attach_order_item_ids(order_contexts)
        counts["payment_record"] = self.insert_rows(
            "payment_record", [context["payment_record"] for context in order_contexts]
        )
        self.attach_payment_ids(order_contexts)
        refund_rows = self.build_refund_requests(order_contexts)
        counts["refund_request"] = self.insert_rows("refund_request", refund_rows)
        cohort_rel_rows = self.build_student_cohort_rels(order_contexts)
        counts["student_cohort_rel"] = self.insert_rows(
            "student_cohort_rel", cohort_rel_rows
        )
        self.apply_coupon_usage()
        self.refresh_coupon_receive_counters()
        self.refresh_cohort_student_counts()

        self.log_table_counts(counts)
        for check in validate_layer4():
            self.log(f"  [OK] validation: {check}")

    def clear_layer_tables(self) -> None:
        tables = list(reversed(LAYERS[self.layer]["tables"]))
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for table in tables:
                db.execute(f"TRUNCATE TABLE `{table}`")
        finally:
            db.execute("SET FOREIGN_KEY_CHECKS = 1")

    def reset_layer4_side_effects(self) -> None:
        db.execute(
            """
            UPDATE coupon_receive_record
            SET
                receive_status = 'unused',
                used_at = NULL
            WHERE receive_status = 'used'
            """
        )
        db.execute("UPDATE coupon SET used_count = 0")
        db.execute("UPDATE series_cohort SET current_student_count = 0")

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

    def money(self, value: Decimal | int | float | str) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def cap_at_now(self, value: datetime) -> datetime:
        return min(value, self.now)

    def order_time_buffer(self, order_status: str) -> timedelta:
        if order_status == "cancelled":
            return timedelta(hours=48)
        if order_status in {"partial_refunded", "refunded"}:
            return timedelta(days=4)
        if order_status in {"paid", "completed"}:
            return timedelta(hours=3)
        return timedelta(0)

    def build_order_contexts(self) -> list[dict[str, Any]]:
        candidates = self.fetch_order_candidates()
        coupons_by_user = self.fetch_available_coupons_by_user()
        order_count = min(int(GENERATION_DEFAULTS["orders"]), len(candidates))
        contexts: list[dict[str, Any]] = []
        successful_pairs: set[tuple[int, int]] = set()
        candidate_index = 0

        while len(contexts) < order_count and candidate_index < len(candidates) * 3:
            candidate = candidates[candidate_index % len(candidates)]
            candidate_index += 1
            order_status = self.pick_order_status(len(contexts))
            pair = (candidate["student_id"], candidate["cohort_id"])
            if self.is_successful_order(order_status) and pair in successful_pairs:
                continue
            if self.is_successful_order(order_status):
                successful_pairs.add(pair)

            coupon = self.pick_coupon_for_order(candidate, coupons_by_user, order_status)
            context = self.build_order_context(candidate, coupon, order_status, len(contexts) + 1)
            contexts.append(context)

        if len(contexts) < order_count:
            raise ValueError("not enough unique order candidates for Layer4")
        return contexts

    def build_order_context(
        self,
        candidate: dict[str, Any],
        coupon: dict[str, Any] | None,
        order_status: str,
        sequence: int,
    ) -> dict[str, Any]:
        base_floor = max(
            candidate["user_created_at"],
            candidate["cohort_created_at"],
            candidate["source_at"],
        )
        status_buffer = self.order_time_buffer(order_status)
        delay_days = ORDER_SOURCE_DELAY_DAYS.get(candidate["source_type"], 14)
        created_ceiling = min(
            self.now - status_buffer,
            candidate["source_at"] + timedelta(days=delay_days),
        )
        min_delay_floor = candidate["source_at"] + timedelta(
            minutes=self.random.randint(5, 180)
        )
        created_floor = (
            max(base_floor, min_delay_floor)
            if created_ceiling >= min_delay_floor
            else base_floor
        )
        if created_ceiling < created_floor:
            created_ceiling = created_floor
        created_at = self.random_datetime(created_floor, created_ceiling)
        total_amount = self.money(candidate["unit_price"])
        discount_amount = self.calculate_discount(total_amount, coupon)
        payable_amount = self.money(total_amount - discount_amount)
        if payable_amount < 0:
            payable_amount = Decimal("0.00")

        paid_at = None
        cancel_at = None
        paid_amount = None
        refund_amount = None
        if order_status == "cancelled":
            cancel_at = self.cap_at_now(
                created_at + timedelta(hours=self.random.randint(1, 48))
            )
        elif order_status in {"paid", "completed", "partial_refunded", "refunded"}:
            paid_at = self.cap_at_now(
                created_at + timedelta(minutes=self.random.randint(5, 180))
            )
            paid_amount = payable_amount
            if order_status == "partial_refunded":
                refund_amount = self.money(payable_amount * Decimal("0.40"))
            elif order_status == "refunded":
                refund_amount = payable_amount

        updated_at = max(
            value
            for value in (
                created_at,
                paid_at,
                cancel_at,
                self.now if order_status == "completed" else None,
            )
            if value is not None
        )
        if refund_amount is not None:
            if paid_at is None:
                raise ValueError("refund order must have paid_at")
            updated_at = max(
                updated_at,
                self.cap_at_now(paid_at + timedelta(days=3)),
            )

        order_no = f"ORD{sequence:010d}"
        order = {
            "institution_id": candidate["institution_id"],
            "order_no": order_no,
            "user_id": candidate["user_id"],
            "student_id": candidate["student_id"],
            "coupon_receive_record_id": None if coupon is None else coupon["id"],
            "order_source_channel_id": candidate["source_channel_id"],
            "order_status": order_status,
            "total_amount": total_amount,
            "discount_amount": discount_amount,
            "payable_amount": payable_amount,
            "paid_amount": paid_amount,
            "refund_amount": refund_amount,
            "remark": None,
            "paid_at": paid_at,
            "cancel_at": cancel_at,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        order_item = {
            "institution_id": candidate["institution_id"],
            "order_id": None,
            "user_id": candidate["user_id"],
            "student_id": candidate["student_id"],
            "cohort_id": candidate["cohort_id"],
            "order_item_status": self.order_item_status(order_status),
            "item_name": candidate["cohort_name"],
            "unit_price": total_amount,
            "discount_amount": discount_amount,
            "payable_amount": payable_amount,
            "service_period_days": 365 if candidate["end_date"] is None else 120,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        payment_record = self.build_payment_record(candidate, order, sequence)
        if coupon is not None and self.is_successful_order(order_status):
            if paid_at is None:
                raise ValueError("successful coupon order must have paid_at")
            self.used_coupon_events.append((coupon["id"], paid_at))
        return {
            "sequence": sequence,
            "candidate": candidate,
            "order": order,
            "order_item": order_item,
            "payment_record": payment_record,
        }

    def build_payment_record(
        self,
        candidate: dict[str, Any],
        order: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        order_status = order["order_status"]
        payment_status = self.payment_status(order_status, sequence)
        paid_at = order["paid_at"] if payment_status in {"paid", "partial_refunded", "refunded"} else None
        refund_amount = order["refund_amount"] if payment_status in {"partial_refunded", "refunded"} else None
        refund_at = None
        if refund_amount is not None:
            if paid_at is None:
                raise ValueError("refunded payment must have paid_at")
            refund_at = self.cap_at_now(paid_at + timedelta(days=3))
        updated_at = max(value for value in (order["created_at"], paid_at, refund_at) if value is not None)
        return {
            "institution_id": candidate["institution_id"],
            "order_id": None,
            "payment_no": f"PAY{sequence:010d}",
            "payment_channel": self.random.choice(PAYMENT_CHANNELS),
            "payment_status": payment_status,
            "amount": order["payable_amount"],
            "third_party_trade_no": (
                f"TP{sequence:014d}" if payment_status in {"paid", "partial_refunded", "refunded"} else None
            ),
            "refund_amount": refund_amount,
            "paid_at": paid_at,
            "refund_at": refund_at,
            "created_at": order["created_at"],
            "updated_at": updated_at,
        }

    def build_refund_requests(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        approvers = self.fetch_approvers_by_institution()
        for context in contexts:
            order = context["order"]
            if order["order_status"] not in {"partial_refunded", "refunded"}:
                continue
            rows.append(
                self.build_refund_row(
                    context,
                    "refunded",
                    order["refund_amount"],
                    len(rows) + 1,
                    approvers,
                )
            )

        extra_limit = int(
            len(contexts) * float(GENERATION_DEFAULTS["extra_refund_request_ratio"])
        )
        extra_candidates = [
            context
            for context in contexts
            if context["order"]["order_status"] in {"paid", "completed"}
        ]
        for context in extra_candidates[:extra_limit]:
            status = self.random.choice(("pending", "approved", "rejected"))
            apply_amount = self.money(context["order_item"]["payable_amount"] * Decimal("0.50"))
            approved_amount = None
            if status == "approved":
                approved_amount = apply_amount
            elif status == "rejected":
                approved_amount = Decimal("0.00")
            rows.append(
                self.build_refund_row(
                    context,
                    status,
                    approved_amount,
                    len(rows) + 1,
                    approvers,
                    apply_amount=apply_amount,
                )
            )
        return rows

    def build_refund_row(
        self,
        context: dict[str, Any],
        refund_status: str,
        approved_amount: Decimal | None,
        sequence: int,
        approvers: dict[int, list[dict[str, Any]]],
        apply_amount: Decimal | None = None,
    ) -> dict[str, Any]:
        order = context["order"]
        order_item = context["order_item"]
        candidate = context["candidate"]
        apply_amount = apply_amount or approved_amount or order_item["payable_amount"]
        if order["paid_at"] is None:
            raise ValueError("refund request must belong to a paid order")
        created_at = self.cap_at_now(
            order["paid_at"] + timedelta(days=self.random.randint(1, 5))
        )
        applied_at = created_at
        approved_at = None
        refunded_at = None
        approver_user_id = None
        if refund_status in {"approved", "rejected", "refunded"}:
            approved_at = self.cap_at_now(
                applied_at + timedelta(hours=self.random.randint(2, 48))
            )
            approver = approvers[candidate["institution_id"]][
                sequence % len(approvers[candidate["institution_id"]])
            ]
            approver_user_id = approver["user_id"]
        if refund_status == "refunded":
            if approved_at is None:
                raise ValueError("refunded request must have approved_at")
            refunded_at = self.cap_at_now(
                approved_at + timedelta(hours=self.random.randint(2, 48))
            )
        updated_at = max(
            value
            for value in (created_at, applied_at, approved_at, refunded_at)
            if value is not None
        )
        return {
            "institution_id": candidate["institution_id"],
            "refund_no": f"RF{sequence:010d}",
            "order_id": context["order_id"],
            "order_item_id": context["order_item_id"],
            "payment_id": context["payment_id"],
            "user_id": candidate["user_id"],
            "student_id": candidate["student_id"],
            "refund_type": self.random.choice(REFUND_TYPES),
            "refund_reason": self.random.choice(REFUND_REASONS),
            "refund_status": refund_status,
            "apply_amount": apply_amount,
            "approved_amount": approved_amount,
            "approver_user_id": approver_user_id,
            "remark": None,
            "yn": 1,
            "applied_at": applied_at,
            "approved_at": approved_at,
            "refunded_at": refunded_at,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def build_student_cohort_rels(
        self, contexts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for context in contexts:
            order = context["order"]
            if not self.is_successful_order(order["order_status"]):
                continue
            status = self.enroll_status(order["order_status"])
            enroll_at = order["paid_at"]
            completed_at = None
            cancelled_at = None
            if status == "completed":
                completed_at = min(
                    self.now,
                    max(enroll_at + timedelta(days=30), order["updated_at"]),
                )
            elif status == "refunded":
                cancelled_at = self.cap_at_now(order["paid_at"] + timedelta(days=3))
            updated_at = max(
                value
                for value in (enroll_at, completed_at, cancelled_at)
                if value is not None
            )
            candidate = context["candidate"]
            rows.append(
                {
                    "institution_id": candidate["institution_id"],
                    "user_id": candidate["user_id"],
                    "student_id": candidate["student_id"],
                    "cohort_id": candidate["cohort_id"],
                    "order_item_id": context["order_item_id"],
                    "enroll_status": status,
                    "enroll_at": enroll_at,
                    "completed_at": completed_at,
                    "cancelled_at": cancelled_at,
                    "created_at": enroll_at,
                    "updated_at": updated_at,
                }
            )
        return rows

    def attach_order_ids(self, contexts: list[dict[str, Any]]) -> None:
        ids = self.fetch_ids_by_code("order", "order_no")
        for context in contexts:
            order_id = ids[context["order"]["order_no"]]
            context["order_id"] = order_id
            context["order_item"]["order_id"] = order_id
            context["payment_record"]["order_id"] = order_id

    def attach_order_item_ids(self, contexts: list[dict[str, Any]]) -> None:
        rows = db.fetch_all("SELECT id, order_id FROM order_item ORDER BY id")
        ids = {row["order_id"]: row["id"] for row in rows}
        for context in contexts:
            context["order_item_id"] = ids[context["order_id"]]

    def attach_payment_ids(self, contexts: list[dict[str, Any]]) -> None:
        ids = self.fetch_ids_by_code("payment_record", "payment_no")
        for context in contexts:
            context["payment_id"] = ids[context["payment_record"]["payment_no"]]

    def pick_order_status(self, index: int) -> str:
        bucket = index % 100
        if bucket < 8:
            return "pending"
        if bucket < 14:
            return "cancelled"
        if bucket < 55:
            return "paid"
        if bucket < 82:
            return "completed"
        if bucket < 92:
            return "partial_refunded"
        return "refunded"

    def pick_coupon_for_order(
        self,
        candidate: dict[str, Any],
        coupons_by_user: dict[int, list[dict[str, Any]]],
        order_status: str,
    ) -> dict[str, Any] | None:
        if order_status == "cancelled" or candidate["user_id"] not in coupons_by_user:
            return None
        if self.random.random() > 0.35:
            return None
        for coupon in coupons_by_user[candidate["user_id"]]:
            if coupon["id"] in self.linked_coupon_receive_ids:
                continue
            if coupon["institution_id"] is not None and coupon["institution_id"] != candidate["institution_id"]:
                continue
            self.linked_coupon_receive_ids.add(coupon["id"])
            return coupon
        return None

    def calculate_discount(
        self, total_amount: Decimal, coupon: dict[str, Any] | None
    ) -> Decimal:
        if coupon is None:
            return Decimal("0.00")
        if total_amount < coupon["threshold_amount"]:
            return Decimal("0.00")
        if coupon["coupon_type"] == "cash" and coupon["discount_amount"] is not None:
            return self.money(min(total_amount, coupon["discount_amount"]))
        if coupon["coupon_type"] == "discount" and coupon["discount_rate"] is not None:
            return self.money(total_amount * (Decimal("1.00") - coupon["discount_rate"]))
        return Decimal("0.00")

    def is_successful_order(self, order_status: str) -> bool:
        return order_status in {"paid", "completed", "partial_refunded", "refunded"}

    def order_item_status(self, order_status: str) -> str:
        if order_status == "partial_refunded":
            return "paid"
        if order_status == "refunded":
            return "refunded"
        return order_status

    def payment_status(self, order_status: str, sequence: int) -> str:
        if order_status == "pending":
            return "failed" if sequence % 3 == 0 else "pending"
        if order_status == "cancelled":
            return "failed"
        if order_status == "partial_refunded":
            return "partial_refunded"
        if order_status == "refunded":
            return "refunded"
        return "paid"

    def enroll_status(self, order_status: str) -> str:
        if order_status == "completed":
            return "completed"
        if order_status == "refunded":
            return "refunded"
        return "active"

    def apply_coupon_usage(self) -> None:
        for receive_id, used_at in self.used_coupon_events:
            db.execute(
                """
                UPDATE coupon_receive_record
                SET
                    receive_status = 'used',
                    used_at = %s,
                    updated_at = GREATEST(updated_at, %s)
                WHERE id = %s
                """,
                (used_at, used_at, receive_id),
            )

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
                c.used_count = COALESCE(r.used_count, 0)
            """
        )

    def refresh_cohort_student_counts(self) -> None:
        db.execute(
            """
            UPDATE series_cohort AS c
            LEFT JOIN (
                SELECT
                    cohort_id,
                    COUNT(*) AS current_student_count
                FROM student_cohort_rel
                WHERE enroll_status = 'active'
                GROUP BY cohort_id
            ) AS r ON r.cohort_id = c.id
            SET c.current_student_count = COALESCE(r.current_student_count, 0)
            """
        )

    def fetch_order_candidates(self) -> list[dict[str, Any]]:
        series_default_cohort_sql = """
            JOIN (
                SELECT
                    series_id,
                    MIN(id) AS cohort_id
                FROM series_cohort
                GROUP BY series_id
            ) AS dc ON dc.series_id = {series_column}
            JOIN series_cohort AS c ON c.id = dc.cohort_id
            JOIN series AS s ON s.id = {series_column}
        """
        cart_rows = db.fetch_all(
            """
            SELECT
                'cart' AS source_type,
                cart.user_id,
                sp.id AS student_id,
                cart.cohort_id,
                c.institution_id,
                c.cohort_name,
                c.end_date,
                c.created_at AS cohort_created_at,
                u.created_at AS user_created_at,
                c.sale_price AS unit_price,
                NULL AS source_channel_id,
                cart.added_at AS source_at
            FROM shopping_cart_item AS cart
            JOIN sys_user AS u ON u.id = cart.user_id
            JOIN student_profile AS sp ON sp.user_id = cart.user_id
            JOIN series_cohort AS c ON c.id = cart.cohort_id
            WHERE cart.removed_at IS NULL
              AND cart.added_at <= %s
              AND c.created_at <= %s
            ORDER BY cart.id
            """,
            (self.now, self.now),
        )
        consultation_rows = db.fetch_all(
            """
            SELECT
                'consultation' AS source_type,
                consult.user_id,
                sp.id AS student_id,
                consult.cohort_id,
                c.institution_id,
                c.cohort_name,
                c.end_date,
                c.created_at AS cohort_created_at,
                u.created_at AS user_created_at,
                c.sale_price AS unit_price,
                consult.source_channel_id,
                consult.consulted_at AS source_at
            FROM consultation_record AS consult
            JOIN sys_user AS u ON u.id = consult.user_id
            JOIN student_profile AS sp ON sp.user_id = consult.user_id
            JOIN series_cohort AS c ON c.id = consult.cohort_id
            WHERE consult.consulted_at <= %s
              AND c.created_at <= %s
            ORDER BY consult.id
            """,
            (self.now, self.now),
        )
        favorite_rows = db.fetch_all(
            f"""
            SELECT
                'favorite' AS source_type,
                fav.user_id,
                sp.id AS student_id,
                c.id AS cohort_id,
                c.institution_id,
                c.cohort_name,
                c.end_date,
                c.created_at AS cohort_created_at,
                u.created_at AS user_created_at,
                c.sale_price AS unit_price,
                NULL AS source_channel_id,
                fav.created_at AS source_at
            FROM series_favorite AS fav
            JOIN sys_user AS u ON u.id = fav.user_id
            JOIN student_profile AS sp ON sp.user_id = fav.user_id
            {series_default_cohort_sql.format(series_column='fav.series_id')}
            WHERE fav.yn = 1
              AND fav.created_at <= %s
              AND c.created_at <= %s
            ORDER BY fav.id
            """,
            (self.now, self.now),
        )
        visit_rows = db.fetch_all(
            f"""
            SELECT
                'visit' AS source_type,
                visit.user_id,
                sp.id AS student_id,
                c.id AS cohort_id,
                c.institution_id,
                c.cohort_name,
                c.end_date,
                c.created_at AS cohort_created_at,
                u.created_at AS user_created_at,
                c.sale_price AS unit_price,
                NULL AS source_channel_id,
                visit.enter_at AS source_at
            FROM series_visit_log AS visit
            JOIN sys_user AS u ON u.id = visit.user_id
            JOIN student_profile AS sp ON sp.user_id = visit.user_id
            {series_default_cohort_sql.format(series_column='visit.series_id')}
            WHERE visit.enter_at <= %s
              AND c.created_at <= %s
            ORDER BY visit.id
            """,
            (self.now, self.now),
        )
        search_rows = db.fetch_all(
            f"""
            SELECT
                'search' AS source_type,
                search.user_id,
                sp.id AS student_id,
                c.id AS cohort_id,
                c.institution_id,
                c.cohort_name,
                c.end_date,
                c.created_at AS cohort_created_at,
                u.created_at AS user_created_at,
                c.sale_price AS unit_price,
                NULL AS source_channel_id,
                search.searched_at AS source_at
            FROM series_search_log AS search
            JOIN sys_user AS u ON u.id = search.user_id
            JOIN student_profile AS sp ON sp.user_id = search.user_id
            {series_default_cohort_sql.format(series_column='search.clicked_series_id')}
            WHERE search.clicked_series_id IS NOT NULL
              AND search.searched_at <= %s
              AND c.created_at <= %s
            ORDER BY search.id
            """,
            (self.now, self.now),
        )
        rows = (
            cart_rows
            + consultation_rows
            + favorite_rows
            + visit_rows
            + search_rows
        )
        self.random.shuffle(rows)
        return rows

    def fetch_available_coupons_by_user(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT
                r.*,
                c.institution_id,
                c.coupon_type,
                c.discount_amount,
                c.discount_rate,
                c.threshold_amount
            FROM coupon_receive_record AS r
            JOIN coupon AS c ON c.id = r.coupon_id
            WHERE r.receive_status = 'unused'
              AND r.used_at IS NULL
            ORDER BY r.user_id, r.id
            """
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["user_id"], []).append(row)
        return result

    def fetch_approvers_by_institution(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT s.*
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE r.role_category IN ('management', 'academic')
            ORDER BY s.institution_id, s.id
            """
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_ids_by_code(self, table_name: str, code_column: str) -> dict[str, int]:
        rows = db.fetch_all(f"SELECT id, `{code_column}` AS code FROM `{table_name}`")
        return {str(row["code"]): int(row["id"]) for row in rows}
