"""Integration tests — RecognitionService._save_event with SQLite.

Validates:
- dedupe_key is stamped on matched events before persistence
- unmatched events have no dedupe_key
- duplicate dedupe_key (IntegrityError) is swallowed — idempotent design
- db=None skips persistence without raising
- non-dedupe IntegrityError is re-raised (data integrity preserved)
"""

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.db_models import RecognitionEvent
from app.services.recognition_service import RecognitionService


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def svc(db_session):
    deepface = MagicMock()
    vector = MagicMock()
    minio = MagicMock()
    return RecognitionService(
        deepface_service=deepface,
        vector_search_service=vector,
        minio_service=minio,
        db=db_session,
    )


def _make_event(**kwargs) -> RecognitionEvent:
    defaults = dict(
        employee_code=None,
        matched=False,
        confidence=0.0,
        device_name="cam-01",
        filename="snap.jpg",
        snapshot_url="http://minio/snap.jpg",
        dedupe_key=None,
    )
    defaults.update(kwargs)
    return RecognitionEvent(**defaults)


# ---------------------------------------------------------------------------
# dedupe_key stamping
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveEventDedupeKey:
    def test_matched_event_receives_dedupe_key(self, svc, db_session):
        event = _make_event(employee_code="EMP001", matched=True, confidence=0.95)
        svc._save_event(event)

        assert event.dedupe_key is not None
        assert "EMP001" in event.dedupe_key

    def test_unmatched_event_has_no_dedupe_key(self, svc, db_session):
        event = _make_event(matched=False, confidence=0.0)
        svc._save_event(event)

        assert event.dedupe_key is None

    def test_matched_event_persisted_to_db(self, svc, db_session):
        event = _make_event(employee_code="EMP002", matched=True, confidence=0.9)
        svc._save_event(event)

        row = db_session.query(RecognitionEvent).filter_by(employee_code="EMP002").first()
        assert row is not None
        assert row.matched is True

    def test_unmatched_event_persisted_to_db(self, svc, db_session):
        event = _make_event(matched=False, confidence=0.1, filename="unknown.jpg")
        svc._save_event(event)

        rows = db_session.query(RecognitionEvent).all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Duplicate dedupe_key — idempotent (IntegrityError on dedupe_key swallowed)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveEventDedupeSilence:
    def test_duplicate_dedupe_key_is_silently_ignored(self, svc, db_session):
        """Second event with the same dedupe_key within the same time window is discarded."""
        event_a = _make_event(employee_code="EMP003", matched=True, confidence=0.9)
        svc._save_event(event_a)

        # Capture the key value before session state changes
        saved_key = event_a.dedupe_key

        # Force same dedupe_key so the second insert collides
        event_b = _make_event(employee_code="EMP003", matched=True, confidence=0.9)
        event_b.dedupe_key = saved_key

        # Should NOT raise
        svc._save_event(event_b)

        # DB must still have exactly one row for this key
        rows = db_session.query(RecognitionEvent).filter_by(dedupe_key=saved_key).all()
        assert len(rows) == 1

    def test_non_dedupe_integrity_error_is_reraised(self, svc, db_session):
        """Integrity errors unrelated to dedupe_key must bubble up."""
        event = _make_event(matched=False, confidence=0.0)

        with patch.object(db_session, "flush", side_effect=IntegrityError("unique constraint", {}, None)):
            with pytest.raises(IntegrityError):
                svc._save_event(event)


# ---------------------------------------------------------------------------
# db=None — skip persistence path
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveEventNoDb:
    def test_save_event_with_no_db_does_not_raise(self):
        svc = RecognitionService(
            deepface_service=MagicMock(),
            vector_search_service=MagicMock(),
            minio_service=MagicMock(),
            db=None,
        )
        event = _make_event(matched=False, confidence=0.0)
        # Must complete silently
        svc._save_event(event)
