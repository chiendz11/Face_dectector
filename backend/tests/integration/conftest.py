import os
import time
from dataclasses import dataclass

import boto3
import httpx
import pytest


def _base_url() -> str:
    return os.getenv("FACE_DETECTOR_BASE_URL", "http://localhost")


def _admin_username() -> str:
    return os.getenv("FACE_DETECTOR_ADMIN_USERNAME", "admin")


def _admin_password() -> str:
    return os.getenv("FACE_DETECTOR_ADMIN_PASSWORD", "local-admin-password")


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    timeout = float(os.getenv("FACE_DETECTOR_TIMEOUT_SECONDS", "30"))
    with httpx.Client(base_url=_base_url(), timeout=timeout) as live_client:
        yield live_client


@pytest.fixture(scope="session")
def auth_headers(client: httpx.Client) -> dict[str, str]:
    response = client.post(
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

    def make_employee_code(self, prefix: str) -> str:
        return f"{prefix}-{int(time.time())}"

    def create_employee(self, employee_code: str, full_name: str, department: str) -> dict:
        response = self.client.post(
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
        response = self.client.get("/api/admin/employees", headers=self.auth_headers)
        response.raise_for_status()
        return response.json()

    def enroll_face(self, employee_code: str, filename: str, face_bytes: bytes) -> dict:
        response = self.client.post(
            f"/api/admin/employees/{employee_code}/enroll",
            headers=self.auth_headers,
            files={"file": (filename, face_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()

    def recognize_face(self, filename: str, face_bytes: bytes, device_name: str) -> dict:
        response = self.client.post(
            "/api/vision/recognize",
            data={"device_name": device_name},
            files={"file": (filename, face_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()

    def delete_employee(self, employee_code: str) -> dict:
        response = self.client.delete(
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