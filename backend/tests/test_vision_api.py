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
