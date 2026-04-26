# GitHub OIDC Setup For Infrastructure Workflows

This repository now assumes AWS roles through GitHub OIDC instead of storing long-lived `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets.

## Required AWS roles

Create three IAM roles in the shared AWS account:

- `Role-Sandbox`: used by feature branches for sandbox `plan`, `apply`, `destroy`, and sandbox bootstrap.
- `Role-Staging`: used by the default branch for shared staging `apply` and staging bootstrap.
- `Role-Prod`: used by the default branch for production `apply` and production bootstrap.

Use these trust policy templates as the starting point:

- `aws/github-oidc-trust-policy-sandbox.json`
- `aws/github-oidc-trust-policy-staging.json`
- `aws/github-oidc-trust-policy-production.json`

Replace these placeholders before creating the roles:

- `${AWS_ACCOUNT_ID}`
- `${GITHUB_OWNER}`
- `${GITHUB_REPO}`

## GitHub configuration

Repository variables:

- `AWS_ROLE_SANDBOX_ARN`
- `AWS_ROLE_STAGING_ARN`
- `AWS_ROLE_PRODUCTION_ARN`
- `STAGING_EKS_CLUSTER_NAME`, `PRODUCTION_EKS_CLUSTER_NAME`
- `STAGING_SNAPSHOT_BUCKET_NAME`, `PRODUCTION_SNAPSHOT_BUCKET_NAME`
- `SANDBOX_EKS_CLUSTER_PREFIX` optional, defaults to `face-detector-sbx`
- `SANDBOX_SNAPSHOT_BUCKET_PREFIX` optional, defaults to `face-detector-sbx`
- `STAGING_NODE_*`, `PRODUCTION_NODE_*`
- `SANDBOX_NODE_INSTANCE_TYPE`, `SANDBOX_NODE_MIN_SIZE`, `SANDBOX_NODE_MAX_SIZE`, `SANDBOX_NODE_DESIRED_SIZE` optional
- `SSM_KMS_KEY_ID` optional

Repository secrets:

- `AWS_REGION`
- `TF_STATE_BUCKET`
- `TF_STATE_LOCK_TABLE`
- `TF_STATE_REGION`
- `STAGING_BACKEND_ENV_FILE`
- `PRODUCTION_BACKEND_ENV_FILE`
- `SANDBOX_BACKEND_ENV_FILE` optional. When unset, sandbox runs reuse the staging env contract.
- `ARGOCD_REPO_USERNAME`, `ARGOCD_REPO_TOKEN` optional
- `GHCR_USERNAME`, `GHCR_TOKEN` optional

After the OIDC roles work, delete these legacy secrets from GitHub:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Workflow behavior

- `Terraform PR Plan` runs on pull requests to `main` or `master`, derives a sandbox cluster name from the `feature/*` branch, assumes `Role-Sandbox`, and comments EKS plus SSM plan excerpts on the PR.
- `Infrastructure Management` accepts `sandbox`, `staging`, or `production`.
- `sandbox` runs are allowed only from `feature/*` branches and may `apply` or `destroy`.
- `staging` and `production` runs are allowed only from the default branch and only with `action=apply`.
- Shared staging and production reject manual cluster, bucket, and node-size overrides to protect the canonical environments.
- `ArgoCD Bootstrap` now accepts an optional `cluster_name` input so a feature branch can bootstrap its own sandbox cluster.
- Sandbox SSM parameters live under `/facedetector/sandbox/<cluster-name>/...`.

## IAM scope guidance

The three GitHub roles do not need identical permissions.

- `Role-Sandbox` should be allowed to create and destroy the lab EKS, RDS, ElastiCache, S3, IAM, and SSM resources used by the Terraform modules.
- `Role-Staging` should be limited to the shared staging resources and should not have `destroy` paths exposed by workflow policy.
- `Role-Prod` should be tighter still and typically require environment protection or manual approvals in GitHub before production apply.

In a student or solo-project setup it is acceptable to start with broad Terraform execution permissions for `Role-Sandbox` and tighten them later, but do not keep long-lived IAM user credentials in GitHub once OIDC is configured.