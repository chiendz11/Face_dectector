from datetime import datetime

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    department: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None


class EmployeeRecord(EmployeeCreate):
    active: bool = True


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
