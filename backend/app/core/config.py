from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MODEL_EMBEDDING_DIMENSIONS = {
    "VGG-Face": 4096,
    "Facenet": 128,
    "Facenet512": 512,
    "OpenFace": 128,
    "DeepFace": 4096,
    "DeepID": 160,
    "Dlib": 128,
    "ArcFace": 512,
    "SFace": 128,
    "GhostFaceNet": 512,
    "Buffalo_L": 512,
}


class Settings(BaseSettings):
    app_name: str = "Face Detector Backend"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/face_detector"
    database_replica_urls: str | None = None
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_use_s3_api: bool = False
    minio_bucket: str = "face-snapshots"
    aws_s3_bucket: str | None = None
    aws_s3_region: str | None = None
    aws_s3_presigned_url_expire_seconds: int = 3600
    embedding_provider: str = "deepface"
    embedding_dimensions: int = 512
    model_name: str = "Facenet512"
    model_version: str = "2026.05-deepface-facenet512"
    deepface_detector_backend: str = "opencv"
    deepface_align: bool = True
    deepface_enforce_detection: bool = False
    embedding_allow_hash_fallback: bool = False
    match_threshold: float = 0.55
    enrollment_min_samples: int = 3
    enrollment_max_samples: int = 10
    enrollment_session_ttl_minutes: int = 10
    dedupe_window_seconds: int = 30
    db_retry_attempts: int = 3
    db_retry_backoff_seconds: float = 0.5
    db_circuit_failure_threshold: int = 5
    db_circuit_recovery_seconds: int = 30
    s3_retry_attempts: int = 3
    s3_retry_backoff_seconds: float = 1.0
    s3_circuit_failure_threshold: int = 5
    s3_circuit_recovery_seconds: int = 30
    sqlalchemy_pool_size: int = 10
    sqlalchemy_max_overflow: int = 20
    sqlalchemy_pool_recycle_seconds: int = 1800
    jwt_secret_key: str = "development-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    admin_username: str = "admin"
    admin_password: str = "admin"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    @model_validator(mode="after")
    def normalize_embedding_dimensions(self) -> "Settings":
        if self.embedding_provider.strip().lower() != "deepface":
            return self

        expected_dimensions = MODEL_EMBEDDING_DIMENSIONS.get(self.model_name)
        if expected_dimensions is not None:
            self.embedding_dimensions = expected_dimensions
        return self


settings = Settings()
