from pydantic_settings import BaseSettings, SettingsConfigDict


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
    minio_bucket: str = "face-snapshots"
    aws_s3_bucket: str | None = None
    aws_s3_region: str | None = None
    embedding_dimensions: int = 16
    model_name: str = "VGG-Face"
    model_version: str = "2026.04-baseline"
    match_threshold: float = 0.35
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


settings = Settings()
