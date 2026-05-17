import pytest

from app.models.schemas import EmployeeCreate
from app.services import minio_service as minio_module
from app.services.deepface_service import DeepFaceService
from app.services.employee_registry import EmployeeRegistryService
from app.services.minio_service import MinioService
from app.services.vector_search_service import VectorSearchService
from app.services.recognition_service import RecognitionService


def make_hash_embedding_service(embedding_dimensions: int = 16) -> DeepFaceService:
    return DeepFaceService(provider="hash", embedding_dimensions=embedding_dimensions)


def test_deepface_service_returns_deterministic_embedding() -> None:
    service = make_hash_embedding_service()

    left = service.embed_face(b"employee-face")
    right = service.embed_face(b"employee-face")

    assert left == right
    assert len(left) == len(right)
    assert len(left) > 0


def test_deepface_service_rejects_empty_image_bytes() -> None:
    service = make_hash_embedding_service()

    with pytest.raises(ValueError, match="image_bytes must not be empty"):
        service.embed_face(b"")


def test_vector_search_service_returns_best_match_above_threshold() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)
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
    service = VectorSearchService(match_threshold=0.95, embedding_dimensions=3)
    service.upsert_face_embedding("emp-004", [1.0, 0.0, 0.0])

    result = service.search_similar_face([0.0, 1.0, 0.0])

    assert result["match"] is None
    assert result["score"] == 0.0
    assert result["metadata"] is None


def test_vector_search_integration_enroll_then_search_match() -> None:
    vector_search_service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)
    enrolled_embedding = [0.5, 0.5, 0.707106]

    vector_search_service.upsert_face_embedding(
        "emp-010",
        enrolled_embedding,
        metadata={"source": "admin-enroll"},
    )

    result = vector_search_service.search_similar_face([0.5, 0.5, 0.707106])

    assert result["match"] == "EMP-010"
    assert result["score"] == 1.0
    assert result["metadata"] == {"source": "admin-enroll"}


def test_minio_service_returns_http_snapshot_url() -> None:
    service = MinioService(bucket_name="snapshots", endpoint="minio.internal:9000", public_endpoint="http://minio.internal:9000")

    snapshot_url = service.upload_snapshot("main-gate/face.jpg", b"binary-image")

    assert snapshot_url == "http://minio.internal:9000/snapshots/main-gate/face.jpg"


def test_minio_service_uploads_to_local_s3_when_enabled(monkeypatch) -> None:
    uploaded = {}
    state = {"head_calls": 0, "create_bucket_calls": 0}

    class FakeLocalS3Client:
        def head_bucket(self, **kwargs) -> None:
            state["head_calls"] += 1
            raise RuntimeError("bucket missing")

        def create_bucket(self, **kwargs) -> None:
            state["create_bucket_calls"] += 1
            uploaded["bucket"] = kwargs["Bucket"]

        def put_object(self, **kwargs) -> None:
            uploaded.update(kwargs)

    class FakeBoto3:
        @staticmethod
        def client(service_name: str, **kwargs):
            assert service_name == "s3"
            assert kwargs["endpoint_url"] == "http://minio.internal:9000"
            assert kwargs["aws_access_key_id"] == "minioadmin"
            assert kwargs["aws_secret_access_key"] == "minio-secret"
            return FakeLocalS3Client()

    monkeypatch.setattr(minio_module, "boto3", FakeBoto3())
    service = MinioService(
        bucket_name="snapshots",
        endpoint="minio.internal:9000",
        public_endpoint="http://minio.public:9000",
        access_key="minioadmin",
        secret_key="minio-secret",
        use_s3_api=True,
    )

    snapshot_url = service.upload_snapshot("main-gate/face.jpg", b"binary-image")

    assert snapshot_url == "http://minio.public:9000/snapshots/main-gate/face.jpg"
    assert uploaded["Bucket"] == "snapshots"
    assert uploaded["Key"] == "main-gate/face.jpg"
    assert state == {"head_calls": 1, "create_bucket_calls": 1}


