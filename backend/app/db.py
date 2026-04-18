from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url
REPLICA_URLS = [
    url.strip()
    for url in (settings.database_replica_urls or "").split(",")
    if url.strip()
]
READ_DATABASE_URL = REPLICA_URLS[0] if REPLICA_URLS else SQLALCHEMY_DATABASE_URL

connect_args = {
    "check_same_thread": False,
} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=settings.sqlalchemy_pool_size,
    max_overflow=settings.sqlalchemy_max_overflow,
    pool_recycle=settings.sqlalchemy_pool_recycle_seconds,
    future=True,
)
read_engine = create_engine(
    READ_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=settings.sqlalchemy_pool_size,
    max_overflow=settings.sqlalchemy_max_overflow,
    pool_recycle=settings.sqlalchemy_pool_recycle_seconds,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
ReadSessionLocal = sessionmaker(bind=read_engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db():
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()
