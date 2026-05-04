from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import (
    get_current_user,
    get_deepface_service,
    get_employee_registry_service,
    get_vector_search_service,
)
from app.models.schemas import (
    EmployeeCreate,
    EmployeeDeleteResponse,
    EmployeeFaceEnrollResponse,
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
        embedding = deepface_service.embed_face(image_bytes)
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

    return EmployeeFaceEnrollResponse(
        employee_code=employee.employee_code,
        enrolled=True,
        embedding_dimensions=len(embedding),
        message=f"Face embedding enrolled for employee {employee.employee_code}.",
    )
