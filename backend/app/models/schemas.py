from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    department: str | None = None


class EmployeeRecord(EmployeeCreate):
    active: bool = True


class EmployeeListResponse(BaseModel):
    items: list[EmployeeRecord] = Field(default_factory=list)
    total: int


class EmployeeDeleteResponse(BaseModel):
    employee_code: str
    deleted: bool


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
