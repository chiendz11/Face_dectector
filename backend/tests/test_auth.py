from fastapi.testclient import TestClient

from app.main import app


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
