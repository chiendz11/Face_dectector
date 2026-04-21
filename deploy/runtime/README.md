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

- `MINIO_PUBLIC_ENDPOINT` is rewritten during `ArgoCD Bootstrap` after the Kubernetes load balancer hostname is known.
- Keep `DATABASE_URL` aligned with `POSTGRES_*` values if you manage both explicitly.
- For staging and production, prefer storing the real values only in GitHub Secrets and AWS SSM, not in Git.

## External Secrets later

These templates remain useful even if you later move from bootstrap-created Kubernetes secrets to External Secrets Operator.

The recommended migration path is:

1. Keep `STAGING_BACKEND_ENV_FILE` and `PRODUCTION_BACKEND_ENV_FILE` as the CI/CD materialization source.
2. Continue syncing values into SSM under `/facedetector/<environment>/...`.
3. Replace the bootstrap-generated `face-detector-env` secret with an `ExternalSecret` that targets the same secret name.
4. Leave backend and worker deployments unchanged, because they already consume `face-detector-env`.