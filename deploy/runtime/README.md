# Backend Runtime Templates

These files define the backend runtime configuration contract for deployed environments:

- `backend.staging.env.example`
- `backend.production.env.example`

They are intended to be used in two ways:

1. As the committed template that documents which backend runtime keys must exist.
2. As the starting point for the multiline GitHub Secrets `STAGING_BACKEND_ENV_FILE` and `PRODUCTION_BACKEND_ENV_FILE`.

## How to create the GitHub multiline secret

1. Copy the matching template file.
2. Replace every `change-me-*` placeholder with a real value.
3. Paste the full content into the GitHub Secret with the same environment name.

Notes:

- In cloud environments, `DATABASE_URL` should point to external PostgreSQL and `REDIS_URL` should point to external Redis or Valkey. The application Helm chart no longer deploys these stateful services inside EKS.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `REDIS_PASSWORD` are now the canonical secret inputs for managed AWS data services. The infrastructure workflow reads them to provision RDS and ElastiCache.
- `REDIS_ADDRESS` and `REDIS_PASSWORD` are included for worker autoscaling and should point to the same external Redis deployment used by Celery.
- `AWS_S3_BUCKET` is the primary object store for staging and production. Leave the `MINIO_*` values blank there unless you intentionally want a local fallback.
- These templates are backend-only. Edge device settings such as `API_BASE_URL`, `EDGE_DEVICE_NAME`, and `SCAN_INTERVAL_SECONDS` belong in `edge-client/.env.example` rather than the backend runtime contract.
- The current deployment expects edge devices to capture frames locally, crop faces on-device, and upload only face crops over HTTP. There is no centralized raw-video streaming pipeline in the backend runtime contract.
- `ArgoCD Bootstrap` rewrites `DATABASE_URL`, `REDIS_URL`, `REDIS_ADDRESS`, and `AWS_S3_BUCKET` from Terraform outputs before syncing the final runtime contract into SSM, so committed templates can stay generic.
- `AWS_S3_PRESIGNED_URL_EXPIRE_SECONDS` controls how long direct S3 download links remain valid after the backend uploads a snapshot.
- For staging and production, prefer storing the real values only in GitHub Secrets and AWS SSM, not in Git.

## External Secrets later

These templates remain useful even if you later move from bootstrap-created Kubernetes secrets to External Secrets Operator.

The recommended migration path is:

1. Keep `STAGING_BACKEND_ENV_FILE` and `PRODUCTION_BACKEND_ENV_FILE` as the CI/CD materialization source.
2. Continue syncing values into SSM under `/facedetector/<environment>/...`.
3. Replace the bootstrap-generated `face-detector-env` secret with an `ExternalSecret` that targets the same secret name.
4. Leave backend and worker deployments unchanged, because they already consume `face-detector-env`.