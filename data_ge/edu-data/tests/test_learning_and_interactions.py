from __future__ import annotations


def test_get_my_cohorts(client, samples, user_headers):
    rel = samples.active_rel
    response = client.get("/api/v1/me/cohorts", headers=user_headers(rel["user_id"]))
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_my_cohort_detail(client, samples, user_headers):
    rel = samples.active_rel
    response = client.get(
        f"/api/v1/me/cohorts/{rel['cohort_id']}",
        headers=user_headers(rel["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["cohortId"] == rel["cohort_id"]


def test_get_my_cohort_sessions(client, samples, user_headers):
    rel = samples.active_rel
    response = client.get(
        f"/api/v1/me/cohorts/{rel['cohort_id']}/sessions",
        headers=user_headers(rel["user_id"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_get_my_cohort_progress(client, samples, user_headers):
    rel = samples.active_rel
    response = client.get(
        f"/api/v1/me/cohorts/{rel['cohort_id']}/progress",
        headers=user_headers(rel["user_id"]),
    )
    assert response.status_code == 200
    assert "attendance" in response.json()["data"]


def test_get_session_detail(client, samples, user_headers):
    ctx = samples.accessible_session
    response = client.get(
        f"/api/v1/sessions/{ctx['session_id']}",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["sessionId"] == ctx["session_id"]


def test_get_video_detail(client, samples, user_headers):
    ctx = samples.accessible_video
    response = client.get(
        f"/api/v1/videos/{ctx['video_id']}",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["videoId"] == ctx["video_id"]


def test_get_video_chapters(client, samples, user_headers):
    ctx = samples.accessible_video
    response = client.get(
        f"/api/v1/videos/{ctx['video_id']}/chapters",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_get_video_history(client, samples, user_headers):
    ctx = samples.accessible_video
    response = client.get(
        "/api/v1/me/video-history",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_my_homeworks(client, samples, user_headers):
    ctx = samples.accessible_homework
    response = client.get(
        "/api/v1/me/homeworks",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_homework_detail(client, samples, user_headers):
    ctx = samples.accessible_homework
    response = client.get(
        f"/api/v1/homeworks/{ctx['homework_id']}",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["homeworkId"] == ctx["homework_id"]


def test_get_homework_submissions(client, samples, user_headers):
    ctx = samples.accessible_homework
    response = client.get(
        "/api/v1/me/homework-submissions",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_my_exams(client, samples, user_headers):
    ctx = samples.accessible_exam
    response = client.get("/api/v1/me/exams", headers=user_headers(ctx["user_id"]))
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_get_exam_detail(client, samples, user_headers):
    ctx = samples.accessible_exam
    response = client.get(
        f"/api/v1/exams/{ctx['exam_id']}",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["examId"] == ctx["exam_id"]


def test_get_exam_submissions(client, samples, user_headers):
    ctx = samples.accessible_exam
    response = client.get(
        "/api/v1/me/exam-submissions",
        headers=user_headers(ctx["user_id"]),
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]


def test_post_cohort_review(client, samples, user_headers):
    ctx = samples.review_context
    response = client.post(
        f"/api/v1/cohorts/{ctx['cohort_id']}/reviews",
        headers=user_headers(ctx["user_id"]),
        json={
            "scoreOverall": 5,
            "scoreTeacher": 5,
            "scoreContent": 5,
            "scoreService": 5,
            "reviewTags": ["pytest", "good"],
            "reviewContent": "pytest review",
            "anonymousFlag": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["reviewId"] > 0


def test_get_cohort_reviews(client, samples, user_headers):
    ctx = samples.review_context
    client.post(
        f"/api/v1/cohorts/{ctx['cohort_id']}/reviews",
        headers=user_headers(ctx["user_id"]),
        json={
            "scoreOverall": 5,
            "scoreTeacher": 5,
            "scoreContent": 5,
            "scoreService": 5,
            "reviewTags": ["pytest", "good"],
            "reviewContent": "pytest review list",
            "anonymousFlag": 0,
        },
    )
    response = client.get(
        f"/api/v1/cohorts/{ctx['cohort_id']}/reviews",
        headers=user_headers(ctx["user_id"]),
        params={"onlyMine": "true"},
    )
    assert response.status_code == 200
    assert "total" in response.json()["data"]
