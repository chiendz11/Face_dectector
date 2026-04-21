from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db, get_read_db
from app.services.auth_service import AuthService
from app.services.deepface_service import DeepFaceService
from app.services.employee_registry import EmployeeRegistryService
from app.services.minio_service import MinioService
from app.services.vector_search_service import VectorSearchService
from app.services.recognition_service import RecognitionService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


def get_employee_registry_service(db: Session = Depends(get_db)) -> EmployeeRegistryService:
    return EmployeeRegistryService(db=db)


@lru_cache
def get_deepface_service() -> DeepFaceService:
    return DeepFaceService()


def get_vector_search_service(
    db: Session = Depends(get_db),
    read_db: Session = Depends(get_read_db),
) -> VectorSearchService:
    return VectorSearchService(
        db=db,
        read_db=read_db,
        match_threshold=settings.match_threshold,
        embedding_dimensions=settings.embedding_dimensions,
    )


@lru_cache
def get_minio_service() -> MinioService:
    return MinioService(
        bucket_name=settings.minio_bucket,
        endpoint=settings.minio_endpoint,
        public_endpoint=settings.minio_public_endpoint,
        aws_s3_bucket=settings.aws_s3_bucket,
        aws_s3_region=settings.aws_s3_region,
        s3_retry_attempts=settings.s3_retry_attempts,
        s3_retry_backoff_seconds=settings.s3_retry_backoff_seconds,
        s3_circuit_failure_threshold=settings.s3_circuit_failure_threshold,
        s3_circuit_recovery_seconds=settings.s3_circuit_recovery_seconds,
    )


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService()


def get_recognition_service(
    deepface_service: DeepFaceService = Depends(get_deepface_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
    minio_service: MinioService = Depends(get_minio_service),
) -> RecognitionService:
    return RecognitionService(
        db=vector_search_service.db,
        deepface_service=deepface_service,
        qdrant_service=vector_search_service,
        minio_service=minio_service,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> str:
    try:
        return auth_service.verify_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
