from datetime import UTC, datetime
import secrets

from sqlalchemy.orm import Session

from app.models.db_models import Department, Employee, FaceEmbedding
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
        employee_code = (
            self._normalize_employee_code(employee.employee_code)
            if employee.employee_code
            else self._generate_employee_code()
        )
        full_name = employee.full_name.strip()
        department_id, department = self._resolve_department(
            department_id=employee.department_id,
            department_name=employee.department,
        )

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
            department_id=department_id,
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
            department_id = record.department_id if "department_id" not in fields_set else update.department_id
            resolved_department_id, resolved_department = self._resolve_department(
                department_id=department_id,
                department_name=update.department,
                allow_legacy_department=True,
            )
            record.department_id = resolved_department_id
            record.department = resolved_department

        if "department_id" in fields_set and "department" not in fields_set:
            resolved_department_id, resolved_department = self._resolve_department(
                department_id=update.department_id,
                department_name=None,
            )
            record.department_id = resolved_department_id
            record.department = resolved_department

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

    def _generate_employee_code(self) -> str:
        for _ in range(10):
            candidate = f"EMP-{secrets.token_hex(3).upper()}"
            exists = (
                self.db.query(Employee)
                .filter(Employee.employee_code == candidate)
                .first()
            )
            if exists is None:
                return candidate
        raise ValueError("unable to generate a unique employee_code")

    def _resolve_department(
        self,
        *,
        department_id: int | None,
        department_name: str | None,
        allow_legacy_department: bool = True,
    ) -> tuple[int | None, str | None]:
        if department_id is not None:
            department = (
                self.db.query(Department)
                .filter(Department.id == department_id)
                .filter(Department.active.is_(True))
                .first()
            )
            if department is None:
                raise ValueError(f"department {department_id} was not found")
            return department.id, department.name

        if department_name and allow_legacy_department:
            normalized = department_name.strip()
            return None, normalized or None

        return None, None

    def _has_face_embedding(self, employee_code: str) -> bool:
        return (
            self.db.query(FaceEmbedding.id)
            .filter(FaceEmbedding.employee_code == employee_code)
            .first()
            is not None
        )

    def _to_record(self, record: Employee) -> EmployeeRecord:
        return EmployeeRecord(
            employee_code=record.employee_code,
            full_name=record.full_name,
            department_id=record.department_id,
            department=record.department,
            active=bool(record.active),
            has_face_embedding=self._has_face_embedding(record.employee_code),
        )
