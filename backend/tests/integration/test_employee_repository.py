"""Integration tests — EmployeeRegistryService + SQLite.

Covers edge cases, validation rules, DB constraint behaviour, and
ordering guarantees that unit tests with mocked sessions cannot reach.
"""

import pytest

from app.services.employee_registry import EmployeeRegistryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(db_session):
    return EmployeeRegistryService(db=db_session)


def _create(service, code="EMP001", full_name="Alice", department="Engineering"):
    from app.models.schemas import EmployeeCreate
    return service.create_employee(
        EmployeeCreate(employee_code=code, full_name=full_name, department=department)
    )


# ---------------------------------------------------------------------------
# create_employee
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCreateEmployee:
    def test_create_returns_record_with_correct_fields(self, db_session):
        svc = _make_service(db_session)
        record = _create(svc)

        assert record.employee_code == "EMP001"
        assert record.full_name == "Alice"
        assert record.department == "Engineering"

    def test_code_normalized_to_uppercase(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate
        record = svc.create_employee(
            EmployeeCreate(employee_code="emp-001", full_name="Bob")
        )

        assert record.employee_code == "EMP-001"

    def test_code_leading_trailing_whitespace_stripped(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate
        record = svc.create_employee(
            EmployeeCreate(employee_code="  EMP002  ", full_name="Carol")
        )

        assert record.employee_code == "EMP002"

    def test_full_name_leading_trailing_whitespace_stripped(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate
        record = svc.create_employee(
            EmployeeCreate(employee_code="EMP003", full_name="  Dave  ")
        )

        assert record.full_name == "Dave"

    def test_department_is_optional(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate
        record = svc.create_employee(
            EmployeeCreate(employee_code="EMP004", full_name="Eve", department=None)
        )

        assert record.department is None

    def test_department_whitespace_stripped(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate
        record = svc.create_employee(
            EmployeeCreate(employee_code="EMP005", full_name="Frank", department="  HR  ")
        )

        assert record.department == "HR"

    def test_duplicate_code_raises_value_error(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP006")

        with pytest.raises(ValueError, match="already exists"):
            _create(svc, code="EMP006", full_name="Another Person")

    def test_duplicate_code_case_insensitive(self, db_session):
        """Codes are normalised to uppercase before the duplicate check."""
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate

        svc.create_employee(EmployeeCreate(employee_code="EMP007", full_name="Grace"))

        with pytest.raises(ValueError, match="already exists"):
            svc.create_employee(EmployeeCreate(employee_code="emp007", full_name="Grace2"))

    def test_empty_code_raises_value_error(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate

        with pytest.raises(ValueError, match="employee_code"):
            svc.create_employee(EmployeeCreate(employee_code="   ", full_name="Heidi"))

    def test_whitespace_only_full_name_raises_value_error(self, db_session):
        svc = _make_service(db_session)
        from app.models.schemas import EmployeeCreate

        with pytest.raises(ValueError, match="full_name"):
            svc.create_employee(EmployeeCreate(employee_code="EMP008", full_name="   "))


# ---------------------------------------------------------------------------
# list_employees
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestListEmployees:
    def test_empty_db_returns_empty_list(self, db_session):
        svc = _make_service(db_session)
        assert svc.list_employees() == []

    def test_returns_all_created_employees(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="C")
        _create(svc, code="A")
        _create(svc, code="B")

        codes = [e.employee_code for e in svc.list_employees()]
        assert codes == ["A", "B", "C"]

    def test_ordered_by_employee_code(self, db_session):
        svc = _make_service(db_session)
        for code in ["Z001", "A001", "M001"]:
            _create(svc, code=code, full_name=f"Person {code}")

        records = svc.list_employees()
        codes = [r.employee_code for r in records]
        assert codes == sorted(codes)


# ---------------------------------------------------------------------------
# get_employee
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetEmployee:
    def test_get_existing_employee(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP010", full_name="Ivan")

        record = svc.get_employee("EMP010")
        assert record is not None
        assert record.full_name == "Ivan"

    def test_get_normalizes_code_before_lookup(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP011")

        record = svc.get_employee("  emp011  ")
        assert record is not None
        assert record.employee_code == "EMP011"

    def test_get_missing_employee_returns_none(self, db_session):
        svc = _make_service(db_session)
        assert svc.get_employee("NOTEXIST") is None


# ---------------------------------------------------------------------------
# delete_employee
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDeleteEmployee:
    def test_delete_existing_returns_deleted_record(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP020", full_name="Judy")

        deleted = svc.delete_employee("EMP020")
        assert deleted is not None
        assert deleted.employee_code == "EMP020"

    def test_delete_soft_deletes_employee_from_active_views(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP021")

        svc.delete_employee("EMP021")
        assert svc.get_employee("EMP021") is None
        inactive = svc.get_employee("EMP021", include_inactive=True)
        assert inactive is not None
        assert inactive.active is False

    def test_delete_missing_employee_returns_none(self, db_session):
        svc = _make_service(db_session)
        assert svc.delete_employee("NOBODY") is None

    def test_delete_then_recreate_same_code_is_rejected(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP022", full_name="Mallory")

        svc.delete_employee("EMP022")

        with pytest.raises(ValueError, match="already exists"):
            _create(svc, code="EMP022", full_name="Mallory v2")

    def test_delete_does_not_affect_other_employees(self, db_session):
        svc = _make_service(db_session)
        _create(svc, code="EMP023", full_name="Niaj")
        _create(svc, code="EMP024", full_name="Oscar")

        svc.delete_employee("EMP023")
        remaining = svc.list_employees()
        assert len(remaining) == 1
        assert remaining[0].employee_code == "EMP024"
