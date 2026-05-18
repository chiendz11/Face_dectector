from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.db_models import Employee
from app.models.schemas import EmployeeCreate, EmployeeRecord, EmployeeUpdate


class EmployeeRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_employees(self, include_inactive: bool = False) -> list[EmployeeRecord]:
        query = self.db.query(Employee)
        if not include_inactive:
            query = query.filter(Employee.active.is_(True))

        employees = query.order_by(Employee.employee_code).all()
        return [self._to_record(item) for item in employees]

    def get_employee(self, employee_code: str, include_inactive: bool = False) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        query = self.db.query(Employee).filter(Employee.employee_code == normalized_code)
        if not include_inactive:
            query = query.filter(Employee.active.is_(True))

        record = query.first()
        if record is None:
            return None

        return self._to_record(record)

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
            active=True,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return self._to_record(record)

    def update_employee(self, employee_code: str, update: EmployeeUpdate) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        record = (
            self.db.query(Employee)
            .filter(Employee.employee_code == normalized_code)
            .filter(Employee.active.is_(True))
            .first()
        )
        if record is None:
            return None

        fields_set = getattr(update, "model_fields_set", None)
        if fields_set is None:
            fields_set = getattr(update, "__fields_set__", set())

        if "full_name" in fields_set and update.full_name is not None:
            full_name = update.full_name.strip()
            if not full_name:
                raise ValueError("full_name must not be empty")
            record.full_name = full_name

        if "department" in fields_set:
            record.department = update.department.strip() if update.department else None

        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def delete_employee(self, employee_code: str) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        record = (
            self.db.query(Employee)
            .filter(Employee.employee_code == normalized_code)
            .first()
        )
        if record is None:
            return None

        record.active = False
        record.deleted_at = datetime.now(UTC)
        record.updated_at = record.deleted_at
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def restore_employee(self, employee_code: str) -> EmployeeRecord | None:
        normalized_code = self._normalize_employee_code(employee_code)
        record = (
            self.db.query(Employee)
            .filter(Employee.employee_code == normalized_code)
            .first()
        )
        if record is None:
            return None

        record.active = True
        record.deleted_at = None
        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    @staticmethod
    def _normalize_employee_code(employee_code: str) -> str:
        normalized_code = employee_code.strip().upper()

        if not normalized_code:
            raise ValueError("employee_code must not be empty")

        return normalized_code

    @staticmethod
    def _to_record(record: Employee) -> EmployeeRecord:
        return EmployeeRecord(
            employee_code=record.employee_code,
            full_name=record.full_name,
            department=record.department,
            active=bool(record.active),
        )
