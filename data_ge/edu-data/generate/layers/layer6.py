"""Layer6: business-derived settlement, risk, and moderation data."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from ..insert_support import insert_dict_rows
from .base import BaseGenerator
from .validations import validate_layer6

TEACHER_UNIT_PRICE = {
    "online_live": Decimal("180.00"),
    "online_recorded": Decimal("90.00"),
    "offline_face_to_face": Decimal("220.00"),
}
COMMISSION_RATE_BY_CATEGORY = {
    "acquisition": Decimal("0.12"),
    "referral": Decimal("0.08"),
    "offline": Decimal("0.10"),
    "cooperation": Decimal("0.15"),
}
RISK_LEVELS = ("low", "medium", "high", "critical")
RISK_SOURCES = ("rule_engine", "manual_report", "model_detection", "scheduled_job")
RISK_ALERT_STATUSES = ("pending", "in_progress", "closed")
DISPOSAL_ACTIONS = (
    "review",
    "contact_user",
    "freeze_account",
    "mark_false_positive",
    "close_alert",
)
DISPOSAL_RESULTS = (
    "pending_follow_up",
    "confirmed_risk",
    "false_positive",
    "resolved",
)


class Layer6Generator(BaseGenerator):
    layer = 6
    layer_name = "经营衍生结果"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]) + 6)
        self.now = self.local_now()
        self.today = self.now.date()

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        teacher_result = self.generate_teacher_compensation()
        counts["teacher_compensation_bill"] = teacher_result["bill_count"]
        counts["teacher_compensation_item"] = teacher_result["item_count"]

        commission_result = self.generate_channel_commission()
        counts["channel_commission_bill"] = commission_result["bill_count"]
        counts["channel_commission_item"] = commission_result["item_count"]

        counts["ugc_moderation_task"] = self.generate_ugc_moderation_tasks()

        risk_result = self.generate_risk_alerts()
        counts["risk_alert_event"] = risk_result["alert_count"]
        counts["risk_disposal_record"] = risk_result["disposal_count"]

        self.log_table_counts(counts)
        for check in validate_layer6():
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

    def money(self, value: Decimal | int | float | str) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def generate_teacher_compensation(self) -> dict[str, int]:
        sessions = self.fetch_teacher_payable_sessions()
        approvers = self.fetch_staff_users_by_institution(("academic", "management"))
        grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
        for session in sessions:
            settle_period = session["teaching_date"].strftime("%Y-%m")
            grouped[(session["institution_id"], session["teacher_id"], settle_period)].append(
                session
            )

        bill_rows: list[dict[str, Any]] = []
        item_rows: list[dict[str, Any]] = []
        sequence = 1
        bill_id = 1
        for (institution_id, teacher_id, settle_period), group_rows in grouped.items():
            group_rows.sort(key=lambda row: (row["teaching_date"], row["session_id"]))
            period_end = datetime.combine(
                max(row["teaching_date"] for row in group_rows),
                time(hour=23, minute=59, second=59),
            )
            created_floor = max(row["teacher_created_at"] for row in group_rows)
            created_floor = max(
                created_floor,
                max(row["session_created_at"] for row in group_rows),
            )
            created_floor = max(created_floor, period_end + timedelta(days=1))
            created_at = self.random_datetime(created_floor, self.now)

            lesson_count = len(group_rows)
            base_amount = Decimal("0.00")
            bonus_amount = Decimal("0.00")
            deduction_amount = Decimal("0.00")
            current_items: list[dict[str, Any]] = []

            for row in group_rows:
                unit_price = TEACHER_UNIT_PRICE[row["delivery_mode"]]
                item_amount = self.money(unit_price)
                base_amount += item_amount
                current_items.append(
                    {
                        "id": len(item_rows) + len(current_items) + 1,
                        "institution_id": institution_id,
                        "bill_id": bill_id,
                        "teacher_id": teacher_id,
                        "cohort_id": row["cohort_id"],
                        "session_id": row["session_id"],
                        "item_type": "session_fee",
                        "unit_price": unit_price,
                        "item_amount": item_amount,
                        "remark": None,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )

            if lesson_count >= 8 and self.random.random() < 0.35:
                bonus_amount = self.money(self.random.choice((80, 120, 160, 200)))
                current_items.append(
                    {
                        "id": len(item_rows) + len(current_items) + 1,
                        "institution_id": institution_id,
                        "bill_id": bill_id,
                        "teacher_id": teacher_id,
                        "cohort_id": None,
                        "session_id": None,
                        "item_type": "bonus",
                        "unit_price": None,
                        "item_amount": bonus_amount,
                        "remark": "阶段授课质量奖励",
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
            if self.random.random() < 0.18:
                deduction_amount = self.money(self.random.choice((30, 50, 80)))
                current_items.append(
                    {
                        "id": len(item_rows) + len(current_items) + 1,
                        "institution_id": institution_id,
                        "bill_id": bill_id,
                        "teacher_id": teacher_id,
                        "cohort_id": None,
                        "session_id": None,
                        "item_type": "deduction",
                        "unit_price": None,
                        "item_amount": -deduction_amount,
                        "remark": "结算扣减项",
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )

            payable_amount = self.money(base_amount + bonus_amount - deduction_amount)
            status, approver_user_id, settled_at, paid_at, updated_at = (
                self.bill_status_timing(
                    created_at,
                    approvers.get(institution_id, []),
                )
            )
            bill_rows.append(
                {
                    "id": bill_id,
                    "institution_id": institution_id,
                    "bill_no": f"TCB{institution_id:03d}{sequence:07d}",
                    "teacher_id": teacher_id,
                    "settle_period": settle_period,
                    "bill_status": status,
                    "lesson_count": lesson_count,
                    "base_amount": self.money(base_amount),
                    "bonus_amount": self.money(bonus_amount),
                    "deduction_amount": self.money(deduction_amount),
                    "payable_amount": payable_amount,
                    "approver_user_id": approver_user_id,
                    "yn": 1,
                    "settled_at": settled_at,
                    "paid_at": paid_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
            item_rows.extend(current_items)
            sequence += 1
            bill_id += 1

        bill_count = self.insert_rows("teacher_compensation_bill", self.strip_ids(bill_rows))
        item_count = self.insert_rows("teacher_compensation_item", self.strip_ids(item_rows))
        return {"bill_count": bill_count, "item_count": item_count}

    def generate_channel_commission(self) -> dict[str, int]:
        rows = self.fetch_commissionable_order_items()
        approvers = self.fetch_staff_users_by_institution(("sales", "management", "academic"))
        grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            settle_anchor = row["paid_at"] or row["created_at"]
            settle_period = settle_anchor.strftime("%Y-%m")
            grouped[(row["institution_id"], row["channel_id"], settle_period)].append(row)

        bill_rows: list[dict[str, Any]] = []
        item_rows: list[dict[str, Any]] = []
        sequence = 1
        bill_id = 1
        for (institution_id, channel_id, settle_period), group_rows in grouped.items():
            group_rows.sort(key=lambda row: row["order_item_id"])
            created_floor = max(row["created_at"] for row in group_rows)
            if created_floor > self.now:
                continue
            created_at = self.random_datetime(created_floor, self.now)
            commission_total = Decimal("0.00")
            for row in group_rows:
                rate = COMMISSION_RATE_BY_CATEGORY.get(
                    row["channel_category_code"], Decimal("0.10")
                )
                base_amount = self.money(row["payable_amount"])
                commission_amount = self.money(base_amount * rate)
                commission_total += commission_amount
                item_rows.append(
                    {
                        "id": len(item_rows) + 1,
                        "institution_id": institution_id,
                        "bill_id": bill_id,
                        "order_item_id": row["order_item_id"],
                        "commission_rate": rate,
                        "base_amount": base_amount,
                        "commission_amount": commission_amount,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
            status, approver_user_id, settled_at, paid_at, updated_at = (
                self.bill_status_timing(created_at, approvers.get(institution_id, []))
            )
            bill_rows.append(
                {
                    "id": bill_id,
                    "institution_id": institution_id,
                    "bill_no": f"CCB{institution_id:03d}{sequence:07d}",
                    "channel_id": channel_id,
                    "settle_period": settle_period,
                    "bill_status": status,
                    "order_count": len(group_rows),
                    "commission_amount": self.money(commission_total),
                    "approver_user_id": approver_user_id,
                    "yn": 1,
                    "settled_at": settled_at,
                    "paid_at": paid_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
            bill_id += 1
            sequence += 1

        bill_count = self.insert_rows("channel_commission_bill", self.strip_ids(bill_rows))
        item_count = self.insert_rows("channel_commission_item", self.strip_ids(item_rows))
        return {"bill_count": bill_count, "item_count": item_count}

    def generate_ugc_moderation_tasks(self) -> int:
        target = int(GENERATION_DEFAULTS["ugc_moderation_target"])
        moderators = self.fetch_staff_users_by_institution(("service", "academic", "management"))
        candidates = self.fetch_ugc_candidates()
        self.random.shuffle(candidates)
        rows: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates[:target], start=1):
            submitted_at = self.random_datetime(candidate["created_at"], self.now)
            status = self.random.choices(
                ("pending", "approved", "rejected"), weights=(18, 64, 18), k=1
            )[0]
            moderator_pool = moderators.get(candidate["institution_id"], [])
            moderator_user_id = None
            moderated_at = None
            reject_reason = None
            if status != "pending" and not moderator_pool:
                status = "pending"
            if status != "pending" and moderator_pool:
                moderator_user_id = moderator_pool[index % len(moderator_pool)]["user_id"]
                moderated_at = self.random_datetime(submitted_at, self.now)
                if status == "rejected":
                    reject_reason = "存在疑似敏感或不当内容，需要驳回处理。"
            updated_at = moderated_at or submitted_at
            rows.append(
                {
                    "institution_id": candidate["institution_id"],
                    "task_no": f"MOD{candidate['institution_id']:03d}{index:09d}",
                    "content_type": candidate["content_type"],
                    "topic_id": candidate["topic_id"],
                    "post_id": candidate["post_id"],
                    "review_id": candidate["review_id"],
                    "submit_user_id": candidate["submit_user_id"],
                    "moderator_user_id": moderator_user_id,
                    "moderation_status": status,
                    "risk_level": self.random.choices(
                        ("low", "medium", "high"),
                        weights=(50, 35, 15),
                        k=1,
                    )[0],
                    "reject_reason": reject_reason,
                    "yn": 1,
                    "submitted_at": submitted_at,
                    "moderated_at": moderated_at,
                    "created_at": submitted_at,
                    "updated_at": updated_at,
                }
            )
        return self.insert_rows("ugc_moderation_task", rows)

    def generate_risk_alerts(self) -> dict[str, int]:
        target = int(GENERATION_DEFAULTS["risk_alert_target"])
        handlers = self.fetch_staff_users_by_institution(("service", "academic", "management"))
        alert_rows = self.build_risk_alert_candidates(target)
        alert_count = self.insert_rows("risk_alert_event", self.strip_ids(alert_rows))
        inserted_alerts = db.fetch_all(
            "SELECT id, institution_id, alert_no, alert_status, detected_at, closed_at, created_at FROM risk_alert_event ORDER BY id"
        )
        alert_by_key = {
            (row["institution_id"], row["alert_no"]): row for row in inserted_alerts
        }

        disposal_rows: list[dict[str, Any]] = []
        for alert_index, alert in enumerate(alert_rows, start=1):
            persisted = alert_by_key[(alert["institution_id"], alert["alert_no"])]
            if alert["alert_status"] == "pending":
                continue
            institution_handlers = handlers.get(alert["institution_id"], [])
            if not institution_handlers:
                continue
            record_count = 1 if alert["alert_status"] == "in_progress" else self.random.randint(1, 3)
            last_handled_at = persisted["detected_at"]
            for index in range(record_count):
                handler = institution_handlers[(alert_index + index) % len(institution_handlers)]
                handled_upper = persisted["closed_at"] or self.now
                handled_floor = max(persisted["created_at"], last_handled_at)
                handled_at = self.random_datetime(handled_floor, handled_upper)
                if alert["alert_status"] == "closed" and index == record_count - 1:
                    final_result = self.random.choice(("resolved", "false_positive", "confirmed_risk"))
                    action_result = final_result
                    action_type = (
                        "mark_false_positive"
                        if final_result == "false_positive"
                        else "close_alert"
                    )
                    handled_at = handled_upper
                else:
                    action_type = self.random.choice(("review", "contact_user", "freeze_account"))
                    action_result = self.random.choice(("pending_follow_up", "confirmed_risk"))
                disposal_rows.append(
                    {
                        "alert_id": persisted["id"],
                        "handler_user_id": handler["user_id"],
                        "action_type": action_type,
                        "action_result": action_result,
                        "action_note": "已记录风险核查过程并同步处理意见。",
                        "handled_at": handled_at,
                        "created_at": handled_at,
                        "updated_at": handled_at,
                    }
                )
                last_handled_at = handled_at
        disposal_count = self.insert_rows("risk_disposal_record", disposal_rows)
        return {"alert_count": alert_count, "disposal_count": disposal_count}

    def build_risk_alert_candidates(self, target: int) -> list[dict[str, Any]]:
        refund_rows = self.fetch_refund_risk_candidates()
        learning_rows = self.fetch_learning_risk_candidates()
        exam_rows = self.fetch_exam_risk_candidates()
        ugc_rows = self.fetch_ugc_risk_candidates()
        operation_rows = self.fetch_operation_risk_candidates()

        pools = [
            ("refund_anomaly", refund_rows),
            ("learning_anomaly", learning_rows),
            ("exam_anomaly", exam_rows),
            ("ugc_anomaly", ugc_rows),
            ("operation_anomaly", operation_rows),
        ]
        rows: list[dict[str, Any]] = []
        sequence_by_institution: dict[int, int] = defaultdict(int)
        pool_index = 0
        while len(rows) < target and any(pool for _, pool in pools):
            alert_type, pool = pools[pool_index % len(pools)]
            pool_index += 1
            if not pool:
                continue
            source = pool.pop()
            institution_id = source["institution_id"]
            sequence_by_institution[institution_id] += 1
            created_at = max(source["created_at"], source["institution_created_at"])
            detected_at = self.random_datetime(created_at, self.now)
            status = self.random.choices(
                RISK_ALERT_STATUSES,
                weights=(18, 34, 48),
                k=1,
            )[0]
            closed_at = None
            if status == "closed":
                closed_at = self.random_datetime(detected_at, self.now)
            updated_at = closed_at or detected_at
            row = {
                "id": len(rows) + 1,
                "institution_id": institution_id,
                "alert_no": f"ALT{institution_id:03d}{sequence_by_institution[institution_id]:09d}",
                "alert_type": alert_type,
                "risk_level": source["risk_level"],
                "related_user_id": source.get("related_user_id"),
                "related_student_id": source.get("related_student_id"),
                "cohort_id": source.get("cohort_id"),
                "session_id": source.get("session_id"),
                "order_item_id": source.get("order_item_id"),
                "refund_request_id": source.get("refund_request_id"),
                "related_exam_attempt_id": source.get("related_exam_attempt_id"),
                "ugc_content_type": source.get("ugc_content_type"),
                "ugc_content_id": source.get("ugc_content_id"),
                "alert_source": self.random.choice(RISK_SOURCES),
                "alert_reason": source["alert_reason"],
                "event_payload": json.dumps(source["payload"], ensure_ascii=False),
                "alert_status": status,
                "yn": 1,
                "detected_at": detected_at,
                "closed_at": closed_at,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            rows.append(row)
        return rows

    def bill_status_timing(
        self,
        created_at: datetime,
        approvers: list[dict[str, Any]],
    ) -> tuple[str, int | None, datetime | None, datetime | None, datetime]:
        age_days = (self.now - created_at).days
        if age_days >= 45:
            status = "paid"
        elif age_days >= 12:
            status = "approved"
        else:
            status = "pending"
        if status in {"approved", "paid"} and not approvers:
            status = "pending"
        approver_user_id = None
        settled_at = None
        paid_at = None
        updated_at = created_at
        if status in {"approved", "paid"} and approvers:
            approver_user_id = approvers[0]["user_id"]
            settled_at = self.random_datetime(created_at + timedelta(hours=4), self.now)
            updated_at = settled_at
        if status == "paid" and settled_at is not None:
            paid_at = self.random_datetime(settled_at + timedelta(hours=4), self.now)
            updated_at = paid_at
        return status, approver_user_id, settled_at, paid_at, updated_at

    def strip_ids(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{key: value for key, value in row.items() if key != "id"} for row in rows]

    def fetch_staff_users_by_institution(
        self, categories: tuple[str, ...]
    ) -> dict[int, list[dict[str, Any]]]:
        placeholders = ", ".join(["%s"] * len(categories))
        rows = db.fetch_all(
            f"""
            SELECT s.*, r.role_category
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE r.role_category IN ({placeholders})
            ORDER BY s.institution_id, s.id
            """,
            categories,
        )
        result: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[row["institution_id"]].append(row)
        return result

    def fetch_teacher_payable_sessions(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                c.institution_id,
                rel.teacher_id,
                rel.created_at AS teacher_rel_created_at,
                staff.created_at AS teacher_created_at,
                session.id AS session_id,
                session.created_at AS session_created_at,
                session.teaching_date,
                c.id AS cohort_id,
                s.delivery_mode
            FROM session_teacher_rel AS rel
            JOIN staff_profile AS staff ON staff.id = rel.teacher_id
            JOIN series_cohort_session AS session ON session.id = rel.session_id
            JOIN series_cohort_course AS cc ON cc.id = session.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series AS s ON s.id = c.series_id
            WHERE session.created_at <= %s
              AND session.teaching_date <= %s
            ORDER BY c.institution_id, rel.teacher_id, session.id
            """,
            (self.now, self.today),
        )

    def fetch_commissionable_order_items(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                item.id AS order_item_id,
                item.institution_id,
                item.created_at,
                item.payable_amount,
                o.paid_at,
                o.order_source_channel_id AS channel_id,
                ch.channel_category_code
            FROM order_item AS item
            JOIN `order` AS o ON o.id = item.order_id
            JOIN dim_channel AS ch ON ch.id = o.order_source_channel_id
            WHERE o.order_source_channel_id IS NOT NULL
              AND o.order_status IN ('paid', 'completed', 'partial_refunded', 'refunded')
              AND item.created_at <= %s
            ORDER BY item.id
            """,
            (self.now,),
        )

    def fetch_ugc_candidates(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        topic_rows = db.fetch_all(
            """
            SELECT
                institution_id,
                id AS topic_id,
                NULL AS post_id,
                NULL AS review_id,
                'topic' AS content_type,
                creator_user_id AS submit_user_id,
                created_at
            FROM cohort_discussion_topic
            WHERE created_at <= %s
            ORDER BY id
            """,
            (self.now,),
        )
        post_rows = db.fetch_all(
            """
            SELECT
                institution_id,
                topic_id,
                id AS post_id,
                NULL AS review_id,
                'post' AS content_type,
                author_user_id AS submit_user_id,
                created_at
            FROM cohort_discussion_post
            WHERE created_at <= %s
            ORDER BY id
            """,
            (self.now,),
        )
        review_rows = db.fetch_all(
            """
            SELECT
                institution_id,
                NULL AS topic_id,
                NULL AS post_id,
                id AS review_id,
                'review' AS content_type,
                user_id AS submit_user_id,
                created_at
            FROM cohort_review
            WHERE created_at <= %s
            ORDER BY id
            """,
            (self.now,),
        )
        rows.extend(topic_rows)
        rows.extend(post_rows)
        rows.extend(review_rows)
        return rows

    def fetch_refund_risk_candidates(self) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                refund.id AS refund_request_id,
                refund.institution_id,
                refund.user_id AS related_user_id,
                refund.student_id AS related_student_id,
                refund.order_item_id,
                refund.created_at,
                inst.created_at AS institution_created_at,
                refund.approved_amount
            FROM refund_request AS refund
            JOIN org_institution AS inst ON inst.id = refund.institution_id
            WHERE refund.created_at <= %s
              AND refund.refund_status IN ('approved', 'refunded')
            ORDER BY refund.id
            """,
            (self.now,),
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    **row,
                    "risk_level": (
                        "critical"
                        if Decimal(str(row["approved_amount"])) >= Decimal("3000")
                        else "high"
                    ),
                    "alert_reason": "退款金额偏高或退款行为异常，需要人工核查。",
                    "payload": {"approved_amount": str(row["approved_amount"])},
                }
            )
        self.random.shuffle(results)
        return results

    def fetch_learning_risk_candidates(self) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                attendance.institution_id,
                attendance.user_id AS related_user_id,
                attendance.student_id AS related_student_id,
                attendance.cohort_id,
                attendance.session_id,
                attendance.created_at,
                inst.created_at AS institution_created_at,
                attendance.attendance_status
            FROM session_attendance AS attendance
            JOIN org_institution AS inst ON inst.id = attendance.institution_id
            WHERE attendance.created_at <= %s
              AND attendance.attendance_status IN ('absent', 'leave', 'late')
            ORDER BY attendance.id
            """,
            (self.now,),
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    **row,
                    "risk_level": "medium" if row["attendance_status"] == "late" else "high",
                    "alert_reason": "学习出勤异常，需要关注学员履约风险。",
                    "payload": {"attendance_status": row["attendance_status"]},
                }
            )
        self.random.shuffle(results)
        return results

    def fetch_exam_risk_candidates(self) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                exam_sub.institution_id,
                exam_sub.user_id AS related_user_id,
                exam_sub.student_id AS related_student_id,
                exam_sub.id AS related_exam_attempt_id,
                exam_sub.created_at,
                inst.created_at AS institution_created_at,
                exam_sub.attempt_status,
                exam_sub.score_value
            FROM session_exam_submission AS exam_sub
            JOIN org_institution AS inst ON inst.id = exam_sub.institution_id
            WHERE exam_sub.created_at <= %s
              AND exam_sub.attempt_status IN ('timeout', 'absent')
            ORDER BY exam_sub.id
            """,
            (self.now,),
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    **row,
                    "risk_level": "medium" if row["attempt_status"] == "timeout" else "high",
                    "alert_reason": "考试作答异常，需要复核是否存在考试风险。",
                    "payload": {"attempt_status": row["attempt_status"]},
                }
            )
        self.random.shuffle(results)
        return results

    def fetch_ugc_risk_candidates(self) -> list[dict[str, Any]]:
        candidates = self.fetch_ugc_candidates()
        results: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate["content_type"] == "topic":
                content_id = candidate["topic_id"]
            elif candidate["content_type"] == "post":
                content_id = candidate["post_id"]
            else:
                content_id = candidate["review_id"]
            results.append(
                {
                    "institution_id": candidate["institution_id"],
                    "related_user_id": candidate["submit_user_id"],
                    "related_student_id": None,
                    "cohort_id": None,
                    "session_id": None,
                    "order_item_id": None,
                    "refund_request_id": None,
                    "related_exam_attempt_id": None,
                    "ugc_content_type": candidate["content_type"],
                    "ugc_content_id": content_id,
                    "created_at": candidate["created_at"],
                    "institution_created_at": candidate["created_at"],
                    "risk_level": self.random.choice(("low", "medium", "high")),
                    "alert_reason": "UGC 内容存在潜在风险，进入人工复核队列。",
                    "payload": {"content_type": candidate["content_type"]},
                }
            )
        self.random.shuffle(results)
        return results

    def fetch_operation_risk_candidates(self) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                ticket.institution_id,
                ticket.user_id AS related_user_id,
                ticket.student_id AS related_student_id,
                ticket.order_item_id,
                ticket.created_at,
                inst.created_at AS institution_created_at,
                ticket.ticket_type,
                ticket.priority_level
            FROM service_ticket AS ticket
            JOIN org_institution AS inst ON inst.id = ticket.institution_id
            WHERE ticket.created_at <= %s
              AND (ticket.ticket_type = 'complaint' OR ticket.priority_level IN ('high', 'urgent'))
            ORDER BY ticket.id
            """,
            (self.now,),
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    **row,
                    "cohort_id": None,
                    "session_id": None,
                    "refund_request_id": None,
                    "related_exam_attempt_id": None,
                    "ugc_content_type": None,
                    "ugc_content_id": None,
                    "risk_level": "high" if row["priority_level"] == "urgent" else "medium",
                    "alert_reason": "异常操作或高优先级投诉，需要运营核查。",
                    "payload": {
                        "ticket_type": row["ticket_type"],
                        "priority_level": row["priority_level"],
                    },
                }
            )
        self.random.shuffle(results)
        return results
