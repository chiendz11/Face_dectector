from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import AuthService


def test_login_returns_access_token() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert "access_token" in payload


def test_admin_routes_require_auth() -> None:
    client = TestClient(app)

    response = client.get("/api/admin/employees")

    assert response.status_code == 401


def test_login_rejects_wrong_password() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "totally-wrong-password"},
    )

    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_login_rejects_missing_password_field() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin"},
    )

    assert response.status_code == 422


def test_protected_route_with_invalid_token_returns_401() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/admin/employees",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_protected_route_with_expired_token_returns_401() -> None:
    auth_service = AuthService()
    expired_token = auth_service.create_access_token(
        subject="admin",
        expires_delta=timedelta(seconds=-1),
    )
    client = TestClient(app)

    response = client.get(
        "/api/admin/employees",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
