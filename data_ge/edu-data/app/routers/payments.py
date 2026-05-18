"""Payment and refund APIs."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Path, Query
from pydantic import BaseModel, Field

from ..config import DEMO_PAYMENT_SIGNATURE
from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import bad_request, conflict, not_found, unauthorized
from ..response import ok
from ..utils import count_total, format_datetime, local_now, make_no, money, offset_limit

router = APIRouter(prefix="/api/v1", tags=["payments"])

PAYMENT_CHANNELS = {"wechat_pay", "alipay", "bank_card"}
REFUND_TYPES = {
    "personal_reason",
    "course_unsatisfied",
    "schedule_conflict",
    "duplicate_purchase",
}


class OrderPaymentCreateRequest(BaseModel):
    paymentChannelCode: str = Field(description="支付渠道编码。可选值：wechat_pay、alipay、bank_card。")


class MockPaymentNotificationRequest(BaseModel):
    paymentNo: str = Field(description="支付流水号。")
    orderId: int = Field(description="订单 ID；必须与支付流水所属订单一致。")
    paymentChannelCode: str = Field(
        description="支付渠道编码；必须与支付流水的支付渠道一致。可选值：wechat_pay、alipay、bank_card。"
    )
    amount: Decimal = Field(description="支付渠道回传金额；必须与支付流水金额一致。")
    tradeStatus: str = Field(description="交易状态。可选值：paid、failed、closed。")
    thirdPartyTradeNo: str | None = Field(default=None, description="第三方交易号。")


class PaymentCloseRequest(BaseModel):
    closeReason: str = Field(description="关闭原因；当前仅用于接口入参表达，不单独落库。")


class RefundRequestCreateRequest(BaseModel):
    refundType: str = Field(
        description=(
            "退款类型。可选值：personal_reason、course_unsatisfied、"
            "schedule_conflict、duplicate_purchase。"
        )
    )
    refundReason: str = Field(description="退款原因。")
    applyAmount: Decimal = Field(description="申请退款金额。")
    remark: str | None = Field(default=None, description="备注。")


def refund_payload(row: dict[str, Any]) -> dict[str, object]:
    return {
        "refundRequestId": row["id"],
        "refundNo": row["refund_no"],
        "refundStatusCode": row["refund_status"],
        "applyAmount": row["apply_amount"],
        "approvedAmount": row["approved_amount"],
        "appliedAt": format_datetime(row["applied_at"]),
        "approvedAt": format_datetime(row["approved_at"]),
        "refundedAt": format_datetime(row["refunded_at"]),
    }


def payment_payload(row: dict[str, Any]) -> dict[str, object]:
    return {
        "paymentId": row["id"],
        "paymentNo": row["payment_no"],
        "paymentChannelCode": row["payment_channel"],
        "paymentStatusCode": row["payment_status"],
        "amount": money(row["amount"]),
        "thirdPartyTradeNo": row["third_party_trade_no"],
        "paidAt": format_datetime(row["paid_at"]),
        "createdAt": format_datetime(row["created_at"]),
    }


def ensure_order_item_owned(order_item_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM order_item WHERE id = %s AND user_id = %s",
        (order_item_id, current_user_id),
    )
    if row is None:
        raise not_found("ORDER_ITEM_NOT_FOUND", "订单明细不存在")
    return row


def ensure_order_owned(order_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM `order` WHERE id = %s AND user_id = %s",
        (order_id, current_user_id),
    )
    if row is None:
        raise not_found("ORDER_NOT_FOUND", "订单不存在")
    return row


def ensure_payment_owned(payment_id: int, current_user_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT payment.*
        FROM payment_record AS payment
        JOIN `order` AS o ON o.id = payment.order_id
        WHERE payment.id = %s AND o.user_id = %s
        """,
        (payment_id, current_user_id),
    )
    if row is None:
        raise not_found("PAYMENT_NOT_FOUND", "支付记录不存在")
    return row


