import pytest
from fastapi.testclient import TestClient

pytest.importorskip("python_multipart")

from app.main import app
from app.core.config import settings


def test_root_health_returns_service_metadata() -> None:
    client = TestClient(app)

    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "Face Detector Backend"
    assert payload["embedding_provider"] == settings.embedding_provider
    assert payload["model_name"] == settings.model_name
    assert payload["model_version"] == settings.model_version
    assert payload["embedding_dimensions"] == settings.embedding_dimensions
    assert payload["match_threshold"] == settings.match_threshold


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
