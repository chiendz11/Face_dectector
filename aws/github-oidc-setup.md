# GitHub OIDC Setup For Infrastructure Workflows

This repository now assumes AWS roles through GitHub OIDC instead of storing long-lived `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets.

The enterprise invariant in this repository is default-branch anchoring, not blind trust in contributor branches. Today the GitHub repository default branch is still `master`, so the concrete workflow references in this repository use `@refs/heads/master`. If you rename the default branch to `main`, update the pinned reusable workflow refs and the AWS trust policy strings from `master` to `main`.

## Required AWS roles

Create three IAM roles in the shared AWS account:

- `Role-Sandbox`: used by the main-controlled developer sandbox lane and the privileged `devops/*` verification lane for sandbox `plan`, `apply`, `destroy`, and sandbox bootstrap.
- `Role-Staging`: used by the default branch for shared staging `apply` and staging bootstrap.
- `Role-Prod`: used by the default branch for production `apply` and production bootstrap.

If you enable the third workflow R&D lane, add one more role:

- `Role-Workflow-RD`: used only by the `Sandbox Workflow R&D` lane from `devops/*` branches. This role should live in a burner or otherwise isolated AWS account whenever possible and should not have connectivity to the shared sandbox, staging, or production blast radius.

Use these trust policy templates as the starting point:

- `aws/github-oidc-trust-policy-sandbox.json`
- `aws/github-oidc-trust-policy-staging.json`
- `aws/github-oidc-trust-policy-production.json`
- `aws/github-oidc-trust-policy-workflow-rd.json` for the optional workflow R&D role

The sandbox trust policy intentionally trusts only the approved workflow path plus the approved lane context. In the strict enterprise mode, AWS matches a customized GitHub OIDC `sub` that includes `repo`, `context`, and `job_workflow_ref`.

That pattern keeps `feature/*` and every other ad hoc branch out of AWS trust. Developer PRs still work because the parent workflows live on the default branch and call reusable child workflows from there. The `devops/*` allowance is the permanent admin lane for validating Terraform and application changes against AWS, but the child workflow identity is still borrowed from the default branch.

The workflow R&D lane is intentionally different: it uses local reusable child workflows from the selected `devops/*` branch so you can validate workflow changes themselves. That is why it must assume a separate AWS role from `aws/github-oidc-trust-policy-workflow-rd.json` rather than reusing the normal sandbox role.

For AWS, prefer matching a customized `sub` that contains `job_workflow_ref`. Do not rely on a standalone `token.actions.githubusercontent.com:job_workflow_ref` IAM condition unless you have verified that exact pattern in your own AWS account. The portable and well-documented path for AWS is to encode `job_workflow_ref` into `sub` and match `sub` only.

Replace these placeholders before creating the roles:

- `${AWS_ACCOUNT_ID}`
- `${GITHUB_OWNER}`
- `${GITHUB_REPO}`

## GitHub configuration

Repository variables:

- `STAGING_EKS_CLUSTER_NAME`, `PRODUCTION_EKS_CLUSTER_NAME`
- `STAGING_SNAPSHOT_BUCKET_NAME`, `PRODUCTION_SNAPSHOT_BUCKET_NAME`
- `SANDBOX_EKS_CLUSTER_PREFIX` optional, defaults to `face-detector-sbx`
- `SANDBOX_SNAPSHOT_BUCKET_PREFIX` optional, defaults to `face-detector-sbx`
- `STAGING_NODE_*`, `PRODUCTION_NODE_*`
- `SANDBOX_NODE_INSTANCE_TYPE`, `SANDBOX_NODE_MIN_SIZE`, `SANDBOX_NODE_MAX_SIZE`, `SANDBOX_NODE_DESIRED_SIZE` optional
- `SSM_KMS_KEY_ID` optional
- `DEVOPS_ADMIN_ALLOWED_ACTORS_JSON` required for the DevOps infra lane. Set it to a JSON array such as `["devops-a", "devops-b"]`.
- `WORKFLOW_RD_ALLOWED_ACTORS_JSON` required for the workflow R&D lane. Set it to a JSON array of the GitHub logins allowed to exercise unsafe workflow changes.
- `AWS_ROLE_WORKFLOW_RD_ARN` required only when you enable the workflow R&D lane.

Repository secrets:

- `AWS_ROLE_SANDBOX_ARN` preferred. You can keep a repository variable fallback during migration, but the sensitive ARN should move to a secret.
- `AWS_ROLE_STAGING_ARN` preferred. You can keep a repository variable fallback during migration, but the sensitive ARN should move to a secret.
- `AWS_ROLE_PRODUCTION_ARN` preferred. You can keep a repository variable fallback during migration, but the sensitive ARN should move to a secret.
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

## GitHub guardrails

- Add a branch protection or ruleset that lets only the DevOps maintainers create or push `devops/*` branches.
- Add `CODEOWNERS` protection for `.github/workflows/*` and `aws/github-oidc-*` so those files require explicit DevOps approval once you have more than one maintainer.
- Create a GitHub Environment named `devops-admin-sandbox` and put the required reviewers for the DevOps infra lane there.
- Create a separate GitHub Environment named `workflow-rd` and put the stricter required reviewers for workflow experiments there.
- If the current GitHub plan does not support required environment reviewers or repository rulesets, treat the open `devops/*` pull request plus at least one approving review from another maintainer as the compensating control. The manual DevOps and workflow R&D lanes in this repository enforce that review path before they run.
- If you later move the AWS role ARN secrets into a GitHub Environment such as `Sandbox-Internal`, remember that GitHub's default OIDC `sub` claim changes to `repo:<owner>/<repo>:environment:<environment-name>` for jobs that reference an environment. In that mode, the AWS trust policy must match the environment subject, or you must customize the OIDC subject template. Keep the branch-pattern trust policy only when the AWS-auth job does not reference a GitHub Environment.

Use `aws/iam-policy-workflow-rd.json` as the starting point for the `Role-Workflow-RD` permissions policy. It is intentionally narrower than `AdministratorAccess` and only keeps the AWS service families used by the sandbox infrastructure and bootstrap workflows.

## Strict External Setup Runbook

Use this runbook when you want the enterprise-tight mode where AWS trusts both the lane context and the reusable workflow path.

### 1. Capture the exact OIDC claims before changing AWS

Create a temporary debug workflow or temporarily add `github/actions-oidc-debugger` to a non-production branch so you can inspect the exact `sub`, `ref`, `event_name`, and `job_workflow_ref` values emitted by both lanes.

Run and record these two cases:

- Developer lane: open a same-repo PR, add `deploy-sandbox`, and observe the OIDC token emitted inside the called reusable workflow.
- DevOps lane: manually dispatch `Sandbox DevOps Verify` from a `devops/*` branch and observe the OIDC token emitted inside the called reusable workflow.

Do not update AWS trust until you have the exact strings from your repository. The critical value is the final `sub` after customization, not what you expect it to be.

### 2. Back up the current repository OIDC subject template

Use a token with repository `Actions: write` permission.

```bash
gh api \
	-H "Accept: application/vnd.github+json" \
	/repos/OWNER/REPO/actions/oidc/customization/sub
```

If you are still on the default template, the response will usually look like this:

```json
{
	"use_default": true
}
```

### 3. Customize the GitHub OIDC `sub` template

Set the repository to emit `repo`, `context`, and `job_workflow_ref` inside `sub`.

```bash
gh api \
	--method PUT \
	-H "Accept: application/vnd.github+json" \
	/repos/OWNER/REPO/actions/oidc/customization/sub \
	--input - <<'JSON'
{
	"use_default": false,
	"include_claim_keys": [
		"repo",
		"context",
		"job_workflow_ref"
	]
}
JSON
```

Verify the template after the update:

```bash
gh api \
	-H "Accept: application/vnd.github+json" \
	/repos/OWNER/REPO/actions/oidc/customization/sub
```

The response should now contain:

```json
{
	"use_default": false,
	"include_claim_keys": [
		"repo",
		"context",
		"job_workflow_ref"
	]
}
```

### 4. Apply the default-branch-anchored three-lane model

This repository now targets one recommended enterprise model:

- Developer lane: `pull_request_target` parent workflows come from the default branch, and their local reusable child workflows are therefore also trusted from the default branch.
- DevOps infra lane: the manual `devops/*` parent workflow explicitly calls the child workflows pinned to the default branch so AWS still sees the approved workflow identity. GitHub-side approval is gated by the `devops-admin-sandbox` environment and the `DEVOPS_ADMIN_ALLOWED_ACTORS_JSON` allowlist.
- Workflow R&D lane: the manual `devops/*` parent workflow calls the local reusable child workflows from the selected branch so you can validate workflow changes themselves. GitHub-side approval is gated by the `workflow-rd` environment and the `WORKFLOW_RD_ALLOWED_ACTORS_JSON` allowlist, and AWS trust is isolated to `Role-Workflow-RD`.

Today that means `@refs/heads/master`. After a future default-branch rename, the same pattern becomes `@refs/heads/main`.

There is one rollout dependency you should expect: the default branch must already contain the reusable child workflows with `workflow_call` before the pinned DevOps manual lane clears all GitHub validation. Until that merge lands on the default branch, local editors can report that the referenced reusable workflow does not define `workflow_call`.

There is also one parent-workflow dependency to plan for: `workflow_dispatch` workflows only become callable once the workflow file itself exists on the default branch. In this repository, that means `Sandbox DevOps Verify` and `Sandbox Workflow R&D` need a landing commit on `master` before you can exercise them from the Actions UI against `devops/*` branches.

### 5. Update the AWS sandbox role trust policy

After you have the exact claim strings from step 1, update the role trust relationship. For AWS, match only `aud` and the customized `sub`.

Example for the strict default-branch mode in this repository today:

```json
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Effect": "Allow",
			"Principal": {
				"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
			},
			"Action": "sts:AssumeRoleWithWebIdentity",
			"Condition": {
				"StringEquals": {
					"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
				},
				"StringLike": {
					"token.actions.githubusercontent.com:sub": [
						"repo:OWNER/REPO:pull_request:job_workflow_ref:OWNER/REPO/.github/workflows/infrastructure.yml@refs/heads/master",
						"repo:OWNER/REPO:pull_request:job_workflow_ref:OWNER/REPO/.github/workflows/app-cd.yml@refs/heads/master",
						"repo:OWNER/REPO:pull_request:job_workflow_ref:OWNER/REPO/.github/workflows/terraform-plan-reusable.yml@refs/heads/master",
						"repo:OWNER/REPO:ref:refs/heads/devops/*:job_workflow_ref:OWNER/REPO/.github/workflows/infrastructure.yml@refs/heads/master",
						"repo:OWNER/REPO:ref:refs/heads/devops/*:job_workflow_ref:OWNER/REPO/.github/workflows/app-cd.yml@refs/heads/master"
					]
				}
			}
		}
	]
}
```

If you later rename the default branch to `main`, replace `refs/heads/master` with `refs/heads/main` in both the reusable workflow pin and the AWS trust strings.

Replace `OWNER`, `REPO`, and the AWS account ID with your actual values. Use the exact `sub` strings from the debugger rather than inventing them.

If you want AWS itself to enforce the DevOps actor allowlist in addition to the GitHub-side allowlists in this repository, add `actor` to the customized subject template, then update every affected AWS trust policy to match the new `sub` shape. Keep that as a second hardening pass because it affects sandbox, staging, production, and workflow R&D roles together.

### 6. Apply GitHub branch restrictions

Outside the repository code, create a ruleset or branch protection rule that:

- restricts who can create or push `devops/*`
- requires pull requests for `main`
- optionally requires status checks for the sandbox parent workflows

If you later have more maintainers, then also enforce `CODEOWNERS` review on `.github/workflows/*` and `aws/github-oidc-*`.

### 7. Apply an AWS permission boundary for sandbox roles

Use a permission boundary on the role or on any IAM roles Terraform creates for sandbox workloads. The boundary should at minimum:

- deny access to production-tagged resources
- deny creating resources without your required sandbox tags
- deny destructive operations outside the sandbox naming or tag namespace

Typical mandatory tags are:

- `Environment=sandbox`
- `ManagedBy=github-actions`
- `Lane=developer` or `Lane=admin`
- `Owner=<github-login>`

The goal is simple: even if the role is assumed successfully, the boundary still prevents any operation outside the sandbox blast radius.

### 8. Roll out in this order

Apply changes in this sequence to avoid breaking active workflows:

1. Add the debugger and capture current claims.
2. Prepare the new AWS trust policy but do not save it yet.
3. Update the GitHub OIDC subject template.
4. Re-run the debugger to capture the new `sub` values.
5. Paste those exact `sub` values into the AWS trust policy.
6. Save the AWS trust policy.
7. Test the Developer lane.
8. Test the DevOps manual lane.

### 9. Rollback

If anything fails, reset the repository to the default GitHub subject template:

```bash
gh api \
	--method PUT \
	-H "Accept: application/vnd.github+json" \
	/repos/OWNER/REPO/actions/oidc/customization/sub \
	--input - <<'JSON'
{
	"use_default": true
}
JSON
```

Then restore the simpler branch-based AWS trust policy from `aws/github-oidc-trust-policy-sandbox.json`.

## Workflow behavior

- `Terraform PR Plan` is now a main-controlled `pull_request_target` parent that calls a reusable child workflow, so the AWS trust decision is anchored on the trusted workflow definition rather than the contributor branch.
- `Infrastructure Management` accepts `sandbox`, `staging`, or `production`.
- `sandbox` runs are allowed only for same-repo pull request head branches and may `apply` or `destroy`.
- `staging` and `production` runs are allowed only from the default branch and only with `action=apply`.
- Shared staging and production reject manual cluster, bucket, and node-size overrides to protect the canonical environments.
- `ArgoCD Bootstrap` accepts an optional `cluster_name` input for manual shared-environment operations, but sandbox identity is now derived from the PR number and is not manually overridden.
- Developer sandbox automation runs only from default-branch parents on `pull_request_target`, while the separate `Sandbox DevOps Verify` workflow is reserved for `devops/*` branches.
- `Sandbox DevOps Verify` is a manual-dispatch admin lane. Select a `devops/*` branch in the Actions UI, then run `apply` to create the admin sandbox or `destroy` to tear it down. The parent workflow comes from the selected `devops/*` branch, but the child infrastructure and bootstrap workflows are pinned to the default branch so AWS sees the approved workflow identity.
- `Sandbox Workflow R&D` is the unsafe workflow-testing lane. Select a `devops/*` branch in the Actions UI, pass the `workflow-rd` environment gate, and the parent workflow will call the branch-local child workflows so you can test workflow edits without teaching the normal sandbox role to trust arbitrary workflow refs.
- Developer sandbox state lives under `sandboxes/pr-<number>/...` and SSM parameters live under `/facedetector/sandbox/pr-<number>/...`.
- DevOps manual sandbox state lives under `admin-previews/<owner>/<branch>/...` and SSM parameters live under `/facedetector/admin/<owner>/<branch>/...`.

## Solo operator guidance

If you are running the repository solo, keep the same two-lane model.

- Use `feature/*` or `dev/*` branches for application work and let the automatic PR-driven sandbox flow behave like it would for a larger team.
- Use `devops/*` branches only when you are changing Terraform, workflow orchestration, OIDC, or other platform code, then validate those changes through the manual `Sandbox DevOps Verify` lane before merging.
- Keep a `CODEOWNERS` file as documentation if you want, but do not enable a blocking “require code owner review” rule until there is a second maintainer, or you will create unnecessary merge friction for yourself.

## IAM scope guidance

The three GitHub roles do not need identical permissions.

- `Role-Sandbox` should be allowed to create and destroy the lab EKS, RDS, ElastiCache, S3, IAM, and SSM resources used by the Terraform modules.
- `Role-Staging` should be limited to the shared staging resources and should not have `destroy` paths exposed by workflow policy.
- `Role-Prod` should be tighter still and typically require environment protection or manual approvals in GitHub before production apply.

In a student or solo-project setup it is acceptable to start with broad Terraform execution permissions for `Role-Sandbox` and tighten them later, but do not keep long-lived IAM user credentials in GitHub once OIDC is configured.