"""Coupon APIs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Path, Query

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import conflict, not_found
from ..response import ok
from ..utils import (
    count_total,
    format_datetime,
    local_now,
    make_no,
    money,
    offset_limit,
)

router = APIRouter(prefix="/api/v1", tags=["coupons"])


def ensure_coupon(coupon_id: int) -> dict[str, object]:
    row = fetch_one("SELECT * FROM coupon WHERE id = %s AND yn = 1", (coupon_id,))
    if row is None:
        raise not_found("COUPON_NOT_FOUND", "优惠券不存在")
    return row


def coupon_payload(row: dict[str, object]) -> dict[str, object]:
    threshold_amount = row["threshold_amount"]
    discount_amount = row["discount_amount"]
    discount_rate = row["discount_rate"]
    valid_from = row["valid_from"]
    valid_to = row["valid_to"]
    return {
        "couponId": row["id"],
        "couponName": row["coupon_name"],
        "issuerScope": row["issuer_scope"],
        "couponType": row["coupon_type"],
        "thresholdAmount": money(cast(Decimal | float | int | None, threshold_amount)),
        "discountAmount": money(cast(Decimal | float | int | None, discount_amount)),
        "discountRate": float(cast(Decimal | float | int, discount_rate))
        if discount_rate is not None
        else None,
        "validFrom": format_datetime(cast(datetime | None, valid_from)),
        "validTo": format_datetime(cast(datetime | None, valid_to)),
    }


def user_receive_count(coupon_id: int, current_user_id: int) -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM coupon_receive_record
        WHERE coupon_id = %s AND user_id = %s
        """,
        (coupon_id, current_user_id),
    )
    return int((row or {}).get("total") or 0)


@router.get("/coupons/available")
def list_available_coupons(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    series_id: Annotated[
        int | None, Query(alias="seriesId", description="课程系列 ID。")
    ] = None,
    category_id: Annotated[
        int | None,
        Query(
            alias="categoryId",
            description="课程分类 ID；分类数量较多，不在接口文档中展开枚举。",
        ),
    ] = None,
):
    now = local_now()
    conditions = [
        "coupon.yn = 1",
        "%s BETWEEN coupon.valid_from AND coupon.valid_to",
        "coupon.receive_count < coupon.total_count",
    ]
    params: list[Any] = [now]
    if series_id is not None:
        conditions.append(
            """
            (
                NOT EXISTS (
                    SELECT 1 FROM coupon_series_rel csr WHERE csr.coupon_id = coupon.id
                )
                OR EXISTS (
                    SELECT 1 FROM coupon_series_rel csr
                    WHERE csr.coupon_id = coupon.id AND csr.series_id = %s
                )
            )
            """
        )
        params.append(series_id)
    if category_id is not None:
        conditions.append(
            """
            (
                NOT EXISTS (
                    SELECT 1 FROM coupon_category_rel ccr WHERE ccr.coupon_id = coupon.id
                )
                OR EXISTS (
                    SELECT 1 FROM coupon_category_rel ccr
                    WHERE ccr.coupon_id = coupon.id AND ccr.category_id = %s
                )
            )
            """
        )
        params.append(category_id)
    rows = fetch_all(
        f"""
        SELECT
            coupon.*,
            COALESCE(user_receive.receive_total, 0) AS user_receive_total
        FROM coupon
        LEFT JOIN (
            SELECT coupon_id, COUNT(*) AS receive_total
            FROM coupon_receive_record
            WHERE user_id = %s
            GROUP BY coupon_id
        ) AS user_receive ON user_receive.coupon_id = coupon.id
        WHERE {" AND ".join(conditions)}
          AND COALESCE(user_receive.receive_total, 0) < coupon.per_user_limit
        ORDER BY valid_to ASC, id ASC
        LIMIT 50
        """,
        tuple([current_user_id] + params),
    )
    return ok([coupon_payload(row) for row in rows])


@router.post("/coupons/{coupon_id}/receive")
def receive_coupon(
    coupon_id: Annotated[int, Path(description="优惠券 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    now = local_now()
    receive_no = make_no("CR")
    with db_cursor() as (_, cursor):
        cursor.execute(
            "SELECT * FROM coupon WHERE id = %s AND yn = 1 FOR UPDATE",
            (coupon_id,),
        )
        coupon = cast(dict[str, object] | None, cursor.fetchone())
        if coupon is None:
            raise not_found("COUPON_NOT_FOUND", "优惠券不存在")

        valid_to = cast(datetime, coupon["valid_to"])
        receive_count = cast(int, coupon["receive_count"])
        total_count = cast(int, coupon["total_count"])
        per_user_limit = cast(int, coupon["per_user_limit"])
        if now > valid_to:
            raise conflict("COUPON_EXPIRED", "优惠券已过有效期")
        if receive_count >= total_count:
            raise conflict("COUPON_OUT_OF_STOCK", "优惠券库存不足")

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM coupon_receive_record
            WHERE coupon_id = %s AND user_id = %s
            """,
            (coupon_id, current_user_id),
        )
        receive_row = cast(dict[str, object] | None, cursor.fetchone())
        user_receive_total = int(cast(int, (receive_row or {}).get("total", 0)))
        if user_receive_total >= per_user_limit:
            raise conflict(
                "COUPON_RECEIVE_LIMIT_EXCEEDED", "已达到当前优惠券的个人领取上限"
            )

        cursor.execute(
            """
            INSERT INTO coupon_receive_record (
                coupon_id, user_id, receive_no, receive_source, receive_status,
                yn, received_at, used_at, expired_at, created_at, updated_at
            ) VALUES (%s, %s, %s, 'user_receive', 'unused', 1, %s, NULL, %s, %s, %s)
            """,
            (
                coupon_id,
                current_user_id,
                receive_no,
                now,
                valid_to,
                now,
                now,
            ),
        )
        receive_id = cursor.lastrowid
        cursor.execute(
            "UPDATE coupon SET receive_count = receive_count + 1, updated_at = %s WHERE id = %s",
            (now, coupon_id),
        )
    return ok({"receiveId": receive_id, "receiveNo": receive_no})


@router.get("/me/coupons")
def list_my_coupons(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    status: Annotated[
        str | None,
        Query(description="领券状态。可选值：unused、used、expired。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")
    ] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["record.user_id = %s"]
    params: list[Any] = [current_user_id]
    if status:
        conditions.append("record.receive_status = %s")
        params.append(status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM coupon_receive_record AS record
        JOIN coupon ON coupon.id = record.coupon_id
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT
            record.id,
            coupon.coupon_name,
            record.receive_status,
            record.received_at,
            record.used_at,
            record.expired_at
        FROM coupon_receive_record AS record
        JOIN coupon ON coupon.id = record.coupon_id
        WHERE {" AND ".join(conditions)}
        ORDER BY record.received_at DESC, record.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [
                {
                    "receiveId": row["id"],
                    "couponName": row["coupon_name"],
                    "receiveStatusCode": row["receive_status"],
                    "receivedAt": format_datetime(row["received_at"]),
                    "usedAt": format_datetime(row["used_at"]),
                    "expiredAt": format_datetime(row["expired_at"]),
                }
                for row in rows
            ],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )
