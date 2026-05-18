"""Consultation APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import bad_request, conflict, not_found
from ..response import ok
from ..utils import count_total, format_datetime, local_now, offset_limit

router = APIRouter(prefix="/api/v1", tags=["consultations"])

CONSULT_CHANNELS = {"phone", "online_chat", "wechat", "offline_visit"}


class ConsultationCreateRequest(BaseModel):
    consultChannel: str = Field(
        description="咨询渠道。可选值：phone、online_chat、wechat、offline_visit。"
    )
    contactMobile: str = Field(description="咨询人联系电话。")
    consultContent: str | None = Field(default=None, description="咨询内容。")
    sourceChannelId: int = Field(description="来源渠道 ID。")


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


@router.post("/cohorts/{cohort_id}/consultations")
def create_consultation(
    body: Annotated[
        ConsultationCreateRequest, Body(description="创建咨询记录请求体。")
    ],
    cohort_id: Annotated[int, Path(description="班次 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if body.consultChannel not in CONSULT_CHANNELS:
        raise bad_request("INVALID_CONSULT_CHANNEL", "咨询渠道不合法")
    cohort = ensure_cohort(cohort_id)
    if (
        fetch_one(
            "SELECT id FROM dim_channel WHERE id = %s AND yn = 1",
            (body.sourceChannelId,),
        )
        is None
    ):
        raise not_found("CHANNEL_NOT_FOUND", "来源渠道不存在")
    consultant = fetch_one(
        """
        SELECT staff.user_id
        FROM staff_profile AS staff
        JOIN org_staff_role AS role ON role.id = staff.staff_role_id
        WHERE staff.institution_id = %s
          AND role.role_category IN ('sales', 'service')
          AND staff.yn = 1
        ORDER BY staff.id
        LIMIT 1
        """,
        (cohort["institution_id"],),
    )
    if consultant is None:
        raise conflict("NO_CONSULTANT", "当前班次所属机构没有可用顾问")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO consultation_record (
                user_id, cohort_id, consultant_user_id, source_channel_id,
                consult_channel, contact_mobile, consult_content,
                consulted_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                current_user_id,
                cohort_id,
                consultant["user_id"],
                body.sourceChannelId,
                body.consultChannel,
                body.contactMobile,
                body.consultContent,
                now,
                now,
                now,
            ),
        )
        consultation_id = cursor.lastrowid
    return ok({"consultationId": consultation_id})


@router.get("/me/consultations")
def list_my_consultations(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")
    ] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    total = count_total(
        """
        SELECT COUNT(*) AS total
        FROM consultation_record
        WHERE user_id = %s
        """,
        (current_user_id,),
    )
    rows = fetch_all(
        """
        SELECT
            id, cohort_id, consult_channel, consult_content, consulted_at
        FROM consultation_record
        WHERE user_id = %s
        ORDER BY consulted_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (current_user_id, limit, offset),
    )
    return ok(
        {
            "list": [
                {
                    "consultationId": row["id"],
                    "cohortId": row["cohort_id"],
                    "consultChannel": row["consult_channel"],
                    "consultContent": row["consult_content"],
                    "consultedAt": format_datetime(row["consulted_at"]),
                }
                for row in rows
            ],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )
