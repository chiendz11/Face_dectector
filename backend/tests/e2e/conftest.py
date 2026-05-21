import os
import time
from dataclasses import dataclass
from pathlib import Path

import boto3
import httpx
import pytest


def _base_url() -> str:
    return os.getenv("FACE_DETECTOR_BASE_URL", "http://localhost")


def _admin_username() -> str:
    return os.getenv("FACE_DETECTOR_ADMIN_USERNAME", "admin")


def _admin_password() -> str:
    return os.getenv("FACE_DETECTOR_ADMIN_PASSWORD", "local-admin-password")


def _request_with_rate_limit_retry(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    attempts: int = 6,
    default_delay_seconds: float = 0.5,
    **kwargs,
) -> httpx.Response:
    last_response: httpx.Response | None = None
    for attempt in range(attempts):
        response = client.request(method, path, **kwargs)
        last_response = response
        if response.status_code != 429:
            return response

        if attempt == attempts - 1:
            break

        retry_after = response.headers.get("Retry-After")
        try:
            delay_seconds = float(retry_after) if retry_after else default_delay_seconds
        except ValueError:
            delay_seconds = default_delay_seconds
        time.sleep(max(delay_seconds, default_delay_seconds))

    assert last_response is not None
    return last_response


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    timeout = float(os.getenv("FACE_DETECTOR_TIMEOUT_SECONDS", "30"))
    with httpx.Client(base_url=_base_url(), timeout=timeout) as live_client:
        yield live_client


@pytest.fixture(scope="session")
def auth_headers(client: httpx.Client) -> dict[str, str]:
    response = _request_with_rate_limit_retry(
        client,
        "POST",
        "/api/auth/login",
        json={"username": _admin_username(), "password": _admin_password()},
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@dataclass
class LiveApiSession:
    client: httpx.Client
    auth_headers: dict[str, str]

    def backend_health(self) -> dict:
        response = _request_with_rate_limit_retry(self.client, "GET", "/health")
        response.raise_for_status()
        return response.json()

    def face_sample(self, *, env_var: str, synthetic_bytes: bytes) -> bytes:
        sample_path = os.getenv(env_var)
        if sample_path:
            return Path(sample_path).read_bytes()

        provider = str(self.backend_health().get("embedding_provider", "")).strip().lower()
        if provider == "hash":
            return synthetic_bytes

        pytest.skip(
            f"{env_var} is required for live face smoke when embedding_provider={provider or 'unknown'}"
        )

    def make_employee_code(self, prefix: str) -> str:
        return f"{prefix}-{int(time.time())}"

    def create_employee(self, employee_code: str, full_name: str, department: str) -> dict:
        response = _request_with_rate_limit_retry(
            self.client,
            "POST",
            "/api/admin/employees",
            headers=self.auth_headers,
            json={
                "employee_code": employee_code,
                "full_name": full_name,
                "department": department,
            },
        )
        response.raise_for_status()
        return response.json()

    def list_employees(self) -> dict:
        response = _request_with_rate_limit_retry(
            self.client,
            "GET",
            "/api/admin/employees",
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()

    def enroll_face(self, employee_code: str, filename: str, face_bytes: bytes) -> dict:
        response = _request_with_rate_limit_retry(
            self.client,
            "POST",
            f"/api/admin/employees/{employee_code}/enroll",
            headers=self.auth_headers,
            files={"file": (filename, face_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()

    def recognize_face(self, filename: str, face_bytes: bytes, device_name: str) -> dict:
        response = _request_with_rate_limit_retry(
            self.client,
            "POST",
            "/api/vision/recognize",
            data={"device_name": device_name},
            files={"file": (filename, face_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()

    def delete_employee(self, employee_code: str) -> dict:
        response = _request_with_rate_limit_retry(
            self.client,
            "DELETE",
            f"/api/admin/employees/{employee_code}",
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()

    def assert_snapshot_exists(self, object_key: str) -> None:
        if os.getenv("FACE_DETECTOR_OBJECT_STORE_MODE") != "local-minio":
            return

        minio_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("FACE_DETECTOR_MINIO_ENDPOINT", "http://localhost:9000"),
            aws_access_key_id=os.getenv("FACE_DETECTOR_MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("FACE_DETECTOR_MINIO_SECRET_KEY", "local-dev-minio"),
            region_name=os.getenv("FACE_DETECTOR_MINIO_REGION", "us-east-1"),
        )
        minio_client.head_object(
            Bucket=os.getenv("FACE_DETECTOR_MINIO_BUCKET", "face-snapshots"),
            Key=object_key,
        )


@pytest.fixture(scope="session")
def live_api(client: httpx.Client, auth_headers: dict[str, str]) -> LiveApiSession:
    return LiveApiSession(client=client, auth_headers=auth_headers)
