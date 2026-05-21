from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import (
    get_audit_log_service,
    get_current_user,
    get_deepface_service,
    get_department_registry_service,
    get_employee_registry_service,
    get_enrollment_session_service,
    get_recognition_log_service,
    get_vector_search_service,
)
from app.core.config import settings
from app.models.schemas import (
    AuditEventListResponse,
    DepartmentCreate,
    DepartmentDeleteResponse,
    DepartmentListResponse,
    DepartmentRecord,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeDeleteResponse,
    EmployeeFaceEnrollResponse,
    EmployeeFaceEnrollSamplesResponse,
    EmployeeListResponse,
    EmployeeRecord,
    EmployeeUpdate,
    EnrollmentSessionCreateResponse,
    EnrollmentSessionStatusResponse,
    RecognitionEventListResponse,
)
from app.services.audit_log_service import AuditLogService
from app.services.deepface_service import DeepFaceService
from app.services.department_registry import DepartmentRegistryService
from app.services.employee_registry import EmployeeRegistryService
from app.services.enrollment_session_service import EnrollmentSessionService
from app.services.recognition_log_service import RecognitionLogService
from app.services.vector_search_service import VectorSearchService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health() -> dict:
    return {"status": "ok", "scope": "admin"}


@router.get("/recognition-events", response_model=RecognitionEventListResponse)
def list_recognition_events(
    matched: bool | None = Query(default=None),
    employee_code: str | None = Query(default=None),
    device_name: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: str = Depends(get_current_user),
    recognition_log: RecognitionLogService = Depends(get_recognition_log_service),
) -> RecognitionEventListResponse:
    _ = current_user
    events = recognition_log.list_events(
        matched=matched,
        employee_code=employee_code,
        device_name=device_name,
        limit=limit,
    )
    return RecognitionEventListResponse(items=events, total=len(events))


