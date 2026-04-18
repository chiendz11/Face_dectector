from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, func

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
    department = Column(String(64), nullable=True)
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