def test_minio_service_returns_s3_snapshot_url_when_bucket_configured(monkeypatch) -> None:
    uploaded = {}
    presigned = {}

    class FakeS3Client:
        def put_object(self, **kwargs) -> None:
            uploaded.update(kwargs)

        def generate_presigned_url(self, client_method: str, Params: dict[str, str], ExpiresIn: int) -> str:
            presigned["client_method"] = client_method
            presigned["params"] = Params
            presigned["expires_in"] = ExpiresIn
            return "https://signed.example.com/main-gate/face.jpg?signature=test"

    class FakeBoto3:
        @staticmethod
        def client(service_name: str, region_name: str | None = None) -> FakeS3Client:
            assert service_name == "s3"
            assert region_name == "ap-southeast-1"
            return FakeS3Client()

    monkeypatch.setattr(minio_module, "boto3", FakeBoto3())
    service = MinioService(
        aws_s3_bucket="face-detector-staging-snapshots",
        aws_s3_region="ap-southeast-1",
        aws_s3_presigned_url_expire_seconds=900,
        public_endpoint="",
    )

    snapshot_url = service.upload_snapshot("main-gate/face.jpg", b"binary-image")

    assert snapshot_url == "https://signed.example.com/main-gate/face.jpg?signature=test"
    assert uploaded["Bucket"] == "face-detector-staging-snapshots"
    assert uploaded["Key"] == "main-gate/face.jpg"
    assert presigned == {
        "client_method": "get_object",
        "params": {
            "Bucket": "face-detector-staging-snapshots",
            "Key": "main-gate/face.jpg",
        },
        "expires_in": 900,
    }


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
    deepface_service = make_hash_embedding_service()
    vector_search_service = VectorSearchService(match_threshold=0.8)
    minio_service = MinioService()
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        minio_service=minio_service,
    )
    image_bytes = b"known-employee"
    embedding = deepface_service.embed_face(image_bytes)

    vector_search_service.upsert_face_embedding("emp-003", embedding)

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
        deepface_service=make_hash_embedding_service(),
        vector_search_service=VectorSearchService(match_threshold=0.99),
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


# ---------------------------------------------------------------------------
# VectorSearchService — extended coverage
# ---------------------------------------------------------------------------

def test_vector_search_returns_nearest_neighbor_among_multiple_employees() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)
    # emp-020 points toward [1, 0, 0]; emp-021 points toward [0, 1, 0]
    service.upsert_face_embedding("emp-020", [1.0, 0.0, 0.0])
    service.upsert_face_embedding("emp-021", [0.0, 1.0, 0.0])

    # Query is close to emp-020
    result = service.search_similar_face([0.98, 0.02, 0.0])

    assert result["match"] == "EMP-020"
    assert result["score"] > 0.99


def test_vector_search_upsert_overwrites_existing_embedding() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)
    service.upsert_face_embedding("emp-022", [1.0, 0.0, 0.0])
    # Overwrite with orthogonal embedding
    service.upsert_face_embedding("emp-022", [0.0, 1.0, 0.0])

    # Old vector should no longer match
    old_result = service.search_similar_face([1.0, 0.0, 0.0])
    # New vector should match
    new_result = service.search_similar_face([0.0, 1.0, 0.0])

    assert old_result["match"] is None
    assert new_result["match"] == "EMP-022"
    assert new_result["score"] == 1.0


def test_vector_search_rejects_empty_employee_code() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)

    with pytest.raises(ValueError, match="employee_code must not be empty"):
        service.upsert_face_embedding("   ", [0.1, 0.2, 0.3])


def test_vector_search_returns_no_match_when_store_is_empty() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)

    result = service.search_similar_face([0.1, 0.2, 0.3])

    assert result["match"] is None
    assert result["score"] == 0.0
    assert result["metadata"] is None


def test_vector_search_rejects_wrong_dimension_embedding() -> None:
    service = VectorSearchService(match_threshold=0.8, embedding_dimensions=3)

    with pytest.raises(ValueError, match="embedding dimensions must match"):
        service.upsert_face_embedding("emp-023", [0.1, 0.2])  # 2 dims, expects 3


# ---------------------------------------------------------------------------
# EmployeeRegistryService — extended coverage
# ---------------------------------------------------------------------------

def test_employee_registry_returns_none_for_unknown_employee(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)

    result = service.get_employee("DOES-NOT-EXIST")

    assert result is None


def test_employee_registry_delete_removes_employee(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)
    service.create_employee(
        EmployeeCreate(employee_code="emp-030", full_name="To Be Deleted", department="HR")
    )

    deleted = service.delete_employee("emp-030")

    assert deleted is not None
    assert deleted.employee_code == "EMP-030"
    assert service.get_employee("EMP-030") is None
    assert service.list_employees() == []


def test_employee_registry_rejects_blank_employee_code(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)

    with pytest.raises(ValueError, match="employee_code must not be empty"):
        service.create_employee(
            EmployeeCreate(employee_code="  ", full_name="Ghost", department="IT")
        )


