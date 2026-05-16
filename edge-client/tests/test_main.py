import requests

import edge_client.app as edge_app
from edge_client.clients import backend
from edge_client.config import parse_bool


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status code: {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_send_crops_returns_success_when_granted(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "status": "granted",
                "result": {"employee_code": "EMP-001"},
            }
        )

    monkeypatch.setattr(backend.requests, "post", fake_post)

    level, message = backend.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "success"
    assert message == "Verification success: EMP-001"


def test_send_crops_returns_failed_when_rejected(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "status": "rejected",
                "result": {"employee_code": None},
            }
        )

    monkeypatch.setattr(backend.requests, "post", fake_post)

    level, message = backend.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "failed"
    assert message == "Verification failed. Please try again."


def test_send_crops_returns_error_when_request_fails(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(backend.requests, "post", fake_post)

    level, message = backend.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "error"
    assert "Backend unavailable" in message


def test_send_crops_returns_error_for_backend_500(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "status": "error",
                "result": {},
            },
            status_code=500,
        )

    monkeypatch.setattr(backend.requests, "post", fake_post)

    level, message = backend.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "error"
    assert message == "Backend error 500. Please retry or use manual check."


def test_send_crops_uses_configured_timeout(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return DummyResponse(
            {
                "status": "granted",
                "result": {"employee_code": "EMP-001"},
            }
        )

    monkeypatch.setattr(backend.requests, "post", fake_post)

    backend.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
        timeout_seconds=0.25,
    )

    assert captured["timeout"] == 0.25


def test_parse_bool_defaults_when_missing():
    assert parse_bool(None, default=True) is True
    assert parse_bool(None, default=False) is False


def test_parse_bool_accepts_enabled_values():
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("on") is True
    assert parse_bool("false") is False


def test_version_at_least_compares_major_minor_patch():
    assert edge_app._version_at_least("1.0.0", (0, 48, 0)) is True
    assert edge_app._version_at_least("0.48.0", (0, 48, 0)) is True
    assert edge_app._version_at_least("0.47.3", (0, 48, 0)) is False
