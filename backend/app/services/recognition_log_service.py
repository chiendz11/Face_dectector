from sqlalchemy.orm import Session

from app.models.db_models import RecognitionEvent
from app.models.schemas import RecognitionEventRecord


class RecognitionLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_events(
        self,
        *,
        matched: bool | None = None,
        employee_code: str | None = None,
        device_name: str | None = None,
        limit: int = 50,
    ) -> list[RecognitionEventRecord]:
        query = self.db.query(RecognitionEvent)
        if matched is not None:
            query = query.filter(RecognitionEvent.matched.is_(matched))
        normalized_employee_code = self._normalize_optional(employee_code)
        if normalized_employee_code:
            query = query.filter(RecognitionEvent.employee_code.ilike(f"%{normalized_employee_code}%"))
        normalized_device_name = self._normalize_optional(device_name)
        if normalized_device_name:
            query = query.filter(RecognitionEvent.device_name.ilike(f"%{normalized_device_name}%"))

        events = query.order_by(RecognitionEvent.id.desc()).limit(limit).all()
        return [self._to_record(event) for event in events]

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @staticmethod
    def _to_record(event: RecognitionEvent) -> RecognitionEventRecord:
        return RecognitionEventRecord(
            id=event.id,
            employee_code=event.employee_code,
            matched=bool(event.matched),
            confidence=float(event.confidence),
            device_name=event.device_name,
            filename=event.filename,
            snapshot_url=event.snapshot_url,
            created_at=event.created_at,
        )
