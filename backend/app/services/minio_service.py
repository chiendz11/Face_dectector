class MinioService:
    def upload_snapshot(self, object_name: str, image_bytes: bytes) -> str:
        # Replace this stub with a real MinIO upload.
        return f"s3://face-snapshots/{object_name}"
