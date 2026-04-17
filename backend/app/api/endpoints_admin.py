from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_employee_registry_service
from app.models.schemas import (
    EmployeeCreate,
    EmployeeDeleteResponse,
    EmployeeListResponse,
    EmployeeRecord,
)
from app.services.employee_registry import EmployeeRegistryService

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