@router.get("/audit-events", response_model=AuditEventListResponse)
def list_audit_events(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: str = Depends(get_current_user),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> AuditEventListResponse:
    _ = current_user
    events = audit_log.list_events(
        actor=actor,
        action=action,
        resource_type=resource_type,
        limit=limit,
    )
    return AuditEventListResponse(items=events, total=len(events))


@router.get("/departments", response_model=DepartmentListResponse)
def list_departments(
    include_inactive: bool = Query(default=False),
    current_user: str = Depends(get_current_user),
    department_registry: DepartmentRegistryService = Depends(get_department_registry_service),
) -> DepartmentListResponse:
    _ = current_user
    departments = department_registry.list_departments(include_inactive=include_inactive)
    return DepartmentListResponse(items=departments, total=len(departments))


@router.post(
    "/departments",
    response_model=DepartmentRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    department: DepartmentCreate,
    current_user: str = Depends(get_current_user),
    department_registry: DepartmentRegistryService = Depends(get_department_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> DepartmentRecord:
    try:
        created = department_registry.create_department(department)
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "already exists" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    _record_audit(
        audit_log,
        actor=current_user,
        action="department.create",
        resource_type="department",
        resource_id=str(created.id),
        metadata={"code": created.code, "name": created.name},
    )
    return created


@router.patch("/departments/{department_id}", response_model=DepartmentRecord)
def update_department(
    department_id: int,
    update: DepartmentUpdate,
    current_user: str = Depends(get_current_user),
    department_registry: DepartmentRegistryService = Depends(get_department_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> DepartmentRecord:
    try:
        department = department_registry.update_department(department_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"department {department_id} was not found")
    _record_audit(
        audit_log,
        actor=current_user,
        action="department.update",
        resource_type="department",
        resource_id=str(department.id),
        metadata={"code": department.code, "name": department.name},
    )
    return department


@router.delete("/departments/{department_id}", response_model=DepartmentDeleteResponse)
def delete_department(
    department_id: int,
    current_user: str = Depends(get_current_user),
    department_registry: DepartmentRegistryService = Depends(get_department_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> DepartmentDeleteResponse:
    try:
        department = department_registry.delete_department(department_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"department {department_id} was not found")
    _record_audit(
        audit_log,
        actor=current_user,
        action="department.deactivate",
        resource_type="department",
        resource_id=str(department.id),
        metadata={"code": department.code, "name": department.name},
    )
    return DepartmentDeleteResponse(id=department.id, deleted=True)


@router.post("/departments/{department_id}/restore", response_model=DepartmentRecord)
def restore_department(
    department_id: int,
    current_user: str = Depends(get_current_user),
    department_registry: DepartmentRegistryService = Depends(get_department_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> DepartmentRecord:
    department = department_registry.restore_department(department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"department {department_id} was not found")
    _record_audit(
        audit_log,
        actor=current_user,
        action="department.restore",
        resource_type="department",
        resource_id=str(department.id),
        metadata={"code": department.code, "name": department.name},
    )
    return department


@router.get("/employees", response_model=EmployeeListResponse)
def list_employees(
    include_inactive: bool = Query(default=False),
    query: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=50),
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
) -> EmployeeListResponse:
    _ = current_user
    employees = employee_registry.list_employees(
        include_inactive=include_inactive,
        query=query,
        limit=limit,
    )
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
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeRecord:
    try:
        created = employee_registry.create_employee(employee)
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
    _record_audit(
        audit_log,
        actor=current_user,
        action="employee.create",
        resource_type="employee",
        resource_id=created.employee_code,
        metadata={"full_name": created.full_name, "department": created.department},
    )
    return created


@router.patch(
    "/employees/{employee_code}",
    response_model=EmployeeRecord,
)
def update_employee(
    employee_code: str,
    update: EmployeeUpdate,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeRecord:
    try:
        updated_employee = employee_registry.update_employee(employee_code, update)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if updated_employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    _record_audit(
        audit_log,
        actor=current_user,
        action="employee.update",
        resource_type="employee",
        resource_id=updated_employee.employee_code,
        metadata={"full_name": updated_employee.full_name, "department": updated_employee.department},
    )
    return updated_employee


@router.delete(
    "/employees/{employee_code}",
    response_model=EmployeeDeleteResponse,
)
def delete_employee(
    employee_code: str,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeDeleteResponse:
    try:
        deleted_employee = employee_registry.delete_employee(employee_code)
        if deleted_employee is not None:
            vector_search_service.delete_face_embedding(deleted_employee.employee_code)
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

    _record_audit(
        audit_log,
        actor=current_user,
        action="employee.deactivate",
        resource_type="employee",
        resource_id=deleted_employee.employee_code,
        metadata={"embedding_revoked": True},
    )
    return EmployeeDeleteResponse(
        employee_code=deleted_employee.employee_code,
        deleted=True,
    )


@router.post(
    "/employees/{employee_code}/restore",
    response_model=EmployeeRecord,
)
def restore_employee(
    employee_code: str,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeRecord:
    try:
        restored_employee = employee_registry.restore_employee(employee_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if restored_employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    _record_audit(
        audit_log,
        actor=current_user,
        action="employee.restore",
        resource_type="employee",
        resource_id=restored_employee.employee_code,
        metadata={"full_name": restored_employee.full_name, "department": restored_employee.department},
    )
    return restored_employee


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
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeFaceEnrollResponse:
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

    _record_audit(
        audit_log,
        actor=current_user,
        action="face.enroll",
        resource_type="employee",
        resource_id=employee.employee_code,
        metadata={
            "source": "admin-enroll",
            "filename": file.filename or "uploaded-face.jpg",
            "embedding_dimensions": len(embedding),
        },
    )
    return EmployeeFaceEnrollResponse(
        employee_code=employee.employee_code,
        enrolled=True,
        embedding_dimensions=len(embedding),
        message=f"Face embedding enrolled for employee {employee.employee_code}.",
    )


@router.post(
    "/employees/{employee_code}/enrollment-sessions",
    response_model=EnrollmentSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_enrollment_session(
    employee_code: str,
    current_user: str = Depends(get_current_user),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    enrollment_session_service: EnrollmentSessionService = Depends(get_enrollment_session_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EnrollmentSessionCreateResponse:
    try:
        employee = employee_registry.get_employee(employee_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"employee {employee_code.strip().upper()} was not found",
        )

    record, token = enrollment_session_service.create_session(
        employee_code=employee.employee_code,
        created_by=current_user,
    )
    _record_audit(
        audit_log,
        actor=current_user,
        action="enrollment_session.create",
        resource_type="enrollment_session",
        resource_id=str(record.id),
        metadata={"employee_code": record.employee_code, "expires_at": record.expires_at.isoformat()},
    )
    return EnrollmentSessionCreateResponse(
        session_id=record.id,
        employee_code=record.employee_code,
        token=token,
        enrollment_url=f"/admin/#/enroll/session/{token}",
        expires_at=record.expires_at,
        status=record.status,
    )


@router.get(
    "/enrollment-sessions/{token}",
    response_model=EnrollmentSessionStatusResponse,
)
def get_enrollment_session(
    token: str,
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    enrollment_session_service: EnrollmentSessionService = Depends(get_enrollment_session_service),
) -> EnrollmentSessionStatusResponse:
    record = _get_existing_enrollment_session(token, enrollment_session_service)
    employee = employee_registry.get_employee(record.employee_code, include_inactive=True)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="enrollment session employee no longer exists",
        )

    return EnrollmentSessionStatusResponse(
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department,
        status=record.status,
        expires_at=record.expires_at,
        sample_count=record.sample_count,
    )


@router.post(
    "/enrollment-sessions/{token}/complete",
    response_model=EmployeeFaceEnrollSamplesResponse,
)
async def complete_enrollment_session(
    token: str,
    files: list[UploadFile] = File(...),
    device_name: str | None = Form(default=None),
    employee_registry: EmployeeRegistryService = Depends(get_employee_registry_service),
    enrollment_session_service: EnrollmentSessionService = Depends(get_enrollment_session_service),
    deepface_service: DeepFaceService = Depends(get_deepface_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
    audit_log: AuditLogService = Depends(get_audit_log_service),
) -> EmployeeFaceEnrollSamplesResponse:
    record = _get_pending_enrollment_session(token, enrollment_session_service)
    employee = employee_registry.get_employee(record.employee_code)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="enrollment session employee is inactive or no longer exists",
        )

    response = await _enroll_employee_face_samples(
        employee=employee,
        files=files,
        device_name=device_name,
        source="admin-enrollment-session",
        operator=record.created_by,
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
        extra_metadata={"enrollment_session_id": record.id},
    )
    try:
        enrollment_session_service.complete_session(
            record,
            device_name=response.device_name,
            sample_count=response.sample_count,
            used_by="session-token",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    _record_audit(
        audit_log,
        actor=record.created_by,
        action="enrollment_session.complete",
        resource_type="enrollment_session",
        resource_id=str(record.id),
        metadata={
            "employee_code": employee.employee_code,
            "device_name": response.device_name,
            "sample_count": response.sample_count,
            "used_by": "session-token",
        },
    )
    return response


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
    audit_log: AuditLogService = Depends(get_audit_log_service),
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

    response = await _enroll_employee_face_samples(
        employee=employee,
        files=files,
        device_name=device_name,
        source="enrollment-station",
        operator=current_user,
        deepface_service=deepface_service,
        vector_search_service=vector_search_service,
    )
    _record_audit(
        audit_log,
        actor=current_user,
        action="face.enroll_samples",
        resource_type="employee",
        resource_id=employee.employee_code,
        metadata={
            "device_name": response.device_name,
            "sample_count": response.sample_count,
            "source": "enrollment-station",
        },
    )
    return response


def _get_existing_enrollment_session(
    token: str,
    enrollment_session_service: EnrollmentSessionService,
):
    try:
        record = enrollment_session_service.get_session(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="enrollment session was not found",
        )

    return record


def _get_pending_enrollment_session(
    token: str,
    enrollment_session_service: EnrollmentSessionService,
):
    record = _get_existing_enrollment_session(token, enrollment_session_service)
    if record.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"enrollment session is {record.status}",
        )

    return record


async def _enroll_employee_face_samples(
    *,
    employee: EmployeeRecord,
    files: list[UploadFile],
    device_name: str | None,
    source: str,
    operator: str,
    deepface_service: DeepFaceService,
    vector_search_service: VectorSearchService,
    extra_metadata: dict | None = None,
) -> EmployeeFaceEnrollSamplesResponse:
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
        metadata = {
            "source": source,
            "device_name": normalized_device_name,
            "operator": operator,
            "sample_count": sample_count,
            "filenames": filenames,
            "model_name": settings.model_name,
            "model_version": settings.model_version,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        vector_search_service.upsert_face_embedding(
            employee_code=employee.employee_code,
            embedding=averaged_embedding,
            metadata=metadata,
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


def _record_audit(
    audit_log: AuditLogService,
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    audit_log.record_event(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
    )
