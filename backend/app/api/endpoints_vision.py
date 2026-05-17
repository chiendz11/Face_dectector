from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import get_recognition_service
from app.models.schemas import RecognitionResponse
from app.services.recognition_service import RecognitionService

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/health")
def vision_health() -> dict:
    return {"status": "ok", "scope": "vision"}


@router.post("/recognize")
async def recognize_face(
    file: UploadFile = File(...),
    device_name: str | None = Form(default=None),
    recognition_service: RecognitionService = Depends(get_recognition_service),
) -> RecognitionResponse:
    image_bytes = await file.read()

    try:
        return recognition_service.recognize_face(
            filename=file.filename or "uploaded-face.jpg",
            image_bytes=image_bytes,
            device_name=device_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
