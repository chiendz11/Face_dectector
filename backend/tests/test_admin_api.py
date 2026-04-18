from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.dependencies import get_current_user, get_employee_registry_service
from app.api.endpoints_admin import router as admin_router
from app.models.schemas import EmployeeCreate
from app.services.employee_registry import EmployeeRegistryService


def test_admin_employee_crud_flow(sqlite_session) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)
    client.app.dependency_overrides[get_employee_registry_service] = lambda: EmployeeRegistryService(sqlite_session)
    client.app.dependency_overrides[get_current_user] = lambda: "admin"

    create_response = client.post(
        "/api/admin/employees",
        json={
            "employee_code": " emp-100 ",
            "full_name": "Alice Nguyen",
            "department": "Operations",
        },
    )
    list_response = client.get("/api/admin/employees")
    delete_response = client.delete("/api/admin/employees/emp-100")

    client.app.dependency_overrides.clear()

    assert create_response.status_code == 201
    assert create_response.json()["employee_code"] == "EMP-100"
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert delete_response.status_code == 200
    assert delete_response.json() == {"employee_code": "EMP-100", "deleted": True}


def test_admin_create_employee_rejects_duplicate_code(sqlite_session) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)
    service = EmployeeRegistryService(sqlite_session)
    service.create_employee(
        employee=EmployeeCreate(
            employee_code="emp-101",
            full_name="Tran Van A",
            department="IT",
        )
    )
    client.app.dependency_overrides[get_employee_registry_service] = lambda: service
    client.app.dependency_overrides[get_current_user] = lambda: "admin"

    response = client.post(
        "/api/admin/employees",
        json={
            "employee_code": "EMP-101",
            "full_name": "Tran Van B",
            "department": "IT",
        },
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "employee EMP-101 already exists"
