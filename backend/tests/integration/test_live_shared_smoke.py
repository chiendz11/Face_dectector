import os
import time

import pytest


pytestmark = pytest.mark.integration


def _request_with_retry(client, method: str, path: str, attempts: int = 6, **kwargs):
    response = None
    for attempt in range(attempts):
        response = client.request(method, path, **kwargs)
        if response.status_code != 429:
            return response
        if attempt < attempts - 1:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.5
            except ValueError:
                delay = 0.5
            time.sleep(max(delay, 0.5))
    return response


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


def test_live_login_rejects_wrong_password(client) -> None:
    response = _request_with_retry(
        client,
        "POST",
        "/api/auth/login",
        json={
            "username": os.getenv("FACE_DETECTOR_ADMIN_USERNAME", "admin"),
            "password": "completely-wrong-password",
        },
    )

    assert response.status_code in {401, 429}


def test_live_login_rejects_missing_password_field(client) -> None:
    response = _request_with_retry(
        client,
        "POST",
        "/api/auth/login",
        json={"username": os.getenv("FACE_DETECTOR_ADMIN_USERNAME", "admin")},
    )

    assert response.status_code in {422, 429}


def test_live_all_protected_endpoints_require_token(client) -> None:
    endpoints = [
        ("GET", "/api/admin/employees"),
        ("POST", "/api/admin/employees"),
        ("DELETE", "/api/admin/employees/EMP-DUMMY"),
        ("POST", "/api/admin/employees/EMP-DUMMY/enroll"),
    ]
    for method, path in endpoints:
        response = _request_with_retry(client, method, path)
        assert response.status_code in {401, 429}, (
            f"{method} {path} expected 401/429, got {response.status_code}"
        )


def test_live_recognize_rejects_empty_file(client) -> None:
    response = _request_with_retry(
        client,
        "POST",
        "/api/vision/recognize",
        data={"device_name": "gate-01"},
        files={"file": ("face.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400


def test_live_create_employee_rejects_duplicate_code(client, auth_headers) -> None:
    employee_code = f"DUP-{int(time.time())}"

    _request_with_retry(
        client,
        "POST",
        "/api/admin/employees",
        headers=auth_headers,
        json={"employee_code": employee_code, "full_name": "Duplicate A", "department": "Test"},
    ).raise_for_status()

    second = _request_with_retry(
        client,
        "POST",
        "/api/admin/employees",
        headers=auth_headers,
        json={"employee_code": employee_code, "full_name": "Duplicate B", "department": "Test"},
    )

    # Cleanup regardless of assertion outcome
    _request_with_retry(client, "DELETE", f"/api/admin/employees/{employee_code}", headers=auth_headers)

    assert second.status_code == 409