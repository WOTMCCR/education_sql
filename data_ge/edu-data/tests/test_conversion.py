from __future__ import annotations


def test_get_my_favorites(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get("/api/v1/me/favorites", headers=user_headers(user["user_id"]))
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_post_series_favorite(client, samples, user_headers):
    series = samples.on_sale_series
    user = samples.user_with_student
    response = client.post(
        f"/api/v1/series/{series['id']}/favorite",
        headers=user_headers(user["user_id"]),
        json={"favoriteSource": "series_detail"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["favorited"] is True


def test_delete_series_favorite(client, samples, user_headers):
    series = samples.on_sale_series
    user = samples.user_with_student
    client.post(
        f"/api/v1/series/{series['id']}/favorite",
        headers=user_headers(user["user_id"]),
        json={"favoriteSource": "series_detail"},
    )
    response = client.delete(
        f"/api/v1/series/{series['id']}/favorite",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["favorited"] is False


def test_post_consultation(client, samples, user_headers):
    ctx = samples.consultation_context
    response = client.post(
        f"/api/v1/cohorts/{ctx['cohort_id']}/consultations",
        headers=user_headers(ctx["user_id"]),
        json={
            "consultChannel": "wechat",
            "contactMobile": "13800138000",
            "consultContent": "测试咨询记录",
            "sourceChannelId": ctx["source_channel_id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["consultationId"] > 0


def test_get_my_consultations(client, samples, user_headers):
    ctx = samples.consultation_context
    response = client.get(
        "/api/v1/me/consultations",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_available_coupons(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get(
        "/api/v1/coupons/available",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_post_coupon_receive(client, samples, user_headers):
    ctx = samples.available_coupon_for_user
    response = client.post(
        f"/api/v1/coupons/{ctx['coupon_id']}/receive",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["receiveId"] > 0


def test_post_coupon_receive_limit_exceeded(client, samples, user_headers):
    ctx = samples.available_coupon_for_user
    first_response = client.post(
        f"/api/v1/coupons/{ctx['coupon_id']}/receive",
        headers=user_headers(ctx["user_id"]),
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/coupons/{ctx['coupon_id']}/receive",
        headers=user_headers(ctx["user_id"]),
    )
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "COUPON_RECEIVE_LIMIT_EXCEEDED"


def test_get_my_coupons(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get("/api/v1/me/coupons", headers=user_headers(user["user_id"]))
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_cart_items(client, samples, user_headers):
    user = samples.user_with_student
    response = client.get("/api/v1/cart/items", headers=user_headers(user["user_id"]))
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_post_cart_item(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    response = client.post(
        "/api/v1/cart/items",
        headers=user_headers(user["user_id"]),
        json={"cohortId": row["cohort_id"], "cartSource": "series_detail"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["itemId"] > 0


def test_delete_cart_item(client, samples, user_headers):
    user = samples.user_with_student
    row = samples.on_sale_series_with_cohort
    create_response = client.post(
        "/api/v1/cart/items",
        headers=user_headers(user["user_id"]),
        json={"cohortId": row["cohort_id"], "cartSource": "series_detail"},
    )
    item_id = create_response.json()["data"]["itemId"]
    response = client.delete(
        f"/api/v1/cart/items/{item_id}",
        headers=user_headers(user["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["removed"] is True
