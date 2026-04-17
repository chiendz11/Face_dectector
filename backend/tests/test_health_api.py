import pytest
from fastapi.testclient import TestClient

pytest.importorskip("python_multipart")

from app.main import app


def test_root_health_returns_service_metadata() -> None:
    client = TestClient(app)

    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "Face Detector Backend"
    assert payload["model_name"] == "VGG-Face"
    assert payload["model_version"] == "2026.04-baseline"
    assert payload["match_threshold"] == 0.35


def test_admin_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/admin/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "admin"}


def test_vision_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/vision/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "vision"}
