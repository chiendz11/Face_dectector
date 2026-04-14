import mimetypes
from urllib.parse import quote

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None

from app.utils.resilience import CircuitBreaker, retry_operation


class MinioService:
    def __init__(
        self,
        bucket_name: str = "face-snapshots",
        endpoint: str = "minio:9000",
        aws_s3_bucket: str | None = None,
        aws_s3_region: str | None = None,
        s3_retry_attempts: int = 3,
        s3_retry_backoff_seconds: float = 1.0,
        s3_circuit_failure_threshold: int = 5,
        s3_circuit_recovery_seconds: int = 30,
    ) -> None:
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.aws_s3_bucket = aws_s3_bucket
        self.aws_s3_region = aws_s3_region
        self._uploaded_objects: dict[str, bytes] = {}
        self._s3_client = None
        self._retry_attempts = s3_retry_attempts
        self._retry_backoff_seconds = s3_retry_backoff_seconds
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=s3_circuit_failure_threshold,
            recovery_timeout=s3_circuit_recovery_seconds,
            exceptions=(Exception,),
        )

        self._default_content_type = "application/octet-stream"
        self._region = aws_s3_region or "us-east-1"

        if self.aws_s3_bucket and boto3 is None:
            raise RuntimeError("boto3 is required to upload snapshots to AWS S3")

    def upload_snapshot(self, object_name: str, image_bytes: bytes) -> str:
        normalized_name = object_name.strip().lstrip("/")

        if not normalized_name:
            raise ValueError("object_name must not be empty")
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        local_url = self._upload_to_local(normalized_name, image_bytes)

        if self.aws_s3_bucket:
            # Keep local MinIO as the fast cache / local store,
            # and also persist a copy to AWS S3 for backup/archive.
            self._upload_to_s3(normalized_name, image_bytes)

        return local_url

    def _upload_to_local(self, normalized_name: str, image_bytes: bytes) -> str:
        self._uploaded_objects[normalized_name] = image_bytes

        endpoint = self.endpoint.rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        escaped_name = quote(normalized_name, safe="/.-_")
        return f"{endpoint}/{self.bucket_name}/{escaped_name}"

    def _upload_to_s3(self, normalized_name: str, image_bytes: bytes) -> str:
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.aws_s3_region)

        content_type, _ = mimetypes.guess_type(normalized_name)

        @retry_operation(
            max_attempts=self._retry_attempts,
            initial_delay=self._retry_backoff_seconds,
        )
        def attempt_upload() -> None:
            self._s3_client.put_object(
                Bucket=self.aws_s3_bucket,
                Key=normalized_name,
                Body=image_bytes,
                ContentType=content_type or self._default_content_type,
            )

        self._circuit_breaker.call(attempt_upload)

        escaped_name = quote(normalized_name, safe="/.-_")
        return f"https://{self.aws_s3_bucket}.s3.{self._region}.amazonaws.com/{escaped_name}"
