from __future__ import annotations

from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import urllib.error

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "resolve_registry_digest.py"
SPEC = spec_from_file_location("resolve_registry_digest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
resolve_registry_digest = module_from_spec(SPEC)
SPEC.loader.exec_module(resolve_registry_digest)


class FakeResponse:
    def __init__(self, *, headers: dict[str, str] | None = None, body: dict[str, str] | None = None) -> None:
        self.headers = headers or {}
        self._body = json.dumps(body or {}).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_parse_bearer_challenge_extracts_realm_service_and_scope() -> None:
    header = (
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",'
        'scope="repository:owner/image:pull"'
    )

    challenge = resolve_registry_digest.parse_bearer_challenge(header)

    assert challenge == {
        "realm": "https://ghcr.io/token",
        "service": "ghcr.io",
        "scope": "repository:owner/image:pull",
    }


def test_request_bearer_token_uses_query_params_and_extracts_token(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        recorded["url"] = request.full_url
        recorded["timeout"] = timeout
        recorded["authorization"] = request.get_header("Authorization")
        return FakeResponse(body={"token": "bearer-token"})

    monkeypatch.setattr(resolve_registry_digest.urllib.request, "urlopen", fake_urlopen)

    token = resolve_registry_digest.request_bearer_token(
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:owner/image:pull"',
        "ZW5jb2RlZA==",
        15,
    )

    assert token == "bearer-token"
    assert recorded == {
        "url": "https://ghcr.io/token?service=ghcr.io&scope=repository%3Aowner%2Fimage%3Apull",
        "timeout": 15,
        "authorization": "Basic ZW5jb2RlZA==",
    }


def test_resolve_digest_retries_transient_http_errors(monkeypatch) -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def fake_do_resolve(manifest_url: str, encoded_credentials: str, timeout: int) -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise urllib.error.HTTPError(manifest_url, 503, "Service Unavailable", {}, None)
        return "sha256:" + "a" * 64

    monkeypatch.setattr(resolve_registry_digest, "_do_resolve", fake_do_resolve)
    monkeypatch.setattr(resolve_registry_digest.time, "sleep", sleeps.append)

    digest = resolve_registry_digest.resolve_digest(
        "https://ghcr.io/v2/owner/image/manifests/latest",
        "encoded-credentials",
        timeout=12,
        max_retries=3,
    )

    assert digest == "sha256:" + "a" * 64
    assert attempts["count"] == 3
    assert sleeps == [2.0, 4.0]


def test_main_rejects_invalid_digest_format(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        resolve_registry_digest,
        "parse_args",
        lambda: Namespace(
            registry="https://ghcr.io",
            repository="owner/image",
            reference="latest",
            username="user",
            password="token",
            timeout=30,
            max_retries=3,
        ),
    )
    monkeypatch.setattr(resolve_registry_digest, "resolve_digest", lambda *args, **kwargs: "invalid-digest")

    exit_code = resolve_registry_digest.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "invalid digest format" in captured.err
    assert captured.out == ""