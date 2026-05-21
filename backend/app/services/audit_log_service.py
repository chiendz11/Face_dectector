from sqlalchemy.orm import Session

from app.models.db_models import AuditEvent
from app.models.schemas import AuditEventRecord


class AuditLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_event(
        self,
        *,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> AuditEventRecord:
        event = AuditEvent(
            actor=self._normalize_required(actor, "actor"),
            action=self._normalize_required(action, "action"),
            resource_type=self._normalize_required(resource_type, "resource_type"),
            resource_id=self._normalize_optional(resource_id),
            event_metadata=metadata or None,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return self._to_record(event)

    def list_events(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 50,
    ) -> list[AuditEventRecord]:
        query = self.db.query(AuditEvent)
        if actor:
            query = query.filter(AuditEvent.actor.ilike(f"%{self._normalize_optional(actor)}%"))
        if action:
            query = query.filter(AuditEvent.action == self._normalize_required(action, "action"))
        if resource_type:
            query = query.filter(
                AuditEvent.resource_type == self._normalize_required(resource_type, "resource_type")
            )

        events = query.order_by(AuditEvent.id.desc()).limit(limit).all()
        return [self._to_record(event) for event in events]

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError(f"{field_name} must not be empty")
        return normalized

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @staticmethod
    def _to_record(event: AuditEvent) -> AuditEventRecord:
        return AuditEventRecord(
            id=event.id,
            actor=event.actor,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
