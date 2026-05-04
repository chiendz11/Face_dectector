import pytest


pytestmark = pytest.mark.e2e


def test_live_sandbox_full_employee_flow(live_api) -> None:
    employee_code = live_api.make_employee_code("SBX")
    filename = "sandbox-face.jpg"
    face_bytes = b"sandbox-integration-face-payload"

    created = live_api.create_employee(employee_code, "Sandbox Smoke", "Platform")
    assert created["employee_code"] == employee_code

    employee_list = live_api.list_employees()
    assert any(item["employee_code"] == employee_code for item in employee_list["items"])

    enroll_payload = live_api.enroll_face(employee_code, filename, face_bytes)
    assert enroll_payload["employee_code"] == employee_code
    assert enroll_payload["enrolled"] is True

    recognize_payload = live_api.recognize_face(filename, face_bytes, "main-gate-01")
    assert recognize_payload["status"] == "granted"
    assert recognize_payload["result"]["matched"] is True
    assert recognize_payload["result"]["employee_code"] == employee_code

    live_api.assert_snapshot_exists("main-gate-01/sandbox-face.jpg")

    deleted = live_api.delete_employee(employee_code)
    assert deleted == {"employee_code": employee_code, "deleted": True}

    employee_list_after_delete = live_api.list_employees()
    assert all(item["employee_code"] != employee_code for item in employee_list_after_delete["items"])


def test_live_sandbox_enroll_unknown_employee_returns_404(client, auth_headers) -> None:
    response = client.post(
        "/api/admin/employees/DOES-NOT-EXIST-999/enroll",
        headers=auth_headers,
        files={"file": ("face.jpg", b"fake-face-bytes", "image/jpeg")},
    )

    assert response.status_code == 404


def test_live_sandbox_enroll_empty_file_returns_400(client, auth_headers, live_api) -> None:
    employee_code = live_api.make_employee_code("EMPTY")
    live_api.create_employee(employee_code, "Empty File Test", "Platform")

    try:
        response = client.post(
            f"/api/admin/employees/{employee_code}/enroll",
            headers=auth_headers,
            files={"file": ("face.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    finally:
        live_api.delete_employee(employee_code)


def test_live_sandbox_recognize_unknown_face_is_rejected(live_api) -> None:
    # Submit a face that has never been enrolled → should always be rejected.
    payload = live_api.recognize_face(
        "unknown.jpg",
        b"totally-unknown-face-payload-xyz-123",
        "test-gate",
    )

    assert payload["status"] == "rejected"
    assert payload["result"]["matched"] is False
    assert payload["result"]["employee_code"] is None