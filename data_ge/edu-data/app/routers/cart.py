"""Cart APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import bad_request, not_found
from ..response import ok
from ..utils import format_datetime, local_now, money

router = APIRouter(prefix="/api/v1", tags=["cart"])

CART_SOURCES = {"series_detail", "search_result", "recommendation", "activity_page"}


class CartItemCreateRequest(BaseModel):
    cohortId: int = Field(description="班次 ID。")
    cartSource: str = Field(
        description="加入来源。可选值：series_detail、search_result、recommendation、activity_page。"
    )


def ensure_cohort(cohort_id: int) -> dict[str, object]:
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


@router.get("/cart/items")
def list_cart_items(current_user_id: Annotated[int, Depends(get_current_user_id)]):
    rows = fetch_all(
        """
        SELECT
            cart.id,
            cart.cohort_id,
            cohort.cohort_name,
            cart.unit_price,
            cart.added_at
        FROM shopping_cart_item AS cart
        JOIN series_cohort AS cohort ON cohort.id = cart.cohort_id
        WHERE cart.user_id = %s AND cart.removed_at IS NULL
        ORDER BY cart.added_at DESC, cart.id DESC
        """,
        (current_user_id,),
    )
    return ok(
        [
            {
                "itemId": row["id"],
                "cohortId": row["cohort_id"],
                "cohortName": row["cohort_name"],
                "unitPrice": money(row["unit_price"]),
                "addedAt": format_datetime(row["added_at"]),
            }
            for row in rows
        ]
    )


@router.post("/cart/items")
def add_cart_item(
    body: Annotated[CartItemCreateRequest, Body(description="加入购物车请求体。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if body.cartSource not in CART_SOURCES:
        raise bad_request("INVALID_CART_SOURCE", "加入来源不合法")
    cohort = ensure_cohort(body.cohortId)
    now = local_now()
    unit_price = cohort["sale_price"]
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id, removed_at
            FROM shopping_cart_item
            WHERE user_id = %s AND cohort_id = %s
            """,
            (current_user_id, body.cohortId),
        )
        exists = cursor.fetchone()
        if exists:
            if exists["removed_at"] is not None:
                cursor.execute(
                    """
                    UPDATE shopping_cart_item
                    SET unit_price = %s, cart_source = %s, added_at = %s,
                        removed_at = NULL, updated_at = %s
                    WHERE id = %s
                    """,
                    (unit_price, body.cartSource, now, now, exists["id"]),
                )
            return ok({"itemId": exists["id"]})
        cursor.execute(
            """
            INSERT INTO shopping_cart_item (
                user_id, cohort_id, unit_price, cart_source, added_at,
                removed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NULL, %s, %s)
            """,
            (
                current_user_id,
                body.cohortId,
                unit_price,
                body.cartSource,
                now,
                now,
                now,
            ),
        )
        item_id = cursor.lastrowid
    return ok({"itemId": item_id})


@router.delete("/cart/items/{item_id}")
def remove_cart_item(
    item_id: Annotated[int, Path(description="购物车项 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE shopping_cart_item
            SET removed_at = %s, updated_at = %s
            WHERE id = %s AND user_id = %s AND removed_at IS NULL
            """,
            (now, now, item_id, current_user_id),
        )
    return ok({"removed": True})
