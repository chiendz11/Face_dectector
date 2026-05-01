from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.dependencies import (
    get_current_user,
    get_deepface_service,
    get_employee_registry_service,
    get_vector_search_service,
)
from app.api.endpoints_admin import router as admin_router
from app.core.config import settings
from app.models.schemas import EmployeeCreate
from app.services.employee_registry import EmployeeRegistryService
from app.services.vector_search_service import VectorSearchService


class FakeDeepFaceService:
    def embed_face(self, image_bytes: bytes) -> list[float]:
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")
        return [0.25] * settings.embedding_dimensions


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


def test_admin_enroll_face_upserts_embedding(sqlite_session) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)

    employee_registry = EmployeeRegistryService(sqlite_session)
    vector_search_service = VectorSearchService(
        db=None,
        read_db=None,
        embedding_dimensions=settings.embedding_dimensions,
    )

    client.app.dependency_overrides[get_employee_registry_service] = lambda: employee_registry
    client.app.dependency_overrides[get_vector_search_service] = lambda: vector_search_service
    client.app.dependency_overrides[get_deepface_service] = lambda: FakeDeepFaceService()
    client.app.dependency_overrides[get_current_user] = lambda: "admin"

    create_response = client.post(
        "/api/admin/employees",
        json={
            "employee_code": "emp-102",
            "full_name": "Bui Minh",
            "department": "Security",
        },
    )
    enroll_response = client.post(
        "/api/admin/employees/EMP-102/enroll",
        files={"file": ("face.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    result = vector_search_service.search_similar_face([0.25] * settings.embedding_dimensions)

    client.app.dependency_overrides.clear()

    assert create_response.status_code == 201
    assert enroll_response.status_code == 200
    assert enroll_response.json()["employee_code"] == "EMP-102"
    assert enroll_response.json()["enrolled"] is True
    assert enroll_response.json()["embedding_dimensions"] == settings.embedding_dimensions
    assert result["match"] == "EMP-102"
    assert result["metadata"] == {"source": "admin-enroll", "filename": "face.jpg"}


def test_admin_enroll_face_returns_not_found_for_unknown_employee(sqlite_session) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)

    employee_registry = EmployeeRegistryService(sqlite_session)
    vector_search_service = VectorSearchService(
        db=None,
        read_db=None,
        embedding_dimensions=settings.embedding_dimensions,
    )

    client.app.dependency_overrides[get_employee_registry_service] = lambda: employee_registry
    client.app.dependency_overrides[get_vector_search_service] = lambda: vector_search_service
    client.app.dependency_overrides[get_deepface_service] = lambda: FakeDeepFaceService()
    client.app.dependency_overrides[get_current_user] = lambda: "admin"

    response = client.post(
        "/api/admin/employees/EMP-404/enroll",
        files={"file": ("face.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "employee EMP-404 was not found"


def test_admin_enroll_face_rejects_empty_file(sqlite_session) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)

    employee_registry = EmployeeRegistryService(sqlite_session)
    employee_registry.create_employee(
        EmployeeCreate(employee_code="emp-103", full_name="Nguyen Thi C", department="QA")
    )
    vector_search_service = VectorSearchService(db=None, read_db=None, embedding_dimensions=settings.embedding_dimensions)

    client.app.dependency_overrides[get_employee_registry_service] = lambda: employee_registry
    client.app.dependency_overrides[get_vector_search_service] = lambda: vector_search_service
    client.app.dependency_overrides[get_deepface_service] = lambda: FakeDeepFaceService()
    client.app.dependency_overrides[get_current_user] = lambda: "admin"

    response = client.post(
        "/api/admin/employees/EMP-103/enroll",
        files={"file": ("face.jpg", b"", "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "image file must not be empty"


def test_admin_enroll_face_upserts_on_second_enroll(sqlite_session) -> None:
    """Enrolling the same employee twice must overwrite the old embedding (upsert)."""
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app)

    employee_registry = EmployeeRegistryService(sqlite_session)
    employee_registry.create_employee(
        EmployeeCreate(employee_code="emp-104", full_name="Pham Van D", department="Ops")
    )

    class FirstImageService:
        def embed_face(self, image_bytes: bytes) -> list[float]:
            return [0.1] * settings.embedding_dimensions

    class SecondImageService:
        def embed_face(self, image_bytes: bytes) -> list[float]:
            return [0.9] * settings.embedding_dimensions

    vector_search_service = VectorSearchService(db=None, read_db=None, embedding_dimensions=settings.embedding_dimensions)

    def make_client(deepface_service):
        app2 = FastAPI()
        app2.include_router(admin_router, prefix="/api")
        c = TestClient(app2)
        c.app.dependency_overrides[get_employee_registry_service] = lambda: employee_registry
        c.app.dependency_overrides[get_vector_search_service] = lambda: vector_search_service
        c.app.dependency_overrides[get_deepface_service] = lambda: deepface_service
        c.app.dependency_overrides[get_current_user] = lambda: "admin"
        return c

    c1 = make_client(FirstImageService())
    r1 = c1.post("/api/admin/employees/EMP-104/enroll", files={"file": ("face.jpg", b"first", "image/jpeg")})
    c1.app.dependency_overrides.clear()

    c2 = make_client(SecondImageService())
    r2 = c2.post("/api/admin/employees/EMP-104/enroll", files={"file": ("face.jpg", b"second", "image/jpeg")})
    c2.app.dependency_overrides.clear()

    # After second enroll the embedding must match [0.9, ...], not [0.1, ...]
    result = vector_search_service.search_similar_face([0.9] * settings.embedding_dimensions)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert result["match"] == "EMP-104"
    assert result["score"] > 0.99


def test_admin_enroll_face_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    # No dependency override for get_current_user → real OAuth2 scheme → 401
    response = client.post(
        "/api/admin/employees/EMP-999/enroll",
        files={"file": ("face.jpg", b"data", "image/jpeg")},
    )

    assert response.status_code == 401
