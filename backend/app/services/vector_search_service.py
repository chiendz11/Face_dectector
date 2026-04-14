from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import FaceEmbedding
from app.utils.resilience import CircuitBreaker, retry_operation

DB_CIRCUIT_BREAKER = CircuitBreaker(
    failure_threshold=settings.db_circuit_failure_threshold,
    recovery_timeout=settings.db_circuit_recovery_seconds,
    exceptions=(Exception,),
)


class VectorSearchService:
    """Vector search / embedding persistence abstraction.

    This service historically mirrored a Qdrant integration interface, but the
    current implementation supports PostgreSQL + pgvector or an in-memory fallback.
    """

    def __init__(
        self,
        db: Session | None = None,
        read_db: Session | None = None,
        match_threshold: float = 0.35,
        embedding_dimensions: int = 16,
    ) -> None:
        self.db = db
        self.read_db = read_db or db
        self.match_threshold = match_threshold
        self.embedding_dimensions = embedding_dimensions
        self._stored_embeddings: dict[str, dict] = {}

    def upsert_face_embedding(
        self,
        employee_code: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> dict:
        normalized_code = employee_code.strip().upper()
        self._validate_embedding(embedding)

        if not normalized_code:
            raise ValueError("employee_code must not be empty")

        payload = {
            "employee_code": normalized_code,
            "embedding": embedding,
            "metadata": metadata or {},
        }

        if self.db is not None:
            existing = (
                self.db.query(FaceEmbedding)
                .filter(FaceEmbedding.employee_code == normalized_code)
                .first()
            )
            if existing is None:
                existing = FaceEmbedding(
                    employee_code=normalized_code,
                    embedding=embedding,
                    metadata=metadata or {},
                )
                self.db.add(existing)
            else:
                existing.embedding = embedding
                existing.metadata = metadata or {}

            @retry_operation(
                max_attempts=settings.db_retry_attempts,
                initial_delay=settings.db_retry_backoff_seconds,
            )
            def attempt_commit() -> None:
                self.db.commit()

            DB_CIRCUIT_BREAKER.call(attempt_commit)
            return payload

        self._stored_embeddings[normalized_code] = payload
        return payload

    def search_similar_face(self, embedding: list[float]) -> dict:
        self._validate_embedding(embedding)

        if self.read_db is not None:
            def query_best_match() -> dict:
                statement = (
                    select(FaceEmbedding)
                    .order_by(FaceEmbedding.embedding.cosine_distance(embedding))
                    .limit(1)
                )
                result = self.read_db.execute(statement).scalar_one_or_none()
                if result is None:
                    return {"match": None, "score": 0.0, "metadata": None}

                distance = result.embedding.cosine_distance(embedding)
                confidence = round(max(0.0, 1.0 - float(distance)), 6)
                if confidence < self.match_threshold:
                    return {"match": None, "score": 0.0, "metadata": None}

                return {
                    "match": result.employee_code,
                    "score": confidence,
                    "metadata": result.metadata,
                }

            return DB_CIRCUIT_BREAKER.call(
                retry_operation(
                    max_attempts=settings.db_retry_attempts,
                    initial_delay=settings.db_retry_backoff_seconds,
                )(query_best_match)
            )

        if not self._stored_embeddings:
            return {"match": None, "score": 0.0, "metadata": None}

        best_match: dict | None = None
        best_score = -1.0

        for payload in self._stored_embeddings.values():
            score = self._cosine_similarity(embedding, payload["embedding"])
            if score > best_score:
                best_score = score
                best_match = payload

        if best_match is None or best_score < self.match_threshold:
            return {"match": None, "score": round(max(best_score, 0.0), 6), "metadata": None}

        return {
            "match": best_match["employee_code"],
            "score": round(best_score, 6),
            "metadata": best_match["metadata"],
        }

    def _validate_embedding(self, embedding: list[float]) -> None:
        if not embedding:
            raise ValueError("embedding must not be empty")

        if len(embedding) != self.embedding_dimensions:
            raise ValueError("embedding dimensions must match")

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            raise ValueError("embedding dimensions must match")

        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))

        if left_norm == 0 or right_norm == 0:
            raise ValueError("embedding norm must not be zero")

        dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
        return dot_product / (left_norm * right_norm)
