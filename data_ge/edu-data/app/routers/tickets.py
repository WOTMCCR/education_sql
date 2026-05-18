"""Service-ticket APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import get_current_user_id
from ..errors import bad_request, conflict, not_found
from ..response import ok
from ..utils import count_total, format_datetime, local_now, make_no, offset_limit

router = APIRouter(prefix="/api/v1", tags=["tickets"])

TICKET_TYPES = {"after_sales", "complaint", "refund"}
PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}
TICKET_SOURCES = {"user_app", "customer_service"}


class ServiceTicketCreateRequest(BaseModel):
    ticketType: str = Field(description="工单类型。可选值：after_sales、complaint、refund。")
    priorityLevel: str = Field(description="优先级。可选值：low、medium、high、urgent。")
    ticketSource: str = Field(description="工单来源。可选值：user_app、customer_service。")
    title: str = Field(description="标题。")
    ticketContent: str = Field(description="工单内容。")
    studentId: int = Field(description="学员档案 ID。")
    orderItemId: int = Field(description="订单明细 ID。")
    refundRequestId: int | None = Field(default=None, description="退款申请 ID。")


class SatisfactionSurveyCreateRequest(BaseModel):
    scoreValue: int = Field(description="满意度评分，取值范围 1 到 5。")
    commentText: str | None = Field(default=None, description="反馈内容。")


def ticket_list_payload(row: dict[str, object]) -> dict[str, object]:
    created_at = row["created_at"]
    return {
        "ticketId": row["id"],
        "ticketNo": row["ticket_no"],
        "ticketType": row["ticket_type"],
        "ticketStatus": row["ticket_status"],
        "title": row["title"],
        "openedAt": format_datetime(cast(datetime | None, created_at)),
    }


def validate_ticket_body(body: ServiceTicketCreateRequest) -> None:
    if body.ticketType not in TICKET_TYPES:
        raise bad_request("INVALID_TICKET_TYPE", "工单类型不合法")
    if body.priorityLevel not in PRIORITY_LEVELS:
        raise bad_request("INVALID_PRIORITY_LEVEL", "优先级不合法")
    if body.ticketSource not in TICKET_SOURCES:
        raise bad_request("INVALID_TICKET_SOURCE", "工单来源不合法")
    if not body.title.strip():
        raise bad_request("INVALID_TITLE", "工单标题不能为空")
    if not body.ticketContent.strip():
        raise bad_request("INVALID_CONTENT", "工单内容不能为空")


def ensure_order_item_owned(order_item_id: int, current_user_id: int) -> dict[str, object]:
    row = fetch_one(
        "SELECT * FROM order_item WHERE id = %s AND user_id = %s",
        (order_item_id, current_user_id),
    )
    if row is None:
        raise not_found("ORDER_ITEM_NOT_FOUND", "订单明细不存在")
    return row


def ensure_student_owned(student_id: int, current_user_id: int) -> dict[str, object]:
    row = fetch_one(
        "SELECT * FROM student_profile WHERE id = %s AND user_id = %s AND yn = 1",
        (student_id, current_user_id),
    )
    if row is None:
        raise not_found("STUDENT_PROFILE_NOT_FOUND", "学员档案不存在")
    return row


def ensure_refund_owned(
    refund_request_id: int | None, current_user_id: int
) -> dict[str, object]:
    if refund_request_id is None:
        raise bad_request("MISSING_REFUND_REQUEST", "退款类工单必须关联退款申请")
    row = fetch_one(
        "SELECT * FROM refund_request WHERE id = %s AND user_id = %s",
        (refund_request_id, current_user_id),
    )
    if row is None:
        raise not_found("REFUND_REQUEST_NOT_FOUND", "退款申请不存在")
    return row


def find_assignee(institution_id: int) -> dict[str, object] | None:
    return fetch_one(
        """
        SELECT staff.user_id
        FROM staff_profile AS staff
        JOIN org_staff_role AS role ON role.id = staff.staff_role_id
        WHERE staff.institution_id = %s
          AND role.role_category IN ('service', 'operations', 'management')
          AND staff.yn = 1
        ORDER BY staff.id
        LIMIT 1
        """,
        (institution_id,),
    )


def ensure_ticket_owned(ticket_id: int, current_user_id: int) -> dict[str, object]:
    row = fetch_one(
        "SELECT * FROM service_ticket WHERE id = %s AND user_id = %s AND yn = 1",
        (ticket_id, current_user_id),
    )
    if row is None:
        raise not_found("TICKET_NOT_FOUND", "工单不存在")
    return row


@router.get("/service-tickets")
def list_service_tickets(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    ticket_type: Annotated[
        str | None,
        Query(alias="ticketType", description="工单类型。可选值：after_sales、complaint、refund。"),
    ] = None,
    ticket_status: Annotated[
        str | None,
        Query(alias="ticketStatus", description="工单状态。可选值：pending、in_progress、closed。"),
    ] = None,
    page_no: Annotated[int, Query(alias="pageNo", description="页码，从 1 开始。")] = 1,
    page_size: Annotated[int, Query(alias="pageSize", description="每页条数，范围 1 到 100。")] = 20,
):
    offset, limit = offset_limit(page_no, page_size)
    conditions = ["user_id = %s", "yn = 1"]
    params: list[object] = [current_user_id]
    if ticket_type:
        conditions.append("ticket_type = %s")
        params.append(ticket_type)
    if ticket_status:
        conditions.append("ticket_status = %s")
        params.append(ticket_status)
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM service_ticket
        WHERE {" AND ".join(conditions)}
        """,
        tuple(params),
    )
    rows = fetch_all(
        f"""
        SELECT *
        FROM service_ticket
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    return ok(
        {
            "list": [ticket_list_payload(row) for row in rows],
            "pageNo": page_no,
            "pageSize": page_size,
            "total": total,
        }
    )


@router.post("/service-tickets")
def create_service_ticket(
    body: Annotated[ServiceTicketCreateRequest, Body(description="创建服务工单请求体。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    validate_ticket_body(body)
    item = ensure_order_item_owned(body.orderItemId, current_user_id)
    student = ensure_student_owned(body.studentId, current_user_id)
    if student["id"] != item["student_id"]:
        raise bad_request("STUDENT_MISMATCH", "学员档案与订单明细不匹配")
    if body.ticketType == "refund":
        refund = ensure_refund_owned(body.refundRequestId, current_user_id)
        if refund["order_item_id"] != body.orderItemId:
            raise bad_request("REFUND_MISMATCH", "退款申请与订单明细不匹配")
    elif body.refundRequestId is not None:
        raise bad_request("INVALID_REFUND_LINK", "非退款工单不能关联退款申请")
    assignee = find_assignee(cast(int, item["institution_id"]))
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO service_ticket (
                institution_id, ticket_no, user_id, student_id, order_item_id,
                refund_request_id, ticket_type, ticket_source, priority_level,
                ticket_status, assignee_user_id, title, ticket_content, yn,
                first_response_at, closed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s,
                %s, %s, 1, NULL, NULL, %s, %s)
            """,
            (
                item["institution_id"],
                make_no("TK"),
                current_user_id,
                body.studentId,
                body.orderItemId,
                body.refundRequestId,
                body.ticketType,
                body.ticketSource,
                body.priorityLevel,
                assignee["user_id"] if assignee else None,
                body.title,
                body.ticketContent,
                now,
                now,
            ),
        )
        ticket_id = cursor.lastrowid
    row = fetch_one("SELECT ticket_no FROM service_ticket WHERE id = %s", (ticket_id,))
    return ok(
        {
            "ticketId": ticket_id,
            "ticketNo": row["ticket_no"] if row else None,
            "ticketStatus": "pending",
        }
    )


