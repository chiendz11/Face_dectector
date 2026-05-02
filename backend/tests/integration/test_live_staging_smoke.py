import pytest


pytestmark = pytest.mark.integration


def test_live_staging_critical_write_path(live_api) -> None:
    employee_code = live_api.make_employee_code("STG")
    filename = "staging-face.jpg"
    face_bytes = b"staging-integration-face-payload"

    created = live_api.create_employee(employee_code, "Staging Smoke", "Platform")
    assert created["employee_code"] == employee_code

    enroll_payload = live_api.enroll_face(employee_code, filename, face_bytes)
    assert enroll_payload["employee_code"] == employee_code
    assert enroll_payload["enrolled"] is True

    recognize_payload = live_api.recognize_face(filename, face_bytes, "main-gate-01")
    assert recognize_payload["status"] == "granted"
    assert recognize_payload["result"]["matched"] is True
    assert recognize_payload["result"]["employee_code"] == employee_code

    deleted = live_api.delete_employee(employee_code)
    assert deleted == {"employee_code": employee_code, "deleted": True}