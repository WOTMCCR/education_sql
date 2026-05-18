from __future__ import annotations


def create_order(client, user_headers, user_id: int, student_id: int, cohort_id: int) -> int:
    response = client.post(
        "/api/v1/orders",
        headers=user_headers(user_id),
        json={
            "studentId": student_id,
            "cohortId": cohort_id,
            "couponReceiveRecordId": None,
            "orderSourceChannelId": None,
            "remark": "pytest create order",
        },
    )
    assert response.status_code == 200
    return int(response.json()["data"]["orderId"])


def create_payment(client, user_headers, user_id: int, order_id: int) -> int:
    response = client.post(
        f"/api/v1/orders/{order_id}/payments",
        headers=user_headers(user_id),
        json={"paymentChannelCode": "wechat_pay"},
    )
    assert response.status_code == 200
    return int(response.json()["data"]["paymentId"])


def notify_payment_paid(client, payment: dict[str, object]) -> None:
    response = client.post(
        "/api/v1/payment-notifications/mock",
        headers={"X-Demo-Payment-Signature": "mock-payment-signature"},
        json={
            "paymentNo": payment["payment_no"],
            "orderId": payment["order_id"],
            "paymentChannelCode": payment["payment_channel"],
            "amount": str(payment["amount"]),
            "tradeStatus": "paid",
            "thirdPartyTradeNo": "TP_PYTEST_0001",
        },
    )
    assert response.status_code == 200


def test_post_orders_quote(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    response = client.post(
        "/api/v1/orders/quote",
        headers=user_headers(user["user_id"]),
        json={"cohortId": row["cohort_id"], "couponReceiveRecordId": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["cohortId"] == row["cohort_id"]


def test_post_orders_quote_coupon_not_applicable(client, samples, user_headers):
    ctx = samples.inapplicable_coupon_order_context
    response = client.post(
        "/api/v1/orders/quote",
        headers=user_headers(ctx["user_id"]),
        json={
            "cohortId": ctx["cohort_id"],
            "couponReceiveRecordId": ctx["coupon_receive_record_id"],
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_NOT_APPLICABLE"


def test_post_orders(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    assert order_id > 0


def test_post_orders_source_channel_mismatch(client, samples, user_headers):
    ctx = samples.consultation_context
    response = client.post(
        "/api/v1/orders",
        headers=user_headers(ctx["user_id"]),
        json={
            "studentId": ctx["student_id"],
            "cohortId": ctx["cohort_id"],
            "couponReceiveRecordId": None,
            "orderSourceChannelId": samples.alternative_channel_id,
            "remark": "pytest mismatch channel",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_SOURCE_CHANNEL_MISMATCH"


def test_get_orders(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get("/api/v1/orders", headers=user_headers(user["user_id"]))
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_order_detail(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    response = client.get(f"/api/v1/orders/{order_id}", headers=user_headers(user["user_id"]))
    assert response.status_code == 200
    assert response.json()["data"]["orderId"] == order_id


def test_post_order_cancel(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=user_headers(user["user_id"]),
        json={"reason": "pytest cancel"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["orderStatusCode"] == "cancelled"


def test_post_order_payment_create(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    response = client.post(
        f"/api/v1/orders/{order_id}/payments",
        headers=user_headers(user["user_id"]),
        json={"paymentChannelCode": "wechat_pay"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["paymentId"] > 0


def test_get_order_payments(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    create_payment(client, user_headers, user["user_id"], order_id)
    response = client.get(
        f"/api/v1/orders/{order_id}/payments",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"]["list"], list)


def test_get_payment_detail(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    payment_id = create_payment(client, user_headers, user["user_id"], order_id)
    response = client.get(
        f"/api/v1/payments/{payment_id}",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["paymentId"] == payment_id


def test_post_mock_payment_notification(client, samples, user_headers, db):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    payment_id = create_payment(client, user_headers, user["user_id"], order_id)
    payment = db["fetch_one"](
        "SELECT payment_no, order_id, payment_channel, amount FROM payment_record WHERE id = %s",
        (payment_id,),
    )
    assert payment is not None
    response = client.post(
        "/api/v1/payment-notifications/mock",
        headers={"X-Demo-Payment-Signature": "mock-payment-signature"},
        json={
            "paymentNo": payment["payment_no"],
            "orderId": payment["order_id"],
            "paymentChannelCode": payment["payment_channel"],
            "amount": str(payment["amount"]),
            "tradeStatus": "paid",
            "thirdPartyTradeNo": "TP_PYTEST_0001",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["paymentStatusCode"] == "paid"
    assert response.json()["data"]["orderStatusCode"] == "paid"


def test_close_payment(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    payment_id = create_payment(client, user_headers, user["user_id"], order_id)
    response = client.post(
        f"/api/v1/payments/{payment_id}/close",
        headers=user_headers(user["user_id"]),
        json={"closeReason": "pytest close"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["paymentStatusCode"] == "closed"


def test_post_refund_request(client, samples, user_headers, db):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    payment_id = create_payment(client, user_headers, user["user_id"], order_id)
    payment = db["fetch_one"](
        "SELECT payment_no, order_id, payment_channel, amount FROM payment_record WHERE id = %s",
        (payment_id,),
    )
    assert payment is not None
    notify_payment_paid(client, payment)
    order_item = db["fetch_one"](
        "SELECT id FROM order_item WHERE order_id = %s ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    assert order_item is not None
    response = client.post(
        f"/api/v1/order-items/{order_item['id']}/refund-requests",
        headers=user_headers(user["user_id"]),
        json={
            "refundType": "personal_reason",
            "refundReason": "pytest refund",
            "applyAmount": "100.00",
            "remark": "pytest",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["refundRequestId"] > 0


def test_get_refund_requests(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get(
        "/api/v1/refund-requests",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_refund_request_detail(client, samples, user_headers, db):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    order_id = create_order(
        client, user_headers, user["user_id"], user["student_id"], row["cohort_id"]
    )
    payment_id = create_payment(client, user_headers, user["user_id"], order_id)
    payment = db["fetch_one"](
        "SELECT payment_no, order_id, payment_channel, amount FROM payment_record WHERE id = %s",
        (payment_id,),
    )
    assert payment is not None
    notify_payment_paid(client, payment)
    order_item = db["fetch_one"](
        "SELECT id FROM order_item WHERE order_id = %s ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    assert order_item is not None
    create_response = client.post(
        f"/api/v1/order-items/{order_item['id']}/refund-requests",
        headers=user_headers(user["user_id"]),
        json={
            "refundType": "personal_reason",
            "refundReason": "pytest refund detail",
            "applyAmount": "100.00",
            "remark": "pytest",
        },
    )
    refund_request_id = create_response.json()["data"]["refundRequestId"]
    response = client.get(
        f"/api/v1/refund-requests/{refund_request_id}",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["refundRequestId"] == refund_request_id
