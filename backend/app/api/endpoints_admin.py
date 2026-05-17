from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import (
    get_current_user,
    get_deepface_service,
    get_employee_registry_service,
    get_vector_search_service,
)
from app.core.config import settings
from app.models.schemas import (
    EmployeeCreate,
    EmployeeDeleteResponse,
    EmployeeFaceEnrollResponse,
    EmployeeFaceEnrollSamplesResponse,
    EmployeeListResponse,
    EmployeeRecord,
)
from app.services.deepface_service import DeepFaceService
from app.services.employee_registry import EmployeeRegistryService
from app.services.vector_search_service import VectorSearchService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health() -> dict:
    return {"status": "ok", "scope": "admin"}


@router.get("/employees", response_model=EmployeeListResponse)
def list_employees(
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
) -> EmployeeListResponse:
    employees = employee_registry.list_employees()
    return EmployeeListResponse(items=employees, total=len(employees))


@router.post(
    "/employees",
    response_model=EmployeeRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    employee: EmployeeCreate,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
) -> EmployeeRecord:
    try:
        return employee_registry.create_employee(employee)
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "already exists" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.delete(
    "/employees/{employee_code}",
    response_model=EmployeeDeleteResponse,
)
def delete_employee(
    employee_code: str,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
) -> EmployeeDeleteResponse:
    try:
        deleted_employee = employee_registry.delete_employee(employee_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if deleted_employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    return EmployeeDeleteResponse(
        employee_code=deleted_employee.employee_code,
        deleted=True,
    )


@router.post(
    "/employees/{employee_code}/enroll",
    response_model=EmployeeFaceEnrollResponse,
)
async def enroll_employee_face(
    employee_code: str,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    deepface_service: DeepFaceService = Depends(get_deepface_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
) -> EmployeeFaceEnrollResponse:
    _ = current_user

    try:
        employee = employee_registry.get_employee(employee_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image file must not be empty",
        )

    try:
        embedding = deepface_service.embed_face(image_bytes, enforce_detection=True)
        vector_search_service.upsert_face_embedding(
            employee_code=employee.employee_code,
            embedding=embedding,
            metadata={
                "source": "admin-enroll",
                "filename": file.filename or "uploaded-face.jpg",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return EmployeeFaceEnrollResponse(
        employee_code=employee.employee_code,
        enrolled=True,
        embedding_dimensions=len(embedding),
        message=f"Face embedding enrolled for employee {employee.employee_code}.",
    )


@router.post(
    "/employees/{employee_code}/enroll-samples",
    response_model=EmployeeFaceEnrollSamplesResponse,
)
async def enroll_employee_face_samples(
    employee_code: str,
    files: list[UploadFile] = File(...),
    device_name: str | None = Form(default=None),
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    deepface_service: DeepFaceService = Depends(get_deepface_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
) -> EmployeeFaceEnrollSamplesResponse:
    try:
        employee = employee_registry.get_employee(employee_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    sample_count = len(files)
    if sample_count < settings.enrollment_min_samples:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"at least {settings.enrollment_min_samples} face samples are required",
        )
    if sample_count > settings.enrollment_max_samples:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"at most {settings.enrollment_max_samples} face samples are allowed",
        )

    embeddings: list[list[float]] = []
    filenames: list[str] = []

    try:
        for index, upload in enumerate(files, start=1):
            image_bytes = await _read_non_empty_upload(upload, index)
            embeddings.append(deepface_service.embed_face(image_bytes, enforce_detection=True))
            filenames.append(upload.filename or f"sample-{index}.jpg")

        averaged_embedding = _average_embeddings(embeddings)
        normalized_device_name = _normalize_optional_text(device_name)
        vector_search_service.upsert_face_embedding(
            employee_code=employee.employee_code,
            embedding=averaged_embedding,
            metadata={
                "source": "enrollment-station",
                "device_name": normalized_device_name,
                "operator": current_user,
                "sample_count": sample_count,
                "filenames": filenames,
                "model_name": settings.model_name,
                "model_version": settings.model_version,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return EmployeeFaceEnrollSamplesResponse(
        employee_code=employee.employee_code,
        enrolled=True,
        embedding_dimensions=len(averaged_embedding),
        sample_count=sample_count,
        device_name=normalized_device_name,
        message=(
            f"Face embedding enrolled for employee {employee.employee_code} "
            f"from {sample_count} live samples."
        ),
    )


async def _read_non_empty_upload(upload: UploadFile, index: int) -> bytes:
    image_bytes = await upload.read()
    if not image_bytes:
        raise ValueError(f"face sample {index} must not be empty")
    return image_bytes


def _average_embeddings(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        raise ValueError("at least one embedding is required")

    expected_dimensions = len(embeddings[0])
    if expected_dimensions == 0:
        raise ValueError("embedding must not be empty")

    for embedding in embeddings:
        if len(embedding) != expected_dimensions:
            raise ValueError("all face samples must use the same embedding dimensions")

    return [
        round(sum(embedding[index] for embedding in embeddings) / len(embeddings), 8)
        for index in range(expected_dimensions)
    ]


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