def test_employee_registry_lists_multiple_employees_in_sorted_order(sqlite_session) -> None:
    service = EmployeeRegistryService(sqlite_session)
    service.create_employee(EmployeeCreate(employee_code="emp-z99", full_name="Zara", department="X"))
    service.create_employee(EmployeeCreate(employee_code="emp-a01", full_name="Adam", department="X"))
    service.create_employee(EmployeeCreate(employee_code="emp-m50", full_name="Minh", department="X"))

    result = service.list_employees()
    codes = [e.employee_code for e in result]

    assert codes == sorted(codes)


# ---------------------------------------------------------------------------
# MinioService — extended coverage
# ---------------------------------------------------------------------------

def test_minio_service_bucket_already_exists_skips_create(monkeypatch) -> None:
    uploaded = {}
    state = {"head_calls": 0, "create_bucket_calls": 0}

    class FakeLocalS3BucketExists:
        def head_bucket(self, **kwargs) -> None:
            state["head_calls"] += 1  # succeeds — no exception → bucket exists

        def create_bucket(self, **kwargs) -> None:  # must NOT be called
            state["create_bucket_calls"] += 1

        def put_object(self, **kwargs) -> None:
            uploaded.update(kwargs)

    class FakeBoto3Exists:
        @staticmethod
        def client(service_name: str, **kwargs):
            return FakeLocalS3BucketExists()

    monkeypatch.setattr(minio_module, "boto3", FakeBoto3Exists())
    service = MinioService(
        bucket_name="snapshots",
        endpoint="minio.internal:9000",
        public_endpoint="http://minio.internal:9000",
        access_key="minioadmin",
        secret_key="minio-secret",
        use_s3_api=True,
    )

    service.upload_snapshot("gate/face.jpg", b"image-data")

    assert state["head_calls"] == 1
    assert state["create_bucket_calls"] == 0
    assert uploaded["Key"] == "gate/face.jpg"


# ---------------------------------------------------------------------------
# RecognitionService — extended coverage
# ---------------------------------------------------------------------------

def test_recognition_service_includes_snapshot_url_in_response() -> None:
    deepface_service = make_hash_embedding_service()
    vector_search_service = VectorSearchService(match_threshold=0.8)
    minio_service = MinioService(
        bucket_name="snapshots",
        endpoint="minio:9000",
        public_endpoint="http://minio:9000",
    )
    recognition_service = RecognitionService(
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        minio_service=minio_service,
    )
    image_bytes = b"known-face-snapshot"
    vector_search_service.upsert_face_embedding("emp-040", deepface_service.embed_face(image_bytes))

    response = recognition_service.recognize_face(
        filename="face.jpg",
        image_bytes=image_bytes,
        device_name="main-gate-02",
    )

    assert response.status == "granted"
    assert response.result.snapshot_url is not None
    assert "snapshots" in response.result.snapshot_url
    assert "face.jpg" in response.result.snapshot_url


def test_recognition_service_with_no_device_name_uses_fallback() -> None:
    recognition_service = RecognitionService(
        deepface_service=make_hash_embedding_service(),
        vector_search_service=VectorSearchService(match_threshold=0.99),
        minio_service=MinioService(),
    )

    response = recognition_service.recognize_face(
        filename="face.jpg",
        image_bytes=b"some-face-bytes",
        device_name=None,
    )

    assert response.device_name is None
    assert response.result.snapshot_url is not None


# ---------------------------------------------------------------------------
# DeepFaceService — extended coverage
# ---------------------------------------------------------------------------

def test_deepface_service_returns_different_embeddings_for_different_inputs() -> None:
    service = make_hash_embedding_service()

    embedding_a = service.embed_face(b"face-of-person-a")
    embedding_b = service.embed_face(b"face-of-person-b")

    assert embedding_a != embedding_b


def test_deepface_provider_rejects_known_model_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="Facenet512 returns 512 dimensions"):
        DeepFaceService(provider="deepface", model_name="Facenet512", embedding_dimensions=16)


def test_deepface_provider_fails_closed_when_dependency_missing(monkeypatch) -> None:
    from app.services import deepface_service as deepface_module

    monkeypatch.setattr(deepface_module, "DeepFace", None)
    service = DeepFaceService(provider="deepface", model_name="Facenet512", embedding_dimensions=512)

    with pytest.raises(RuntimeError, match="DeepFace embedding failed"):
        service.embed_face(b"image-bytes")
