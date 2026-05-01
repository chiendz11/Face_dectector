from sqlalchemy.orm import Session

from app.models.db_models import Employee
from app.models.schemas import EmployeeCreate, EmployeeRecord


class EmployeeRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_employees(self) -> list[EmployeeRecord]:
        employees = (
            self.db.query(Employee)
            .order_by(Employee.employee_code)
            .all()
        )
        return [
            EmployeeRecord(
                employee_code=item.employee_code,
                full_name=item.full_name,
                department=item.department,
            )
            for item in employees
        ]

    def get_employee(self, employee_code: str) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        record = (
            self.db.query(Employee)
            .filter(Employee.employee_code == normalized_code)
            .first()
        )
        if record is None:
            return None

        return EmployeeRecord(
            employee_code=record.employee_code,
            full_name=record.full_name,
            department=record.department,
        )

    def create_employee(self, employee: EmployeeCreate) -> EmployeeRecord:
        employee_code = self._normalize_employee_code(employee.employee_code)
        full_name = employee.full_name.strip()
        department = employee.department.strip() if employee.department else None

        if not full_name:
            raise ValueError("full_name must not be empty")

        existing = (
            self.db.query(Employee)
            .filter(Employee.employee_code == employee_code)
            .first()
        )
        if existing is not None:
            raise ValueError(f"employee {employee_code} already exists")

        record = Employee(
            employee_code=employee_code,
            full_name=full_name,
            department=department,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return EmployeeRecord(
            employee_code=record.employee_code,
            full_name=record.full_name,
            department=record.department,
        )

    def delete_employee(self, employee_code: str) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        record = (
            self.db.query(Employee)
            .filter(Employee.employee_code == normalized_code)
            .first()
        )
        if record is None:
            return None

        deleted = EmployeeRecord(
            employee_code=record.employee_code,
            full_name=record.full_name,
            department=record.department,
        )
        self.db.delete(record)
        self.db.commit()
        return deleted

    @staticmethod
    def _normalize_employee_code(employee_code: str) -> str:
        normalized_code = employee_code.strip().upper()

        if not normalized_code:
            raise ValueError("employee_code must not be empty")

        return normalized_code
