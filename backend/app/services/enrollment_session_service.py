from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import EnrollmentSession


class EnrollmentSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, *, employee_code: str, created_by: str) -> tuple[EnrollmentSession, str]:
        normalized_code = self._normalize_employee_code(employee_code)
        actor = created_by.strip()
        if not actor:
            raise ValueError("created_by must not be empty")

        token = secrets.token_urlsafe(32)
        record = EnrollmentSession(
            token_hash=self.hash_token(token),
            employee_code=normalized_code,
            status="pending",
            created_by=actor,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.enrollment_session_ttl_minutes),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record, token

    def get_session(self, token: str) -> EnrollmentSession | None:
        token_hash = self.hash_token(token)
        record = (
            self.db.query(EnrollmentSession)
            .filter(EnrollmentSession.token_hash == token_hash)
            .first()
        )
        if record is None:
            return None

        if record.status == "pending" and self._is_expired(record.expires_at):
            record.status = "expired"
            self.db.commit()
            self.db.refresh(record)

        return record

    def complete_session(
        self,
        record: EnrollmentSession,
        *,
        device_name: str | None,
        sample_count: int,
        used_by: str | None = None,
    ) -> EnrollmentSession:
        if record.status != "pending":
            raise ValueError(f"enrollment session is {record.status}")

        record.status = "completed"
        record.completed_at = datetime.now(UTC)
        record.device_name = device_name
        record.sample_count = sample_count
        record.used_by = used_by
        self.db.commit()
        self.db.refresh(record)
        return record

    def revoke_session(self, token: str) -> EnrollmentSession | None:
        record = self.get_session(token)
        if record is None:
            return None

        if record.status == "pending":
            record.status = "revoked"
            record.revoked_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(record)

        return record

    @staticmethod
    def hash_token(token: str) -> str:
        normalized = token.strip()
        if not normalized:
            raise ValueError("enrollment token must not be empty")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_employee_code(employee_code: str) -> str:
        normalized_code = employee_code.strip().upper()
        if not normalized_code:
            raise ValueError("employee_code must not be empty")
        return normalized_code

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        normalized_expires_at = expires_at
        if normalized_expires_at.tzinfo is None:
            normalized_expires_at = normalized_expires_at.replace(tzinfo=UTC)
        return normalized_expires_at <= datetime.now(UTC)
