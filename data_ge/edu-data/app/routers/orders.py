"""Order APIs."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import conflict, not_found
from ..response import ok
from ..utils import count_total, format_datetime, local_now, make_no, money, offset_limit

router = APIRouter(prefix="/api/v1", tags=["orders"])


class OrderQuoteRequest(BaseModel):
    cohortId: int = Field(description="班次 ID。")
    couponReceiveRecordId: int | None = Field(default=None, description="领券记录 ID。")


class OrderCreateRequest(BaseModel):
    studentId: int = Field(description="学员档案 ID。")
    cohortId: int = Field(description="班次 ID。")
    couponReceiveRecordId: int | None = Field(default=None, description="领券记录 ID。")
    orderSourceChannelId: int | None = Field(default=None, description="订单来源渠道 ID。")
    remark: str | None = Field(default=None, description="下单备注。")


class OrderCancelRequest(BaseModel):
    reason: str = Field(description="取消原因。")


def ensure_student_owned(student_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM student_profile WHERE id = %s AND user_id = %s AND yn = 1",
        (student_id, current_user_id),
    )
    if row is None:
        raise not_found("STUDENT_PROFILE_NOT_FOUND", "学员档案不存在")
    return row


def ensure_cohort(cohort_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT cohort.*, series.delivery_mode
        FROM series_cohort AS cohort
        JOIN series ON series.id = cohort.series_id
        WHERE cohort.id = %s AND cohort.yn = 1
        """,
        (cohort_id,),
    )
    if row is None:
        raise not_found("COHORT_NOT_FOUND", "班次不存在")
    return row


def ensure_channel(channel_id: int) -> None:
    if fetch_one("SELECT id FROM dim_channel WHERE id = %s AND yn = 1", (channel_id,)) is None:
        raise not_found("CHANNEL_NOT_FOUND", "订单来源渠道不存在")


def ensure_order_owned(order_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM `order` WHERE id = %s AND user_id = %s",
        (order_id, current_user_id),
    )
    if row is None:
        raise not_found("ORDER_NOT_FOUND", "订单不存在")
    return row


def coupon_applicable_to_cohort(coupon_id: int, cohort_id: int) -> bool:
    row = fetch_one(
        """
        SELECT
            (
                NOT EXISTS (
                    SELECT 1
                    FROM coupon_series_rel AS csr
                    WHERE csr.coupon_id = %s
                )
                OR EXISTS (
                    SELECT 1
                    FROM coupon_series_rel AS csr
                    JOIN series_cohort AS cohort ON cohort.series_id = csr.series_id
                    WHERE csr.coupon_id = %s
                      AND cohort.id = %s
                )
            ) AS series_applicable,
            (
                NOT EXISTS (
                    SELECT 1
                    FROM coupon_category_rel AS ccr
                    WHERE ccr.coupon_id = %s
                )
                OR EXISTS (
                    SELECT 1
                    FROM coupon_category_rel AS ccr
                    JOIN series_cohort AS cohort ON cohort.id = %s
                    JOIN series_category_rel AS scr ON scr.series_id = cohort.series_id
                    WHERE ccr.coupon_id = %s
                      AND ccr.category_id = scr.category_id
                )
            ) AS category_applicable
        """,
        (coupon_id, coupon_id, cohort_id, coupon_id, cohort_id, coupon_id),
    )
    return bool(row and row["series_applicable"] and row["category_applicable"])


def validate_order_source_channel(
    current_user_id: int, cohort_id: int, order_source_channel_id: int | None
) -> None:
    if order_source_channel_id is None:
        return
    has_consultation = fetch_one(
        """
        SELECT id
        FROM consultation_record
        WHERE user_id = %s AND cohort_id = %s
        LIMIT 1
        """,
        (current_user_id, cohort_id),
    )
    if has_consultation is None:
        return
    matched_consultation = fetch_one(
        """
        SELECT id
        FROM consultation_record
        WHERE user_id = %s
          AND cohort_id = %s
          AND source_channel_id = %s
        LIMIT 1
        """,
        (current_user_id, cohort_id, order_source_channel_id),
    )
    if matched_consultation is None:
        raise conflict(
            "ORDER_SOURCE_CHANNEL_MISMATCH",
            "订单来源渠道与当前用户该班次的咨询来源渠道不一致",
        )


