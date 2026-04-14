from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Face Detector Backend"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/face_detector"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://vector-db:6333"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "face-snapshots"
    model_name: str = "VGG-Face"
    model_version: str = "2026.04-baseline"
    match_threshold: float = 0.35

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
