from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str
    code: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None


class DepartmentRecord(BaseModel):
    id: int
    code: str
    name: str
    active: bool = True


class DepartmentListResponse(BaseModel):
    items: list[DepartmentRecord] = Field(default_factory=list)
    total: int


class DepartmentDeleteResponse(BaseModel):
    id: int
    deleted: bool


class EmployeeCreate(BaseModel):
    employee_code: str | None = None
    full_name: str
    department_id: int | None = None
    department: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    department_id: int | None = None
    department: str | None = None


class EmployeeRecord(EmployeeCreate):
    employee_code: str
    active: bool = True
    has_face_embedding: bool = False


class EmployeeListResponse(BaseModel):
    items: list[EmployeeRecord] = Field(default_factory=list)
    total: int


class EmployeeDeleteResponse(BaseModel):
    employee_code: str
    deleted: bool


class EmployeeFaceEnrollResponse(BaseModel):
    employee_code: str
    enrolled: bool
    embedding_dimensions: int
    message: str


class EmployeeFaceEnrollSamplesResponse(EmployeeFaceEnrollResponse):
    sample_count: int
    device_name: str | None = None


class EnrollmentSessionCreateResponse(BaseModel):
    session_id: int
    employee_code: str
    token: str
    enrollment_url: str
    expires_at: datetime
    status: str


class EnrollmentSessionStatusResponse(BaseModel):
    employee_code: str
    full_name: str
    department: str | None = None
    status: str
    expires_at: datetime
    sample_count: int | None = None


class RecognitionEventRecord(BaseModel):
    id: int
    employee_code: str | None = None
    matched: bool
    confidence: float
    device_name: str | None = None
    filename: str
    snapshot_url: str
    created_at: datetime


class RecognitionEventListResponse(BaseModel):
    items: list[RecognitionEventRecord] = Field(default_factory=list)
    total: int


class AuditEventRecord(BaseModel):
    id: int
    actor: str
    action: str
    resource_type: str
    resource_id: str | None = None
    metadata: dict | None = None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventRecord] = Field(default_factory=list)
    total: int


class RecognitionResult(BaseModel):
    matched: bool
    employee_code: str | None = None
    confidence: float
    snapshot_url: str | None = None


class RecognitionResponse(BaseModel):
    device_name: str | None = None
    filename: str
    status: str
    message: str
    result: RecognitionResult


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str