def coupon_discount(
    receive_id: int | None, current_user_id: int, total: Decimal, cohort_id: int
) -> Decimal:
    if receive_id is None:
        return Decimal("0.00")
    record = fetch_one(
        """
        SELECT coupon.*, record.coupon_id
        FROM coupon_receive_record AS record
        JOIN coupon ON coupon.id = record.coupon_id
        WHERE record.id = %s
          AND record.user_id = %s
          AND record.receive_status = 'unused'
          AND record.expired_at >= %s
        """,
        (receive_id, current_user_id, local_now()),
    )
    if record is None:
        raise conflict("COUPON_UNAVAILABLE", "优惠券不可用")
    if not coupon_applicable_to_cohort(int(record["coupon_id"]), cohort_id):
        raise conflict("COUPON_NOT_APPLICABLE", "优惠券不适用于当前班次")
    if total < Decimal(str(record["threshold_amount"] or 0)):
        raise conflict("COUPON_THRESHOLD_NOT_MET", "订单金额未达到优惠券门槛")
    if record["coupon_type"] == "discount":
        rate = Decimal(str(record["discount_rate"] or 1))
        return (total * (Decimal("1") - rate)).quantize(Decimal("0.01"))
    return min(total, Decimal(str(record["discount_amount"] or 0)))


def available_coupon_receives(
    current_user_id: int, total: Decimal, cohort_id: int
) -> list[dict[str, object]]:
    rows = fetch_all(
        """
        SELECT
            record.id,
            record.coupon_id,
            coupon.coupon_name,
            coupon.coupon_type,
            coupon.threshold_amount,
            coupon.discount_amount,
            coupon.discount_rate,
            record.expired_at
        FROM coupon_receive_record AS record
        JOIN coupon ON coupon.id = record.coupon_id
        WHERE record.user_id = %s
          AND record.receive_status = 'unused'
          AND record.expired_at >= %s
        ORDER BY record.received_at DESC, record.id DESC
        """,
        (current_user_id, local_now()),
    )
    available: list[dict[str, object]] = []
    for row in rows:
        if not coupon_applicable_to_cohort(int(row["coupon_id"]), cohort_id):
            continue
        threshold = Decimal(str(row["threshold_amount"] or 0))
        if total < threshold:
            continue
        if row["coupon_type"] == "discount":
            discount_amount = (
                total * (Decimal("1") - Decimal(str(row["discount_rate"] or 1)))
            ).quantize(Decimal("0.01"))
        else:
            discount_amount = min(total, Decimal(str(row["discount_amount"] or 0)))
        available.append(
            {
                "couponReceiveRecordId": row["id"],
                "couponName": row["coupon_name"],
                "couponType": row["coupon_type"],
                "discountAmount": money(discount_amount),
                "expiredAt": format_datetime(row["expired_at"]),
            }
        )
    return available


def order_list_payload(row: dict[str, Any]) -> dict[str, object]:
    return {
        "orderId": row["id"],
        "orderNo": row["order_no"],
        "orderStatusCode": row["order_status"],
        "payableAmount": money(row["payable_amount"]),
        "paidAmount": money(row["paid_amount"]),
        "createdAt": format_datetime(row["created_at"]),
    }


