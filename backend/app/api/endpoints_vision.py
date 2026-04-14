from fastapi import APIRouter, File, Form, UploadFile

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/health")
def vision_health() -> dict:
    return {"status": "ok", "scope": "vision"}


@router.post("/recognize")
async def recognize_face(
    file: UploadFile = File(...),
    device_name: str | None = Form(default=None),
) -> dict:
    return {
        "device_name": device_name,
        "filename": file.filename,
        "status": "received",
        "message": "Plug DeepFace embedding, vector search, and decision logic here.",
    }
