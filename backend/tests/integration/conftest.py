"""Shared fixtures for integration tests.

Integration tests operate at the service / repository layer.
They use an in-memory SQLite database so no external infrastructure
(Postgres, Redis, MinIO) is required, and they run in CI alongside
lint / unit tests.
"""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import Base  # noqa: E402
import app.models.db_models  # noqa: F401,E402


@pytest.fixture(scope="function")
def db_session():
    """Isolated in-memory SQLite session, each test gets its own engine + schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
