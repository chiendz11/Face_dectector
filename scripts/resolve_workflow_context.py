#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request


def slugify(value: str, max_length: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    shortened = normalized[:max_length].rstrip("-")
    return shortened or "sandbox"


def require(value: str, message: str) -> str:
    if not value:
        raise SystemExit(message)
    return value


def short_git_sha(value: str) -> str:
    candidate = re.sub(r"[^0-9a-f]", "", value.lower())
    return candidate[:12]


def parse_pull_request_number(value: str) -> int | None:
    candidate = value.strip()
    if not candidate:
        return None

    if not candidate.isdigit() or int(candidate) <= 0:
        raise SystemExit(f"Invalid pull request number: {value}")

    return int(candidate)


def resolve_pull_request_number(
    explicit_value: str,
    ref_name: str,
    github_repository: str,
    github_token: str,
) -> int:
    explicit_number = parse_pull_request_number(explicit_value)
    if explicit_number is not None:
        return explicit_number

    pulls = list_open_pull_requests_for_ref(ref_name, github_repository, github_token)

    if not pulls:
        raise SystemExit(
            "Sandbox runs require an open PR. No open pull request was found for "
            f"branch {ref_name}."
        )

    if len(pulls) > 1:
        numbers = ", ".join(str(item.get("number", "?")) for item in pulls)
        raise SystemExit(
            "Sandbox runs require an unambiguous PR identity. Multiple open PRs were found for "
            f"branch {ref_name}: {numbers}."
        )

    return int(pulls[0]["number"])


def list_open_pull_requests_for_ref(
    ref_name: str,
    github_repository: str,
    github_token: str,
) -> list[dict]:

    repository = require(
        github_repository.strip(),
        "Sandbox runs require GITHUB_REPOSITORY so the PR number can be resolved.",
    )
    token = require(
        github_token.strip(),
        "Sandbox runs require GITHUB_TOKEN so the PR number can be resolved.",
    )

    owner, repo = repository.split("/", 1)
    encoded_head = urllib.parse.quote(f"{owner}:{ref_name}", safe="")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls?head={encoded_head}&state=open&per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "face-detector-resolve-workflow-context",
        },
    )

    with urllib.request.urlopen(request) as response:  # nosec B310
        return json.load(response)


def resolve_owner_login(
    explicit_value: str,
    ref_name: str,
    github_repository: str,
    github_token: str,
) -> str:
    if explicit_value.strip():
        return explicit_value.strip()

    pulls = list_open_pull_requests_for_ref(ref_name, github_repository, github_token)
    if len(pulls) == 1:
        return str(pulls[0].get("user", {}).get("login", "")).strip()

    return ""


def build_devops_sandbox_identity(owner_login: str, ref_name: str) -> tuple[str, str, str]:
    if not ref_name.startswith("devops/"):
        raise SystemExit(
            "Admin sandbox identities without a PR are reserved for devops/* branches. "
            f"Current ref is {ref_name}."
        )

    owner_slug = slugify(owner_login or "admin", 24)
    branch_label = ref_name.split("/", 1)[1].strip() or "sandbox"
    branch_slug = slugify(branch_label, 24)
    digest = hashlib.sha256(f"{owner_slug}:{ref_name}".encode("utf-8")).hexdigest()[:6]
    sandbox_key = f"admin-{owner_slug[:16]}-{digest}"
    branch_path = f"{branch_slug}-{digest}"
    return sandbox_key, owner_slug, branch_path