@router.post("/orders/{order_id}/payments")
def create_order_payment(
    body: Annotated[OrderPaymentCreateRequest, Body(description="创建支付单请求体。")],
    order_id: Annotated[int, Path(description="订单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if body.paymentChannelCode not in PAYMENT_CHANNELS:
        raise bad_request("INVALID_PAYMENT_CHANNEL", "支付渠道不合法")
    order = ensure_order_owned(order_id, current_user_id)
    if order["order_status"] != "pending":
        raise conflict("ORDER_NOT_CREATABLE_FOR_PAYMENT", "订单当前状态不允许创建支付单")
    payment = fetch_one(
        """
        SELECT *
        FROM payment_record
        WHERE order_id = %s AND payment_status = 'pending'
        ORDER BY id DESC
        LIMIT 1
        """,
        (order_id,),
    )
    now = local_now()
    if payment is None:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO payment_record (
                    institution_id, order_id, payment_no, payment_channel,
                    payment_status, amount, third_party_trade_no, refund_amount,
                    paid_at, refund_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, 'pending', %s, NULL, NULL,
                    NULL, NULL, %s, %s)
                """,
                (
                    order["institution_id"],
                    order_id,
                    make_no("PAY"),
                    body.paymentChannelCode,
                    order["payable_amount"],
                    now,
                    now,
                ),
            )
            payment_id = cursor.lastrowid
        payment = fetch_one("SELECT * FROM payment_record WHERE id = %s", (payment_id,))
    else:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE payment_record
                SET payment_channel = %s, updated_at = %s
                WHERE id = %s
                """,
                (body.paymentChannelCode, now, payment["id"]),
            )
        payment = fetch_one("SELECT * FROM payment_record WHERE id = %s", (payment["id"],))
    assert payment is not None
    return ok(
        {
            "paymentId": payment["id"],
            "paymentNo": payment["payment_no"],
            "paymentChannelCode": payment["payment_channel"],
            "paymentStatusCode": payment["payment_status"],
            "amount": money(payment["amount"]),
            "paymentParams": {"mockToken": f"MOCK_PAY_TOKEN_{payment['id']}"},
            "createdAt": format_datetime(payment["created_at"]),
        }
    )


@router.get("/orders/{order_id}/payments")
def list_order_payments(
    order_id: Annotated[int, Path(description="订单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    ensure_order_owned(order_id, current_user_id)
    rows = fetch_all(
        """
        SELECT *
        FROM payment_record
        WHERE order_id = %s
        ORDER BY created_at DESC, id DESC
        """,
        (order_id,),
    )
    return ok({"list": [payment_payload(row) for row in rows]})


@router.get("/payments/{payment_id}")
def get_payment_detail(
    payment_id: Annotated[int, Path(description="支付记录 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    payment = ensure_payment_owned(payment_id, current_user_id)
    return ok(
        {
            "paymentId": payment["id"],
            "paymentNo": payment["payment_no"],
            "orderId": payment["order_id"],
            "paymentChannelCode": payment["payment_channel"],
            "paymentStatusCode": payment["payment_status"],
            "amount": money(payment["amount"]),
            "thirdPartyTradeNo": payment["third_party_trade_no"],
            "refundAmount": money(payment["refund_amount"]),
            "paidAt": format_datetime(payment["paid_at"]),
            "refundAt": format_datetime(payment["refund_at"]),
            "createdAt": format_datetime(payment["created_at"]),
        }
    )


@router.post("/payments/{payment_id}/close")
def close_payment(
    body: Annotated[PaymentCloseRequest, Body(description="关闭支付单请求体。")],
    payment_id: Annotated[int, Path(description="支付记录 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if not body.closeReason.strip():
        raise bad_request("INVALID_CLOSE_REASON", "关闭原因不能为空")
    payment = ensure_payment_owned(payment_id, current_user_id)
    now = local_now()
    if payment["payment_status"] == "pending":
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE payment_record
                SET payment_status = 'closed',
                    updated_at = %s
                WHERE id = %s
                """,
                (now, payment_id),
            )
        payment = ensure_payment_owned(payment_id, current_user_id)
    return ok(
        {
            "paymentId": payment["id"],
            "paymentNo": payment["payment_no"],
            "orderId": payment["order_id"],
            "paymentStatusCode": payment["payment_status"],
            "updatedAt": format_datetime(payment["updated_at"]),
        }
    )


@router.post("/payment-notifications/mock")
def mock_payment_notification(
    body: Annotated[
        MockPaymentNotificationRequest,
        Body(description="模拟支付渠道异步回调请求体。"),
    ],
    payment_signature: Annotated[
        str | None,
        Header(
            alias="X-Demo-Payment-Signature",
            description="支付通知签名；默认值为 mock-payment-signature，可通过 DEMO_PAYMENT_SIGNATURE 环境变量覆盖。",
        ),
    ] = None,
):
    if payment_signature != DEMO_PAYMENT_SIGNATURE:
        raise unauthorized("INVALID_PAYMENT_SIGNATURE", "支付通知签名不合法")
    if body.tradeStatus not in {"paid", "failed", "closed"}:
        raise bad_request("INVALID_TRADE_STATUS", "交易状态不合法")
    if body.paymentChannelCode not in PAYMENT_CHANNELS:
        raise bad_request("INVALID_PAYMENT_CHANNEL", "支付渠道不合法")
    payment = fetch_one(
        "SELECT * FROM payment_record WHERE payment_no = %s",
        (body.paymentNo,),
    )
    if payment is None:
        raise not_found("PAYMENT_NOT_FOUND", "支付记录不存在")
    order = fetch_one("SELECT * FROM `order` WHERE id = %s", (payment["order_id"],))
    if order is None:
        raise not_found("ORDER_NOT_FOUND", "订单不存在")
    if int(payment["order_id"]) != body.orderId:
        raise conflict("PAYMENT_ORDER_MISMATCH", "支付通知 orderId 与支付记录不一致")
    if payment["payment_channel"] != body.paymentChannelCode:
        raise conflict("PAYMENT_CHANNEL_MISMATCH", "支付通知支付渠道与支付记录不一致")
    if Decimal(str(payment["amount"])) != body.amount:
        raise conflict("PAYMENT_AMOUNT_MISMATCH", "支付通知金额与支付记录不一致")
    if payment["payment_status"] in {"paid", "failed", "closed", "partial_refunded", "refunded"}:
        return ok(
            {
                "paymentId": payment["id"],
                "paymentStatusCode": payment["payment_status"],
                "orderId": order["id"],
                "orderStatusCode": order["order_status"],
                "processed": False,
            }
        )
    if body.tradeStatus == "paid" and payment["payment_status"] != "paid":
        now = local_now()
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE payment_record
                SET payment_status = 'paid',
                    third_party_trade_no = %s,
                    paid_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (body.thirdPartyTradeNo, now, now, payment["id"]),
            )
            cursor.execute(
                """
                UPDATE `order`
                SET order_status = 'paid',
                    paid_amount = payable_amount,
                    paid_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (now, now, order["id"]),
            )
            cursor.execute(
                """
                UPDATE order_item
                SET order_item_status = 'paid', updated_at = %s
                WHERE order_id = %s
                """,
                (now, order["id"]),
            )
            if order["coupon_receive_record_id"]:
                cursor.execute(
                    """
                    UPDATE coupon_receive_record
                    SET receive_status = 'used', used_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (now, now, order["coupon_receive_record_id"]),
                )
    elif body.tradeStatus in {"failed", "closed"} and payment["payment_status"] == "pending":
        now = local_now()
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE payment_record
                SET payment_status = %s,
                    third_party_trade_no = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (body.tradeStatus, body.thirdPartyTradeNo, now, payment["id"]),
            )
    payment = fetch_one("SELECT * FROM payment_record WHERE id = %s", (payment["id"],))
    order = fetch_one("SELECT * FROM `order` WHERE id = %s", (order["id"],))
    assert payment is not None
    assert order is not None
    return ok(
        {
            "paymentId": payment["id"],
            "paymentStatusCode": payment["payment_status"],
            "orderId": order["id"],
            "orderStatusCode": order["order_status"],
            "processed": True,
        }
    )


@router.post("/order-items/{order_item_id}/refund-requests")
def create_refund_request(
    body: Annotated[RefundRequestCreateRequest, Body(description="创建退款申请请求体。")],
    order_item_id: Annotated[int, Path(description="订单明细 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if body.refundType not in REFUND_TYPES:
        raise bad_request("INVALID_REFUND_TYPE", "退款类型不合法")
    if body.applyAmount <= 0:
        raise bad_request("INVALID_REFUND_AMOUNT", "申请退款金额必须大于 0")
    item = ensure_order_item_owned(order_item_id, current_user_id)
    if item["order_item_status"] not in {"paid", "completed"}:
        raise conflict("ORDER_ITEM_NOT_REFUNDABLE", "订单明细当前状态不允许退款")
    if body.applyAmount > Decimal(str(item["payable_amount"])):
        raise conflict("REFUND_AMOUNT_EXCEEDED", "申请退款金额超过可退金额")
    payment = fetch_one(
        """
        SELECT id
        FROM payment_record
        WHERE order_id = %s AND payment_status IN ('paid', 'partial_refunded', 'refunded')
        ORDER BY id DESC
        LIMIT 1
        """,
        (item["order_id"],),
    )
    if payment is None:
        raise conflict("PAYMENT_NOT_FOUND", "订单没有可退款支付记录")
    in_progress = fetch_one(
        """
        SELECT id
        FROM refund_request
        WHERE order_item_id = %s AND refund_status IN ('pending', 'approved')
        LIMIT 1
        """,
        (order_item_id,),
    )
    if in_progress:
        raise conflict("REFUND_IN_PROGRESS", "该订单明细存在处理中的退款申请")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO refund_request (
                institution_id, refund_no, order_id, order_item_id, payment_id,
                user_id, student_id, refund_type, refund_reason, refund_status,
                apply_amount, approved_amount, approver_user_id, remark, yn,
                applied_at, approved_at, refunded_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending',
                %s, NULL, NULL, %s, 1, %s, NULL, NULL, %s, %s)
            """,
            (
                item["institution_id"],
                make_no("RF"),
                item["order_id"],
                order_item_id,
                payment["id"],
                current_user_id,
                item["student_id"],
                body.refundType,
                body.refundReason,
                body.applyAmount,
                body.remark,
                now,
                now,
                now,
            ),
        )
        refund_id = cursor.lastrowid
    row = fetch_one("SELECT refund_no FROM refund_request WHERE id = %s", (refund_id,))
    return ok(
        {
            "refundRequestId": refund_id,
            "refundNo": row["refund_no"] if row else None,
            "refundStatusCode": "pending",
        }
    )


@router.get("/refund-requests")
def list_refund_requests(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="退款状态。可选值：pending、approved、rejected、refunded。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("refund_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM refund_request
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT *
        FROM refund_request
        WHERE {" AND ".join(conditions)}
        ORDER BY applied_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [refund_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.get("/refund-requests/{refund_request_id}")
def get_refund_request_detail(
    refund_request_id: Annotated[int, Path(description="退款申请 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = fetch_one(
        """
        SELECT *
        FROM refund_request
        WHERE id = %s AND user_id = %s
        """,
        (refund_request_id, current_user_id),
    )
    if row is None:
        raise not_found("REFUND_REQUEST_NOT_FOUND", "退款申请不存在")
    return ok(refund_payload(row))
