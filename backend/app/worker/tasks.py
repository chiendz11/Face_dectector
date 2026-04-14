from app.worker.celery_app import celery_app


@celery_app.task
def rebuild_face_embeddings() -> dict:
    return {"status": "queued", "message": "Implement face re-indexing here."}
