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
        public_endpoint: str = "http://localhost:9000",
        access_key: str | None = None,
        secret_key: str | None = None,
        use_s3_api: bool = False,
        aws_s3_bucket: str | None = None,
        aws_s3_region: str | None = None,
        aws_s3_presigned_url_expire_seconds: int = 3600,
        s3_retry_attempts: int = 3,
        s3_retry_backoff_seconds: float = 1.0,
        s3_circuit_failure_threshold: int = 5,
        s3_circuit_recovery_seconds: int = 30,
    ) -> None:
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.public_endpoint = public_endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.use_s3_api = use_s3_api
        self.aws_s3_bucket = aws_s3_bucket
        self.aws_s3_region = aws_s3_region
        self.aws_s3_presigned_url_expire_seconds = aws_s3_presigned_url_expire_seconds
        self._uploaded_objects: dict[str, bytes] = {}
        self._s3_client = None
        self._bucket_initialized = False
        self._retry_attempts = s3_retry_attempts
        self._retry_backoff_seconds = s3_retry_backoff_seconds
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=s3_circuit_failure_threshold,
            recovery_timeout=s3_circuit_recovery_seconds,
            exceptions=(Exception,),
        )

        self._default_content_type = "application/octet-stream"

        if (self.aws_s3_bucket or self.use_s3_api) and boto3 is None:
            raise RuntimeError("boto3 is required to upload snapshots to S3-compatible object storage")

        if self.use_s3_api and (not self.endpoint or not self.access_key or not self.secret_key):
            raise RuntimeError(
                "endpoint, access_key, and secret_key are required when MINIO_USE_S3_API is enabled"
            )

    def upload_snapshot(self, object_name: str, image_bytes: bytes) -> str:
        normalized_name = object_name.strip().lstrip("/")

        if not normalized_name:
            raise ValueError("object_name must not be empty")
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        if self.aws_s3_bucket:
            return self._upload_to_s3(normalized_name, image_bytes)

        if self.use_s3_api:
            return self._upload_to_local_s3(normalized_name, image_bytes)

        return self._upload_to_local(normalized_name, image_bytes)

    def _upload_to_local(self, normalized_name: str, image_bytes: bytes) -> str:
        self._uploaded_objects[normalized_name] = image_bytes

        if not self.public_endpoint:
            raise RuntimeError("MINIO_PUBLIC_ENDPOINT must be set when using local object storage")

        endpoint = self.public_endpoint.rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        escaped_name = quote(normalized_name, safe="/.-_")
        return f"{endpoint}/{self.bucket_name}/{escaped_name}"

    def _upload_to_local_s3(self, normalized_name: str, image_bytes: bytes) -> str:
        client = self._get_local_s3_client()
        self._ensure_bucket_exists(client, self.bucket_name)

        content_type, _ = mimetypes.guess_type(normalized_name)

        @retry_operation(
            max_attempts=self._retry_attempts,
            initial_delay=self._retry_backoff_seconds,
        )
        def attempt_upload() -> None:
            client.put_object(
                Bucket=self.bucket_name,
                Key=normalized_name,
                Body=image_bytes,
                ContentType=content_type or self._default_content_type,
            )

        self._circuit_breaker.call(attempt_upload)
        endpoint = self.public_endpoint or self._endpoint_url(self.endpoint)
        endpoint = endpoint.rstrip("/")
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
        return self._s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.aws_s3_bucket, "Key": normalized_name},
            ExpiresIn=self.aws_s3_presigned_url_expire_seconds,
        )

    def _get_local_s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url(self.endpoint),
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.aws_s3_region or "us-east-1",
            )
        return self._s3_client

    def _ensure_bucket_exists(self, client, bucket_name: str) -> None:
        if self._bucket_initialized:
            return

        try:
            client.head_bucket(Bucket=bucket_name)
        except Exception:
            client.create_bucket(Bucket=bucket_name)

        self._bucket_initialized = True

    @staticmethod
    def _endpoint_url(endpoint: str) -> str:
        normalized = endpoint.strip().rstrip("/")
        if normalized.startswith(("http://", "https://")):
            return normalized
        return f"http://{normalized}"