@router.post("/orders/quote")
def quote_order(
    body: Annotated[OrderQuoteRequest, Body(description="订单试算请求体。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    cohort = ensure_cohort(body.cohortId)
    total = Decimal(str(cohort["sale_price"]))
    discount = coupon_discount(body.couponReceiveRecordId, current_user_id, total, body.cohortId)
    return ok(
        {
            "cohortId": body.cohortId,
            "totalAmount": money(total),
            "discountAmount": money(discount),
            "payableAmount": money(total - discount),
            "availableCoupons": available_coupon_receives(current_user_id, total, body.cohortId),
        }
    )


@router.post("/orders")
def create_order(
    body: Annotated[OrderCreateRequest, Body(description="创建订单请求体。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    student = ensure_student_owned(body.studentId, current_user_id)
    cohort = ensure_cohort(body.cohortId)
    if body.orderSourceChannelId is not None:
        ensure_channel(body.orderSourceChannelId)
    validate_order_source_channel(current_user_id, body.cohortId, body.orderSourceChannelId)
    total_amount = Decimal(str(cohort["sale_price"]))
    discount_amount = coupon_discount(
        body.couponReceiveRecordId, current_user_id, total_amount, body.cohortId
    )
    payable_amount = total_amount - discount_amount
    now = local_now()
    order_no = make_no("ORD")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO `order` (
                institution_id, order_no, user_id, student_id,
                coupon_receive_record_id, order_source_channel_id, order_status,
                total_amount, discount_amount, payable_amount, paid_amount,
                refund_amount, remark, paid_at, cancel_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, NULL, NULL,
                %s, NULL, NULL, %s, %s)
            """,
            (
                cohort["institution_id"],
                order_no,
                current_user_id,
                student["id"],
                body.couponReceiveRecordId,
                body.orderSourceChannelId,
                total_amount,
                discount_amount,
                payable_amount,
                body.remark,
                now,
                now,
            ),
        )
        order_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO order_item (
                institution_id, order_id, user_id, student_id, cohort_id,
                order_item_status, item_name, unit_price, discount_amount,
                payable_amount, service_period_days, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, 90, %s, %s)
            """,
            (
                cohort["institution_id"],
                order_id,
                current_user_id,
                student["id"],
                body.cohortId,
                cohort["cohort_name"],
                total_amount,
                discount_amount,
                payable_amount,
                now,
                now,
            ),
        )
    return ok(
        {
            "orderId": order_id,
            "orderNo": order_no,
            "orderStatusCode": "pending",
            "payableAmount": money(payable_amount),
        }
    )


@router.get("/orders")
def list_orders(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="订单状态。可选值：pending、paid、completed、cancelled、partial_refunded、refunded。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("order_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM `order`
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT *
        FROM `order`
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [order_list_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/orders/{order_id}")
def get_order_detail(
    order_id: Annotated[int, Path(description="订单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    order = ensure_order_owned(order_id, current_user_id)
    payment = fetch_one(
        """
        SELECT payment_status, paid_at
        FROM payment_record
        WHERE order_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (order_id,),
    )
    refund = fetch_one(
        """
        SELECT
            COUNT(*) AS refund_request_count,
            COALESCE(SUM(CASE
                WHEN refund_status IN ('approved', 'refunded') THEN approved_amount
                ELSE 0
            END), 0) AS refund_amount
        FROM refund_request
        WHERE order_id = %s
        """,
        (order_id,),
    )
    return ok(
        {
            "orderId": order["id"],
            "orderNo": order["order_no"],
            "orderStatusCode": order["order_status"],
            "totalAmount": money(order["total_amount"]),
            "discountAmount": money(order["discount_amount"]),
            "payableAmount": money(order["payable_amount"]),
            "paidAmount": money(order["paid_amount"]),
            "paymentSummary": {
                "paymentStatusCode": payment["payment_status"] if payment else None,
                "paidAt": format_datetime(payment["paid_at"]) if payment else None,
            },
            "refundSummary": {
                "refundRequestCount": int(refund["refund_request_count"] or 0)
                if refund
                else 0,
                "refundAmount": money(refund["refund_amount"] if refund else None) or 0,
            },
        }
    )


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    body: Annotated[OrderCancelRequest, Body(description="取消订单请求体。")],
    order_id: Annotated[int, Path(description="订单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    order = ensure_order_owned(order_id, current_user_id)
    if order["order_status"] != "pending":
        raise conflict("ORDER_NOT_CANCELABLE", "只允许取消未支付订单")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE `order`
            SET order_status = 'cancelled', cancel_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (now, now, order_id),
        )
        cursor.execute(
            """
            UPDATE order_item
            SET order_item_status = 'cancelled', updated_at = %s
            WHERE order_id = %s
            """,
            (now, order_id),
        )
        cursor.execute(
            """
            UPDATE payment_record
            SET payment_status = 'closed', updated_at = %s
            WHERE order_id = %s AND payment_status = 'pending'
            """,
            (now, order_id),
        )
    return ok({"orderId": order_id, "orderStatusCode": "cancelled"})
