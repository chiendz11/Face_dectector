from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    department: str | None = None


class RecognitionResult(BaseModel):
    matched: bool
    employee_code: str | None = None
    confidence: float
    snapshot_url: str | None = None
