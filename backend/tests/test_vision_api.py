import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("python_multipart")

from app.api.dependencies import get_recognition_service
from app.api.endpoints_vision import router as vision_router
from app.services.deepface_service import DeepFaceService
from app.services.minio_service import MinioService
from app.services.vector_search_service import VectorSearchService
from app.services.recognition_service import RecognitionService


def test_recognize_face_returns_granted_when_embedding_matches() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    deepface_service = DeepFaceService()
    vector_search_service = VectorSearchService(match_threshold=0.8)
    minio_service = MinioService()
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        minio_service=minio_service,
    )
    image_bytes = b"employee-vision-sample"
    vector_search_service.upsert_face_embedding(
        "emp-200",
        deepface_service.embed_face(image_bytes),
    )

    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        data={"device_name": "main-gate-01"},
        files={"file": ("face.jpg", image_bytes, "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "granted"
    assert payload["result"]["matched"] is True
    assert payload["result"]["employee_code"] == "EMP-200"


def test_recognize_face_returns_bad_request_for_empty_file() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    recognition_service = RecognitionService(
        deepface_service=DeepFaceService(),
        vector_search_service=VectorSearchService(),
        minio_service=MinioService(),
    )
    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        files={"file": ("face.jpg", b"", "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "image_bytes must not be empty"


def test_recognize_face_returns_rejected_when_no_match_found() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    recognition_service = RecognitionService(
        deepface_service=DeepFaceService(),
        vector_search_service=VectorSearchService(match_threshold=0.99),
        minio_service=MinioService(),
    )
    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        data={"device_name": "side-gate-01"},
        files={"file": ("unknown-face.jpg", b"unknown-face", "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "rejected"
    assert payload["result"]["matched"] is False
    assert payload["result"]["employee_code"] is None
    assert payload["result"]["confidence"] == 0.0


def test_recognize_face_without_device_name_still_returns_200() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    deepface_service = DeepFaceService()
    vector_search_service = VectorSearchService(match_threshold=0.8)
    image_bytes = b"employee-no-device-name"
    vector_search_service.upsert_face_embedding(
        "emp-300",
        deepface_service.embed_face(image_bytes),
    )
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        minio_service=MinioService(),
    )
    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        files={"file": ("face.jpg", image_bytes, "image/jpeg")},
        # device_name not sent
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "granted"
    assert payload["device_name"] is None


def test_recognize_face_granted_response_includes_snapshot_url() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    deepface_service = DeepFaceService()
    vector_search_service = VectorSearchService(match_threshold=0.8)
    minio_service = MinioService(
        bucket_name="snapshots",
        endpoint="minio:9000",
        public_endpoint="http://minio:9000",
    )
    image_bytes = b"employee-snapshot-test"
    vector_search_service.upsert_face_embedding(
        "emp-301",
        deepface_service.embed_face(image_bytes),
    )
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        minio_service=minio_service,
    )
    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        data={"device_name": "main-gate-03"},
        files={"file": ("face.jpg", image_bytes, "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["snapshot_url"] is not None
    assert "snapshots" in payload["result"]["snapshot_url"]
    assert "face.jpg" in payload["result"]["snapshot_url"]


def test_recognize_face_response_echoes_device_name() -> None:
    app = FastAPI()
    app.include_router(vision_router, prefix="/api")
    client = TestClient(app)
    recognition_service = RecognitionService(
        deepface_service=DeepFaceService(),
        vector_search_service=VectorSearchService(match_threshold=0.99),
        minio_service=MinioService(),
    )
    client.app.dependency_overrides[get_recognition_service] = lambda: recognition_service

    response = client.post(
        "/api/vision/recognize",
        data={"device_name": "checkpoint-alpha"},
        files={"file": ("face.jpg", b"unknown-face-data", "image/jpeg")},
    )

    client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["device_name"] == "checkpoint-alpha"
