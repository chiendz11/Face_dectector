from fastapi import FastAPI

from app.api.endpoints_admin import router as admin_router
from app.api.endpoints_auth import router as auth_router
from app.api.endpoints_vision import router as vision_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(vision_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "embedding_provider": settings.embedding_provider,
        "model_name": settings.model_name,
        "model_version": settings.model_version,
        "embedding_dimensions": settings.embedding_dimensions,
        "match_threshold": settings.match_threshold,
    }
