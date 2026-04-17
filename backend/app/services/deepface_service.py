import logging
from hashlib import sha256

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None

try:
    from deepface import DeepFace
except ImportError:  # pragma: no cover
    DeepFace = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepFaceService:
    def __init__(self, embedding_dimensions: int = 16) -> None:
        self.embedding_dimensions = embedding_dimensions
        self.model_name = settings.model_name
        self.detector_backend = "opencv"

    def embed_face(self, image_bytes: bytes) -> list[float]:
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        if DeepFace is not None and cv2 is not None and np is not None:
            try:
                image = self._decode_image(image_bytes)
                representation = DeepFace.represent(
                    img_path=image,
                    model_name=self.model_name,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                )
                if hasattr(representation, "tolist"):
                    representation = representation.tolist()

                if isinstance(representation, dict):
                    representation = representation.get("embedding", [])

                embedding = [float(value) for value in representation]
                if embedding:
                    return embedding
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "DeepFace embedding failed, falling back to hashed embedding: %s",
                    exc,
                )

        return self._hash_embedding(image_bytes)

    def _decode_image(self, image_bytes: bytes):
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV and numpy are required for DeepFace image decoding")

        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("image_bytes must be a valid image")

        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def _hash_embedding(self, image_bytes: bytes) -> list[float]:
        digest = sha256(image_bytes).digest()
        embedding: list[float] = []

        for index in range(self.embedding_dimensions):
            byte_value = digest[index % len(digest)]
            normalized_value = round((byte_value / 127.5) - 1.0, 6)
            embedding.append(normalized_value)

        return embedding
