from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func

from app.core.config import settings
from app.db import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    department = Column(String(64), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(96), unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(32), nullable=True)
    matched = Column(Boolean(), nullable=False)
    confidence = Column(Float(), nullable=False)
    device_name = Column(String(64), nullable=True)
    filename = Column(String(256), nullable=False)
    snapshot_url = Column(String(512), nullable=False)
    dedupe_key = Column(String(64), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(32), nullable=False, unique=True, index=True)
    embedding = Column(
        Vector(settings.embedding_dimensions) if Vector is not None else String,
        nullable=False,
    )
    embedding_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EnrollmentSession(Base):
    __tablename__ = "enrollment_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    employee_code = Column(String(32), nullable=False, index=True)
    status = Column(String(24), default="pending", nullable=False)
    created_by = Column(String(128), nullable=False)
    used_by = Column(String(128), nullable=True)
    device_name = Column(String(64), nullable=True)
    sample_count = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String(128), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(128), nullable=True, index=True)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
