# Terraform SSM Parameter Management

This Terraform module reads backend runtime values from a `.env`-style file and writes them into AWS SSM Parameter Store under `/facedetector/<environment>/`.

By default, parameters are stored as `SecureString`, which is the safer default for deployed environments.

## Requirements

- Terraform 1.5+ installed
- AWS CLI configured with credentials that have permission to create and delete SSM parameters

## Usage

From `terraform/ssm`:

```bash
terraform init
terraform plan -var='environment=staging'
terraform apply -var='environment=staging'
```

For production:

```bash
terraform plan -var='environment=production'
terraform apply -var='environment=production'
```

You can also point Terraform at a non-committed runtime env file:

```bash
terraform plan -var='environment=staging' -var='env_file_path=../../.backend-runtime.staging.env'
terraform apply -var='environment=staging' -var='env_file_path=../../.backend-runtime.staging.env'
```

If you want to use a customer-managed KMS key for `SecureString` parameters:

```bash
terraform plan \
	-var='environment=staging' \
	-var='env_file_path=../../.backend-runtime.staging.env' \
	-var='kms_key_id=arn:aws:kms:ap-southeast-1:123456789012:key/abcd-1234'
```

## Notes

- By default the module reads `deploy/runtime/backend.staging.env.example` or `deploy/runtime/backend.production.env.example`.
- In CI/CD you should prefer passing `env_file_path` that points to a materialized secret-backed env file rather than storing runtime values in Git.
- Parameters are stored as `SecureString` by default. Set `parameter_type=String` only for local experiments or if you explicitly want plaintext SSM values.
- When `kms_key_id` is unset, SSM uses the AWS managed key. A customer-managed KMS key is the next step if you need tighter audit and key-rotation policy.
- It overwrites existing parameters with the same name.

## External Secrets migration path

The current flow uses GitHub Actions to materialize a backend runtime env file, sync it to SSM, then generate a Kubernetes secret during `ArgoCD Bootstrap`.

If you later move to External Secrets Operator, the clean migration path is:

1. Keep the SSM path convention `/facedetector/<environment>/<KEY>` unchanged.
2. Install External Secrets Operator in the cluster using IRSA or another workload identity mechanism.
3. Create a `SecretStore` or `ClusterSecretStore` that can read from AWS SSM.
4. Replace the bootstrap step that creates `face-detector-env` with an `ExternalSecret` manifest that targets the same secret name.
5. Keep the backend and worker deployments unchanged, because they already read from `envFrom.secretRef.name = face-detector-env`.
