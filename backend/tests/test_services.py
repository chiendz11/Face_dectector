import pytest

from app.models.schemas import EmployeeCreate
from app.services.deepface_service import DeepFaceService
from app.services.employee_registry import EmployeeRegistryService
from app.services.minio_service import MinioService
from app.services.vector_search_service import VectorSearchService
from app.services.recognition_service import RecognitionService


def test_deepface_service_returns_deterministic_embedding() -> None:
    service = DeepFaceService()

    left = service.embed_face(b"employee-face")
    right = service.embed_face(b"employee-face")

    assert left == right
    assert len(left) == len(right)
    assert len(left) > 0


def test_deepface_service_rejects_empty_image_bytes() -> None:
    service = DeepFaceService()

    with pytest.raises(ValueError, match="image_bytes must not be empty"):
        service.embed_face(b"")


def test_vector_search_service_returns_best_match_above_threshold() -> None:
    service = VectorSearchService(match_threshold=0.8)
    embedding = [0.1, 0.2, 0.3]

    service.upsert_face_embedding(
        "emp-001",
        embedding,
        metadata={"full_name": "Alice Nguyen"},
    )

    result = service.search_similar_face(embedding)

    assert result["match"] == "EMP-001"
    assert result["score"] == 1.0
    assert result["metadata"] == {"full_name": "Alice Nguyen"}


def test_vector_search_service_returns_no_match_below_threshold() -> None:
    service = VectorSearchService(match_threshold=0.95)
    service.upsert_face_embedding("emp-004", [1.0, 0.0, 0.0])

    result = service.search_similar_face([0.0, 1.0, 0.0])

    assert result["match"] is None
    assert result["score"] == 0.0
    assert result["metadata"] is None


def test_minio_service_returns_http_snapshot_url() -> None:
    service = MinioService(bucket_name="snapshots", endpoint="minio.internal:9000")

    snapshot_url = service.upload_snapshot("main-gate/face.jpg", b"binary-image")

    assert snapshot_url == "http://minio.internal:9000/snapshots/main-gate/face.jpg"


def test_minio_service_rejects_empty_snapshot_payload() -> None:
    service = MinioService()

    with pytest.raises(ValueError, match="image_bytes must not be empty"):
        service.upload_snapshot("face.jpg", b"")


def test_employee_registry_service_creates_and_lists_employees(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)

    created = service.create_employee(
        employee=EmployeeCreate(
            employee_code=" emp-002 ",
            full_name=" Bob Tran ",
            department="Engineering",
        )
    )

    assert created.employee_code == "EMP-002"
    assert created.full_name == "Bob Tran"
    assert service.list_employees() == [created]


def test_employee_registry_service_rejects_blank_full_name(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)

    with pytest.raises(ValueError, match="full_name must not be empty"):
        service.create_employee(
            employee=EmployeeCreate(
                employee_code="emp-005",
                full_name="   ",
                department="Engineering",
            )
        )


def test_recognition_service_returns_granted_for_known_face() -> None:
    deepface_service = DeepFaceService()
    qdrant_service = VectorSearchService(match_threshold=0.8)
    minio_service = MinioService()
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        qdrant_service=qdrant_service,
        minio_service=minio_service,
    )
    image_bytes = b"known-employee"
    embedding = deepface_service.embed_face(image_bytes)

    qdrant_service.upsert_face_embedding("emp-003", embedding)

    response = recognition_service.recognize_face(
        filename="face.jpg",
        image_bytes=image_bytes,
        device_name="main-gate-01",
    )

    assert response.status == "granted"
    assert response.result.matched is True
    assert response.result.employee_code == "EMP-003"
    assert response.result.confidence == 1.0
    assert response.result.snapshot_url.endswith("/face-snapshots/main-gate-01/face.jpg")


def test_recognition_service_returns_rejected_for_unknown_face() -> None:
    recognition_service = RecognitionService(
        deepface_service=DeepFaceService(),
        qdrant_service=VectorSearchService(match_threshold=0.99),
        minio_service=MinioService(),
    )

    response = recognition_service.recognize_face(
        filename="unknown-face.jpg",
        image_bytes=b"unmatched-face",
        device_name="side-gate-01",
    )

    assert response.status == "rejected"
    assert response.result.matched is False
    assert response.result.employee_code is None
    assert response.result.confidence == 0.0
