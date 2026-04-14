from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health() -> dict:
    return {"status": "ok", "scope": "admin"}


@router.get("/employees")
def list_employees() -> dict:
    return {
        "items": [],
        "message": "Implement employee CRUD, roles, and access rules here.",
    }
