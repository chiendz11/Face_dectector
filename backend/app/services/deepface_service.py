import logging
import os
from hashlib import sha256
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None

from app.core.config import MODEL_EMBEDDING_DIMENSIONS, settings

logger = logging.getLogger(__name__)
DeepFace: Any | None = None

class DeepFaceService:
    def __init__(
        self,
        embedding_dimensions: int | None = None,
        model_name: str | None = None,
        detector_backend: str | None = None,
        align: bool | None = None,
        enforce_detection: bool | None = None,
        provider: str | None = None,
        allow_hash_fallback: bool | None = None,
    ) -> None:
        self.provider = (provider or settings.embedding_provider).strip().lower()
        self.model_name = model_name or settings.model_name
        self.embedding_dimensions = embedding_dimensions
        if self.embedding_dimensions is None:
            self.embedding_dimensions = settings.embedding_dimensions

        self.detector_backend = detector_backend or settings.deepface_detector_backend
        self.align = settings.deepface_align if align is None else align
        self.enforce_detection = (
            settings.deepface_enforce_detection
            if enforce_detection is None
            else enforce_detection
        )
        self.allow_hash_fallback = (
            settings.embedding_allow_hash_fallback
            if allow_hash_fallback is None
            else allow_hash_fallback
        )

        if self.provider not in {"deepface", "hash"}:
            raise ValueError("EMBEDDING_PROVIDER must be one of: deepface, hash")

        if self.provider == "deepface":
            self._validate_model_dimensions()

    def embed_face(self, image_bytes: bytes, enforce_detection: bool | None = None) -> list[float]:
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        if self.provider == "hash":
            return self._hash_embedding(image_bytes)

        try:
            return self._deepface_embedding(image_bytes, enforce_detection=enforce_detection)
        except ValueError:
            raise
        except Exception as exc:
            if self.allow_hash_fallback:
                logger.warning(
                    "DeepFace embedding failed; falling back to hashed embedding because "
                    "EMBEDDING_ALLOW_HASH_FALLBACK is enabled: %s",
                    exc,
                )
                return self._hash_embedding(image_bytes)
            raise RuntimeError(
                "DeepFace embedding failed. Check model dependencies, model download "
                "access, image validity, and EMBEDDING_DIMENSIONS."
            ) from exc

    def _deepface_embedding(
        self,
        image_bytes: bytes,
        enforce_detection: bool | None = None,
    ) -> list[float]:
        deepface = _load_deepface()
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV and numpy are required for DeepFace embeddings")

        image = self._decode_image(image_bytes)
        representation = deepface.represent(
            img_path=image,
            model_name=self.model_name,
            detector_backend=self.detector_backend,
            align=self.align,
            enforce_detection=(
                self.enforce_detection
                if enforce_detection is None
                else enforce_detection
            ),
        )
        embedding = self._extract_embedding(representation)
        self._validate_embedding_dimensions(embedding)
        return embedding

    def _decode_image(self, image_bytes: bytes):
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV and numpy are required for DeepFace image decoding")

        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("image_bytes must be a valid image")

        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def _extract_embedding(self, representation: Any) -> list[float]:
        if hasattr(representation, "tolist"):
            representation = representation.tolist()

        if isinstance(representation, list):
            if not representation:
                raise ValueError("DeepFace returned no face embeddings")
            first = representation[0]
            if isinstance(first, dict):
                if len(representation) != 1:
                    raise ValueError("image must contain exactly one face")
                representation = first.get("embedding", [])
            elif isinstance(first, list):
                if len(representation) != 1:
                    raise ValueError("image must contain exactly one face")
                representation = first
        elif isinstance(representation, dict):
            representation = representation.get("embedding", [])

        if hasattr(representation, "tolist"):
            representation = representation.tolist()

        embedding = [float(value) for value in representation]
        if not embedding:
            raise ValueError("DeepFace returned an empty embedding")
        return embedding

    def _validate_model_dimensions(self) -> None:
        expected_dimensions = MODEL_EMBEDDING_DIMENSIONS.get(self.model_name)
        if expected_dimensions is None:
            return
        if expected_dimensions != self.embedding_dimensions:
            raise ValueError(
                f"MODEL_NAME={self.model_name} returns {expected_dimensions} dimensions; "
                f"set EMBEDDING_DIMENSIONS={expected_dimensions}."
            )

    def _validate_embedding_dimensions(self, embedding: list[float]) -> None:
        if len(embedding) != self.embedding_dimensions:
            raise ValueError(
                f"embedding dimensions must match EMBEDDING_DIMENSIONS="
                f"{self.embedding_dimensions}; got {len(embedding)}"
            )

    def _hash_embedding(self, image_bytes: bytes) -> list[float]:
        digest = sha256(image_bytes).digest()
        embedding: list[float] = []

        for index in range(self.embedding_dimensions):
            byte_value = digest[index % len(digest)]
            normalized_value = round((byte_value / 127.5) - 1.0, 6)
            embedding.append(normalized_value)

        return embedding


def _load_deepface() -> Any:
    global DeepFace
    if DeepFace is not None:
        return DeepFace

    try:
        from deepface import DeepFace as deepface_client
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("deepface is not installed") from exc

    DeepFace = deepface_client
    return DeepFace
