import os

import pytest


pytestmark = pytest.mark.integration


def test_live_health_endpoints(client) -> None:
    backend_health = client.get("/health")
    admin_health = client.get("/api/admin/health")
    vision_health = client.get("/api/vision/health")
    unauthenticated_admin_list = client.get("/api/admin/employees")

    assert backend_health.status_code == 200
    assert backend_health.json()["status"] == "ok"
    assert admin_health.status_code == 200
    assert admin_health.json() == {"status": "ok", "scope": "admin"}
    assert vision_health.status_code == 200
    assert vision_health.json() == {"status": "ok", "scope": "vision"}
    assert unauthenticated_admin_list.status_code == 401


def test_live_login_issues_bearer_token(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "username": os.getenv("FACE_DETECTOR_ADMIN_USERNAME", "admin"),
            "password": os.getenv("FACE_DETECTOR_ADMIN_PASSWORD", "local-admin-password"),
        },
        )

    response.raise_for_status()
    payload = response.json()

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]