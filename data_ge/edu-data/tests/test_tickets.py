from __future__ import annotations


def create_ticket(client, user_headers, user_id: int, student_id: int, order_item_id: int) -> int:
    response = client.post(
        "/api/v1/service-tickets",
        headers=user_headers(user_id),
        json={
            "ticketType": "after_sales",
            "priorityLevel": "medium",
            "ticketSource": "user_app",
            "title": "pytest ticket",
            "ticketContent": "pytest service ticket content",
            "studentId": student_id,
            "orderItemId": order_item_id,
            "refundRequestId": None,
        },
    )
    assert response.status_code == 200
    return int(response.json()["data"]["ticketId"])


def test_get_service_tickets(client, samples, user_headers):
    ctx = samples.ticket_context
    response = client.get(
        "/api/v1/service-tickets",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_post_service_ticket(client, samples, user_headers):
    ctx = samples.ticket_context
    ticket_id = create_ticket(
        client,
        user_headers,
        ctx["user_id"],
        ctx["student_id"],
        ctx["order_item_id"],
    )
    assert ticket_id > 0


def test_get_service_ticket_detail(client, samples, user_headers):
    ctx = samples.ticket_context
    ticket_id = create_ticket(
        client,
        user_headers,
        ctx["user_id"],
        ctx["student_id"],
        ctx["order_item_id"],
    )
    response = client.get(
        f"/api/v1/service-tickets/{ticket_id}",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["ticketId"] == ticket_id


def test_get_service_ticket_follow_records(client, samples, user_headers):
    ctx = samples.ticket_context
    ticket_id = create_ticket(
        client,
        user_headers,
        ctx["user_id"],
        ctx["student_id"],
        ctx["order_item_id"],
    )
    response = client.get(
        f"/api/v1/service-tickets/{ticket_id}/follow-records",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_post_service_ticket_satisfaction_survey(client, samples, user_headers, db):
    closed_ticket = samples.closed_unsurveyed_ticket
    if closed_ticket is None:
        ctx = samples.ticket_context
        ticket_id = create_ticket(
            client,
            user_headers,
            ctx["user_id"],
            ctx["student_id"],
            ctx["order_item_id"],
        )
        with db["cursor"]() as (_, cursor):
            cursor.execute(
                """
                UPDATE service_ticket
                SET ticket_status = 'closed', closed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (ticket_id,),
            )
        closed_ticket = {"ticket_id": ticket_id, "user_id": ctx["user_id"]}

    response = client.post(
        f"/api/v1/service-tickets/{closed_ticket['ticket_id']}/satisfaction-surveys",
        headers=user_headers(closed_ticket["user_id"]),
        json={"scoreValue": 5, "commentText": "pytest survey"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["surveyId"] > 0