def resolve_sandbox_identity(
    explicit_pull_request_number: str,
    explicit_owner_login: str,
    ref_name: str,
    github_repository: str,
    github_token: str,
) -> tuple[int | None, str, str, str, str]:
    explicit_number = parse_pull_request_number(explicit_pull_request_number)
    explicit_owner = explicit_owner_login.strip()

    if explicit_number is not None:
        owner_login = explicit_owner or resolve_owner_login(
            "",
            ref_name,
            github_repository,
            github_token,
        )
        return explicit_number, owner_login, f"pr-{explicit_number}", "", ""

    if ref_name.startswith("devops/"):
        sandbox_key, owner_path, branch_path = build_devops_sandbox_identity(explicit_owner, ref_name)
        return None, explicit_owner, sandbox_key, owner_path, branch_path

    pulls = list_open_pull_requests_for_ref(ref_name, github_repository, github_token)
    if len(pulls) == 1:
        pull_request_number = int(pulls[0]["number"])
        owner_login = explicit_owner or str(pulls[0].get("user", {}).get("login", "")).strip()
        return pull_request_number, owner_login, f"pr-{pull_request_number}", "", ""

    if not pulls:
        raise SystemExit(
            "Sandbox runs require an open PR unless they are dispatched from a devops/* branch. "
            f"No open pull request was found for branch {ref_name}."
        )

    numbers = ", ".join(str(item.get("number", "?")) for item in pulls)
    raise SystemExit(
        "Sandbox runs require an unambiguous PR identity. Multiple open PRs were found for "
        f"branch {ref_name}: {numbers}."
    )


def is_default_branch(ref_name: str, default_branch: str) -> bool:
    return ref_name in {default_branch, "master"}


def is_release_ref(release_tag: str) -> bool:
    return bool(release_tag.strip())


def compute_env_version(
    environment: str,
    default_branch: str,
    identity: str,
    git_sha: str,
    release_tag: str,
) -> str:
    short_sha = short_git_sha(git_sha)
    if environment == "sandbox":
        return f"{identity}-{short_sha}" if short_sha else identity

    if environment == "staging":
        branch_label = slugify(default_branch or "master", 32)
        return f"{branch_label}-{short_sha}" if short_sha else branch_label

    release_version = release_tag.strip()
    if release_version:
        return release_version

    return f"production-{short_sha}" if short_sha else "production"


