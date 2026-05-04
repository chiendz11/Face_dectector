"""Integration tests — VectorSearchService (in-memory fallback).

Tests cover embedding validation, upsert semantics, similarity search
thresholds, and best-match selection — all without a live Postgres/pgvector
instance.  The service's pure-Python cosine-similarity path is exercised
so that the logic is proven independently of the database driver.
"""

import pytest

from app.services.vector_search_service import VectorSearchService

DIMS = 4  # Keep small; _validate_embedding checks exact dimensionality


def _service(threshold: float = 0.80) -> VectorSearchService:
    return VectorSearchService(
        db=None,
        read_db=None,
        match_threshold=threshold,
        embedding_dimensions=DIMS,
    )


def _unit_vec(index: int) -> list[float]:
    """Return a unit vector with 1.0 at position *index* and 0.0 elsewhere."""
    v = [0.0] * DIMS
    v[index] = 1.0
    return v


# ---------------------------------------------------------------------------
# upsert_face_embedding — validation
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestUpsertValidation:
    def test_empty_embedding_raises(self):
        svc = _service()
        with pytest.raises(ValueError, match="empty"):
            svc.upsert_face_embedding("EMP001", [])

    def test_wrong_dimensions_raises(self):
        svc = _service()
        with pytest.raises(ValueError, match="dimensions"):
            svc.upsert_face_embedding("EMP001", [0.5, 0.5])  # 2 != DIMS

    def test_empty_code_raises(self):
        svc = _service()
        with pytest.raises(ValueError, match="employee_code"):
            svc.upsert_face_embedding("   ", _unit_vec(0))

    def test_code_normalized_to_uppercase(self):
        svc = _service()
        result = svc.upsert_face_embedding("emp001", _unit_vec(0))
        assert result["employee_code"] == "EMP001"


# ---------------------------------------------------------------------------
# upsert_face_embedding — update semantics
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestUpsertUpdateSemantics:
    def test_upsert_stores_embedding(self):
        svc = _service()
        svc.upsert_face_embedding("EMP001", _unit_vec(0))

        result = svc.search_similar_face(_unit_vec(0))
        assert result["match"] == "EMP001"

    def test_second_upsert_replaces_embedding(self):
        svc = _service()
        svc.upsert_face_embedding("EMP001", _unit_vec(0))
        svc.upsert_face_embedding("EMP001", _unit_vec(1))

        # Original direction should no longer be the best match at high threshold
        result_old = svc.search_similar_face(_unit_vec(0))
        result_new = svc.search_similar_face(_unit_vec(1))

        assert result_new["match"] == "EMP001"
        # Cosine similarity between unit vec 0 and unit vec 1 is 0 — no match
        assert result_old["match"] is None

    def test_upsert_returns_payload_with_metadata(self):
        svc = _service()
        meta = {"model": "VGG-Face", "version": "1"}
        result = svc.upsert_face_embedding("EMP002", _unit_vec(2), metadata=meta)

        assert result["metadata"] == meta


# ---------------------------------------------------------------------------
# search_similar_face — threshold & match logic
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearchSimilarFace:
    def test_empty_store_returns_no_match(self):
        svc = _service()
        result = svc.search_similar_face(_unit_vec(0))

        assert result["match"] is None
        assert result["score"] == 0.0

    def test_identical_vector_matches_above_threshold(self):
        svc = _service(threshold=0.80)
        svc.upsert_face_embedding("EMP001", _unit_vec(0))

        result = svc.search_similar_face(_unit_vec(0))
        assert result["match"] == "EMP001"
        assert result["score"] == pytest.approx(1.0)

    def test_orthogonal_vector_does_not_match(self):
        """Cosine similarity of orthogonal unit vectors is 0 — below any positive threshold."""
        svc = _service(threshold=0.5)
        svc.upsert_face_embedding("EMP001", _unit_vec(0))

        result = svc.search_similar_face(_unit_vec(1))
        assert result["match"] is None

    def test_best_match_selected_from_multiple_employees(self):
        svc = _service(threshold=0.5)
        svc.upsert_face_embedding("EMP001", _unit_vec(0))
        svc.upsert_face_embedding("EMP002", _unit_vec(1))
        svc.upsert_face_embedding("EMP003", _unit_vec(2))

        result = svc.search_similar_face(_unit_vec(1))
        assert result["match"] == "EMP002"

    def test_score_zero_returned_when_below_threshold(self):
        svc = _service(threshold=0.99)
        # Orthogonal vectors have cosine similarity == 0, which is below any positive threshold
        svc.upsert_face_embedding("EMP001", _unit_vec(0))

        result = svc.search_similar_face(_unit_vec(3))
        assert result["match"] is None
        assert result["score"] == 0.0

    def test_search_wrong_dimensions_raises(self):
        svc = _service()
        with pytest.raises(ValueError, match="dimensions"):
            svc.search_similar_face([0.5, 0.5])  # 2 != DIMS


# ---------------------------------------------------------------------------
# search_similar_face — score is clamped non-negative
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearchScoreClamping:
    def test_score_is_never_negative(self):
        svc = _service(threshold=0.0)  # always match
        svc.upsert_face_embedding("EMP001", _unit_vec(0))

        result = svc.search_similar_face(_unit_vec(0))
        assert result["score"] >= 0.0