@router.get("/service-tickets/{ticket_id}")
def get_service_ticket_detail(
    ticket_id: Annotated[int, Path(description="工单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    row = ensure_ticket_owned(ticket_id, current_user_id)
    created_at = row["created_at"]
    closed_at = row["closed_at"]
    return ok(
        {
            "ticketId": row["id"],
            "ticketNo": row["ticket_no"],
            "ticketType": row["ticket_type"],
            "ticketStatus": row["ticket_status"],
            "title": row["title"],
            "ticketContent": row["ticket_content"],
            "refundRequestId": row["refund_request_id"],
            "openedAt": format_datetime(cast(datetime | None, created_at)),
            "closedAt": format_datetime(cast(datetime | None, closed_at)),
        }
    )


@router.get("/service-tickets/{ticket_id}/follow-records")
def list_service_ticket_follow_records(
    ticket_id: Annotated[int, Path(description="工单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    ensure_ticket_owned(ticket_id, current_user_id)
    rows = fetch_all(
        """
        SELECT id, follow_type, follow_channel, follow_result, follow_content, followed_at
        FROM service_ticket_follow_record
        WHERE ticket_id = %s
        ORDER BY followed_at ASC, id ASC
        """,
        (ticket_id,),
    )
    return ok(
        [
            {
                "followRecordId": row["id"],
                "followType": row["follow_type"],
                "followChannel": row["follow_channel"],
                "followResult": row["follow_result"],
                "followContent": row["follow_content"],
                "followedAt": format_datetime(row["followed_at"]),
            }
            for row in rows
        ]
    )


@router.post("/service-tickets/{ticket_id}/satisfaction-surveys")
def create_satisfaction_survey(
    body: Annotated[SatisfactionSurveyCreateRequest, Body(description="提交工单满意度评价请求体。")],
    ticket_id: Annotated[int, Path(description="工单 ID。")],
    current_user_id: Annotated[int, Depends(get_current_user_id)],
):
    if not 1 <= body.scoreValue <= 5:
        raise bad_request("INVALID_SCORE", "满意度评分必须在 1 到 5 之间")
    ticket = ensure_ticket_owned(ticket_id, current_user_id)
    if ticket["ticket_status"] != "closed":
        raise conflict("TICKET_NOT_CLOSED", "只有已关闭工单允许提交满意度评价")
    exists = fetch_one(
        "SELECT id FROM service_ticket_satisfaction_survey WHERE ticket_id = %s AND yn = 1",
        (ticket_id,),
    )
    if exists:
        raise conflict("SURVEY_EXISTS", "同一工单只允许提交一条有效满意度记录")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO service_ticket_satisfaction_survey (
                survey_no, user_id, student_id, ticket_id, score_value,
                comment_text, yn, surveyed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            """,
            (
                make_no("SV"),
                current_user_id,
                ticket["student_id"],
                ticket_id,
                body.scoreValue,
                body.commentText,
                now,
                now,
                now,
            ),
        )
        survey_id = cursor.lastrowid
    return ok({"surveyId": survey_id})