def emit_outputs(outputs: dict[str, str]) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        for key, value in outputs.items():
            print(f"{key}={value}")
        return

    with open(github_output, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}<<EOF\n{value}\nEOF\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["infrastructure", "bootstrap", "plan"], required=True)
    parser.add_argument("--environment", choices=["sandbox", "staging", "production"], required=True)
    parser.add_argument("--action", default="apply")
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--default-branch", default="master")
    parser.add_argument("--repository-id", default="0")
    parser.add_argument("--input-cluster-name", default="")
    parser.add_argument("--input-snapshot-bucket-name", default="")
    parser.add_argument("--input-node-instance-type", default="")
    parser.add_argument("--input-node-min-size", default="")
    parser.add_argument("--input-node-max-size", default="")
    parser.add_argument("--input-node-desired-size", default="")
    parser.add_argument("--input-git-revision", default="")
    parser.add_argument("--pull-request-number", default="")
    parser.add_argument("--owner-login", default="")
    parser.add_argument("--github-repository", default="")
    parser.add_argument("--github-token", default="")
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--staging-cluster-name", default="face-detector-staging")
    parser.add_argument("--production-cluster-name", default="face-detector-production")
    parser.add_argument("--sandbox-cluster-prefix", default="face-detector-sbx")
    parser.add_argument("--staging-snapshot-bucket-name", default="face-detector-employee-images-staging")
    parser.add_argument("--production-snapshot-bucket-name", default="face-detector-employee-images-production")
    parser.add_argument("--sandbox-snapshot-bucket-prefix", default="face-detector-sbx")
    parser.add_argument("--staging-node-instance-type", default="c7i-flex.large")
    parser.add_argument("--production-node-instance-type", default="m7i-flex.large")
    parser.add_argument("--sandbox-node-instance-type", default="c7i-flex.large")
    parser.add_argument("--staging-node-min-size", default="1")
    parser.add_argument("--staging-node-max-size", default="2")
    parser.add_argument("--staging-node-desired-size", default="1")
    parser.add_argument("--production-node-min-size", default="2")
    parser.add_argument("--production-node-max-size", default="6")
    parser.add_argument("--production-node-desired-size", default="2")
    parser.add_argument("--sandbox-node-min-size", default="1")
    parser.add_argument("--sandbox-node-max-size", default="2")
    parser.add_argument("--sandbox-node-desired-size", default="1")
    parser.add_argument("--role-sandbox-arn", default="")
    parser.add_argument("--role-staging-arn", default="")
    parser.add_argument("--role-production-arn", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_cluster_name = args.input_cluster_name.strip()
    input_snapshot_bucket_name = args.input_snapshot_bucket_name.strip()
    input_node_instance_type = args.input_node_instance_type.strip()
    input_node_min_size = args.input_node_min_size.strip()
    input_node_max_size = args.input_node_max_size.strip()
    input_node_desired_size = args.input_node_desired_size.strip()
    input_git_revision = args.input_git_revision.strip()
    git_sha = args.git_sha.strip()
    release_tag = args.release_tag.strip()
    owner_login = args.owner_login.strip()
    pull_request_number_output = ""
    sandbox_key = ""

    if args.environment == "sandbox":
        if is_default_branch(args.ref_name, args.default_branch):
            raise SystemExit(
                "Sandbox runs are allowed only from pull request head branches, not the default branch. "
                f"Current ref is {args.ref_name}."
            )
        if input_cluster_name:
            raise SystemExit(
                "Sandbox cluster_name overrides are disabled. Sandbox identity is derived from the PR number or devops branch identity."
            )
        if input_snapshot_bucket_name:
            raise SystemExit(
                "Sandbox snapshot_bucket_name overrides are disabled. Sandbox identity is derived from the PR number or devops branch identity."
            )

        pull_request_number, owner_login, sandbox_key, admin_owner_path, admin_branch_path = resolve_sandbox_identity(
            args.pull_request_number,
            owner_login,
            args.ref_name,
            args.github_repository,
            args.github_token,
        )
        pull_request_number_output = str(pull_request_number) if pull_request_number is not None else ""
        cluster_prefix = slugify(args.sandbox_cluster_prefix, max(6, 29 - len(sandbox_key) - 1))
        bucket_prefix_max_length = max(
            6,
            63 - len(args.repository_id) - len(sandbox_key) - 2,
        )
        bucket_prefix = slugify(args.sandbox_snapshot_bucket_prefix, bucket_prefix_max_length)

        cluster_name = f"{cluster_prefix}-{sandbox_key}"
        cluster_name = slugify(cluster_name, 29)
        cluster_slug = slugify(cluster_name, 29)
        snapshot_bucket_name = f"{bucket_prefix}-{args.repository_id}-{sandbox_key}"
        snapshot_bucket_name = snapshot_bucket_name.lower()[:63].rstrip("-")

        node_instance_type = input_node_instance_type or args.sandbox_node_instance_type
        node_min_size = input_node_min_size or args.sandbox_node_min_size
        node_max_size = input_node_max_size or args.sandbox_node_max_size
        node_desired_size = input_node_desired_size or args.sandbox_node_desired_size

        aws_role_arn = require(
            args.role_sandbox_arn.strip(),
            "GitHub secret AWS_ROLE_SANDBOX_ARN or repository variable AWS_ROLE_SANDBOX_ARN must be configured for sandbox runs.",
        )
        runtime_template_environment = "staging"
        deployment_environment = "sandbox"
        application_template = "deploy/argocd/staging-application.yaml.tpl"
        values_file = "deploy/helm/face-detector/values-staging.yaml"
        target_revision = input_git_revision or args.ref_name
        environment_identity = sandbox_key
        env_version = compute_env_version(
            args.environment,
            args.default_branch,
            environment_identity,
            git_sha,
            release_tag,
        )
        if pull_request_number is None:
            ssm_environment_key = f"admin/{admin_owner_path}/{admin_branch_path}"
            param_prefix = f"/facedetector/{ssm_environment_key}"
            terraform_state_key = f"admin-previews/{admin_owner_path}/{admin_branch_path}/terraform.tfstate"
            ssm_state_key = f"admin-previews/{admin_owner_path}/{admin_branch_path}/ssm.tfstate"
        else:
            ssm_environment_key = f"sandbox/{sandbox_key}"
            param_prefix = f"/facedetector/{ssm_environment_key}"
            terraform_state_key = f"sandboxes/{sandbox_key}/terraform.tfstate"
            ssm_state_key = f"sandboxes/{sandbox_key}/ssm.tfstate"
    else:
        if args.environment == "production":
            if not (is_default_branch(args.ref_name, args.default_branch) or is_release_ref(release_tag)):
                raise SystemExit(
                    "production runs are allowed only from the default branch or a release/tag ref. "
                    f"Current ref is {args.ref_name}."
                )
        elif not is_default_branch(args.ref_name, args.default_branch):
            raise SystemExit(
                f"{args.environment} runs are allowed only from the default branch. "
                f"Current ref is {args.ref_name}."
            )

        if args.mode == "infrastructure" and args.action != "apply":
            raise SystemExit(
                f"{args.environment} infrastructure runs allow only action=apply. "
                f"Received action={args.action}."
            )

        forbidden_overrides = {
            "cluster_name": input_cluster_name,
            "snapshot_bucket_name": input_snapshot_bucket_name,
            "node_instance_type": input_node_instance_type,
            "node_min_size": input_node_min_size,
            "node_max_size": input_node_max_size,
            "node_desired_size": input_node_desired_size,
        }
        used_overrides = [key for key, value in forbidden_overrides.items() if value]
        if used_overrides:
            raise SystemExit(
                f"Shared {args.environment} runs do not accept manual overrides. "
                f"Remove these inputs: {', '.join(used_overrides)}"
            )

        if args.environment == "production":
            cluster_name = args.production_cluster_name
            snapshot_bucket_name = args.production_snapshot_bucket_name
            node_instance_type = args.production_node_instance_type
            node_min_size = args.production_node_min_size
            node_max_size = args.production_node_max_size
            node_desired_size = args.production_node_desired_size
            aws_role_arn = require(
                args.role_production_arn.strip(),
                "GitHub secret AWS_ROLE_PRODUCTION_ARN or repository variable AWS_ROLE_PRODUCTION_ARN must be configured for production runs.",
            )
            application_template = "deploy/argocd/production-application.yaml.tpl"
            values_file = "deploy/helm/face-detector/values-production.yaml"
        else:
            cluster_name = args.staging_cluster_name
            snapshot_bucket_name = args.staging_snapshot_bucket_name
            node_instance_type = args.staging_node_instance_type
            node_min_size = args.staging_node_min_size
            node_max_size = args.staging_node_max_size
            node_desired_size = args.staging_node_desired_size
            aws_role_arn = require(
                args.role_staging_arn.strip(),
                "GitHub secret AWS_ROLE_STAGING_ARN or repository variable AWS_ROLE_STAGING_ARN must be configured for staging runs.",
            )
            application_template = "deploy/argocd/staging-application.yaml.tpl"
            values_file = "deploy/helm/face-detector/values-staging.yaml"

        runtime_template_environment = args.environment
        deployment_environment = args.environment
        ssm_environment_key = args.environment
        param_prefix = f"/facedetector/{args.environment}"
        target_revision = input_git_revision or args.default_branch
        environment_identity = args.environment
        env_version = compute_env_version(
            args.environment,
            args.default_branch,
            environment_identity,
            git_sha,
            release_tag,
        )
        terraform_state_key = f"eks/{cluster_name}.tfstate"
        ssm_state_key = f"ssm/{args.environment}.tfstate"

    outputs = {
        "deployment_environment": deployment_environment,
        "runtime_template_environment": runtime_template_environment,
        "ssm_environment_key": ssm_environment_key,
        "param_prefix": param_prefix,
        "cluster_name": cluster_name,
        "sandbox_key": sandbox_key,
        "pull_request_number": pull_request_number_output,
        "owner_login": owner_login,
        "environment_identity": environment_identity,
        "env_version": env_version,
        "terraform_state_key": terraform_state_key,
        "ssm_state_key": ssm_state_key,
        "snapshot_bucket_name": snapshot_bucket_name,
        "node_instance_type": node_instance_type,
        "node_min_size": node_min_size,
        "node_max_size": node_max_size,
        "node_desired_size": node_desired_size,
        "aws_role_arn": aws_role_arn,
        "application_template": application_template,
        "values_file": values_file,
        "target_revision": target_revision,
    }
    emit_outputs(outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())