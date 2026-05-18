"""Favorite APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all
from ..dependencies import get_current_user_id
from ..errors import bad_request, not_found
from ..response import ok
from ..utils import count_total, format_datetime, local_now, offset_limit

router = APIRouter(prefix="/api/v1", tags=["favorites"])

FAVORITE_SOURCES = {"series_detail", "search_result", "recommendation", "activity_page"}


class FavoriteCreateRequest(BaseModel):
    favoriteSource: str = Field(
        description="收藏来源。可选值：series_detail、search_result、recommendation、activity_page。"
    )


def ensure_series(series_id: int) -> dict[str, object]:
    row = fetch_all(
        "SELECT * FROM series WHERE id = %s AND sale_status = 'on_sale'",
        (series_id,),
    )
    if not row:
        raise not_found("SERIES_NOT_FOUND", "课程不存在")
    return row[0]


@router.get("/me/favorites")
def list_my_favorites(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    total = count_total(
        """
        SELECT COUNT(*) AS total
        FROM series_favorite AS fav
        WHERE fav.user_id = %s AND fav.yn = 1
        """,
        (current_user_id,),
    )
    rows = fetch_all(
        """
        SELECT
            fav.series_id,
            s.series_name,
            fav.created_at
        FROM series_favorite AS fav
        JOIN series AS s ON s.id = fav.series_id
        WHERE fav.user_id = %s AND fav.yn = 1
        ORDER BY fav.created_at DESC, fav.id DESC
        LIMIT %s OFFSET %s
        """,
        (current_user_id, limit, offset),
    )
    return ok(
        {
            "list": [
                {
                    "seriesId": row["series_id"],
                    "seriesName": row["series_name"],
                    "favoriteCreatedAt": format_datetime(row["created_at"]),
                }
                for row in rows
            ],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.post("/series/{series_id}/favorite")
def favorite_series(
    body: Annotated[FavoriteCreateRequest, Body(description="收藏课程请求体。")],
    series_id: Annotated[int, Path(description="课程系列 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if body.favoriteSource not in FAVORITE_SOURCES:
        raise bad_request("INVALID_FAVORITE_SOURCE", "收藏来源不合法")
    ensure_series(series_id)
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id, yn
            FROM series_favorite
            WHERE user_id = %s AND series_id = %s
            """,
            (current_user_id, series_id),
        )
        exists = cursor.fetchone()
        if exists:
            cursor.execute(
                """
                UPDATE series_favorite
                SET yn = 1, favorite_source = %s, updated_at = %s
                WHERE id = %s
                """,
                (body.favoriteSource, now, exists["id"]),
            )
            return ok(
                {
                    "favoriteId": exists["id"],
                    "favorited": True,
                    "created": bool(exists["yn"] == 0),
                }
            )
        cursor.execute(
            """
            INSERT INTO series_favorite (
                user_id, series_id, favorite_source, yn, created_at, updated_at
            ) VALUES (%s, %s, %s, 1, %s, %s)
            """,
            (current_user_id, series_id, body.favoriteSource, now, now),
        )
        favorite_id = cursor.lastrowid
    return ok({"favoriteId": favorite_id, "favorited": True, "created": True})


@router.delete("/series/{series_id}/favorite")
def unfavorite_series(
    series_id: Annotated[int, Path(description="课程系列 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE series_favorite
            SET yn = 0, updated_at = %s
            WHERE user_id = %s AND series_id = %s
            """,
            (now, current_user_id, series_id),
        )
    return ok({"favorited": False})
