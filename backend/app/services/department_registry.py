from datetime import UTC, datetime
import re

from sqlalchemy.orm import Session

from app.models.db_models import Department, Employee
from app.models.schemas import DepartmentCreate, DepartmentRecord, DepartmentUpdate


class DepartmentRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_departments(self, include_inactive: bool = False) -> list[DepartmentRecord]:
        query = self.db.query(Department)
        if not include_inactive:
            query = query.filter(Department.active.is_(True))
        records = query.order_by(Department.name).all()
        return [self._to_record(item) for item in records]

    def get_department(self, department_id: int, include_inactive: bool = False) -> Department | None:
        query = self.db.query(Department).filter(Department.id == department_id)
        if not include_inactive:
            query = query.filter(Department.active.is_(True))
        return query.first()

    def create_department(self, department: DepartmentCreate) -> DepartmentRecord:
        name = self._normalize_name(department.name)
        code = self._normalize_code(department.code) if department.code else self._generate_code(name)

        existing = (
            self.db.query(Department)
            .filter((Department.code == code) | (Department.name == name))
            .first()
        )
        if existing is not None:
            raise ValueError(f"department {name} already exists")

        record = Department(code=code, name=name, active=True)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def update_department(self, department_id: int, update: DepartmentUpdate) -> DepartmentRecord | None:
        record = self.get_department(department_id)
        if record is None:
            return None

        fields_set = getattr(update, "model_fields_set", None)
        if fields_set is None:
            fields_set = getattr(update, "__fields_set__", set())

        if "name" in fields_set and update.name is not None:
            name = self._normalize_name(update.name)
            existing = (
                self.db.query(Department)
                .filter(Department.name == name)
                .filter(Department.id != department_id)
                .first()
            )
            if existing is not None:
                raise ValueError(f"department {name} already exists")
            record.name = name

        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def delete_department(self, department_id: int) -> DepartmentRecord | None:
        record = self.get_department(department_id)
        if record is None:
            return None

        active_employee_count = (
            self.db.query(Employee)
            .filter(Employee.department_id == department_id)
            .filter(Employee.active.is_(True))
            .count()
        )
        if active_employee_count:
            raise ValueError("department has active employees")

        record.active = False
        record.deleted_at = datetime.now(UTC)
        record.updated_at = record.deleted_at
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def restore_department(self, department_id: int) -> DepartmentRecord | None:
        record = self.get_department(department_id, include_inactive=True)
        if record is None:
            return None

        record.active = True
        record.deleted_at = None
        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return self._to_record(record)

    def _generate_code(self, name: str) -> str:
        base = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:24] or "DEPT"
        code = base
        suffix = 2
        while self.db.query(Department).filter(Department.code == code).first() is not None:
            code = f"{base[:20]}-{suffix}"
            suffix += 1
        return code

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise ValueError("department name must not be empty")
        return normalized

    @staticmethod
    def _normalize_code(code: str) -> str:
        normalized = re.sub(r"[^A-Z0-9-]+", "-", code.strip().upper()).strip("-")
        if not normalized:
            raise ValueError("department code must not be empty")
        return normalized[:32]

    @staticmethod
    def _to_record(record: Department) -> DepartmentRecord:
        return DepartmentRecord(
            id=record.id,
            code=record.code,
            name=record.name,
            active=bool(record.active),
        )
