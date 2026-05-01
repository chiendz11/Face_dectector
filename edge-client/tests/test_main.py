import requests

import main as edge_main


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

    monkeypatch.setattr(edge_main.requests, "post", fake_post)

    level, message = edge_main.send_crops_to_backend(
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

    monkeypatch.setattr(edge_main.requests, "post", fake_post)

    level, message = edge_main.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "failed"
    assert message == "Verification failed. Please try again."


def test_send_crops_returns_error_when_request_fails(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(edge_main.requests, "post", fake_post)

    level, message = edge_main.send_crops_to_backend(
        [b"fake-face"],
        "http://localhost",
        "main-gate-01",
    )

    assert level == "error"
    assert "Backend request failed" in message
