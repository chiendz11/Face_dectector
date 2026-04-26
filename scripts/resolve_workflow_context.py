#!/usr/bin/env python3
import argparse
import os
import re
import sys


def slugify(value: str, max_length: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    shortened = normalized[:max_length].rstrip("-")
    return shortened or "sandbox"


def require(value: str, message: str) -> str:
    if not value:
        raise SystemExit(message)
    return value


def is_default_branch(ref_name: str, default_branch: str) -> bool:
    return ref_name in {default_branch, "main", "master"}


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
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--repository-id", default="0")
    parser.add_argument("--input-cluster-name", default="")
    parser.add_argument("--input-snapshot-bucket-name", default="")
    parser.add_argument("--input-node-instance-type", default="")
    parser.add_argument("--input-node-min-size", default="")
    parser.add_argument("--input-node-max-size", default="")
    parser.add_argument("--input-node-desired-size", default="")
    parser.add_argument("--input-git-revision", default="")
    parser.add_argument("--staging-cluster-name", default="face-detector-staging")
    parser.add_argument("--production-cluster-name", default="face-detector-production")
    parser.add_argument("--sandbox-cluster-prefix", default="face-detector-sbx")
    parser.add_argument("--staging-snapshot-bucket-name", default="face-detector-employee-images-staging")
    parser.add_argument("--production-snapshot-bucket-name", default="face-detector-employee-images-production")
    parser.add_argument("--sandbox-snapshot-bucket-prefix", default="face-detector-sbx")
    parser.add_argument("--staging-node-instance-type", default="t3.medium")
    parser.add_argument("--production-node-instance-type", default="t3.large")
    parser.add_argument("--sandbox-node-instance-type", default="t3.medium")
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

    if args.environment == "sandbox":
        if not args.ref_name.startswith("feature/"):
            raise SystemExit(
                "Sandbox runs are allowed only from feature/* branches. "
                f"Current ref is {args.ref_name}."
            )

        sandbox_branch = args.ref_name.split("/", 1)[1]
        cluster_prefix = slugify(args.sandbox_cluster_prefix, 12)
        max_branch_slug_length = max(6, 29 - len(cluster_prefix) - 1)
        branch_slug = slugify(sandbox_branch, max_branch_slug_length)
        bucket_prefix = slugify(args.sandbox_snapshot_bucket_prefix, 24)

        cluster_name = input_cluster_name or f"{cluster_prefix}-{branch_slug}"
        cluster_name = slugify(cluster_name, 29)
        cluster_slug = slugify(cluster_name, 29)
        snapshot_bucket_name = input_snapshot_bucket_name or f"{bucket_prefix}-{args.repository_id}-{branch_slug}"
        snapshot_bucket_name = snapshot_bucket_name.lower()[:63].rstrip("-")

        node_instance_type = input_node_instance_type or args.sandbox_node_instance_type
        node_min_size = input_node_min_size or args.sandbox_node_min_size
        node_max_size = input_node_max_size or args.sandbox_node_max_size
        node_desired_size = input_node_desired_size or args.sandbox_node_desired_size

        aws_role_arn = require(
            args.role_sandbox_arn.strip(),
            "Repository variable AWS_ROLE_SANDBOX_ARN must be configured for sandbox runs.",
        )
        runtime_template_environment = "staging"
        deployment_environment = "sandbox"
        ssm_environment_key = f"sandbox/{cluster_slug}"
        param_prefix = f"/facedetector/{ssm_environment_key}"
        application_template = "deploy/argocd/staging-application.yaml.tpl"
        values_file = "deploy/helm/face-detector/values-staging.yaml"
        target_revision = input_git_revision or args.ref_name
    else:
        if not is_default_branch(args.ref_name, args.default_branch):
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
                "Repository variable AWS_ROLE_PRODUCTION_ARN must be configured for production runs.",
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
                "Repository variable AWS_ROLE_STAGING_ARN must be configured for staging runs.",
            )
            application_template = "deploy/argocd/staging-application.yaml.tpl"
            values_file = "deploy/helm/face-detector/values-staging.yaml"

        runtime_template_environment = args.environment
        deployment_environment = args.environment
        ssm_environment_key = args.environment
        param_prefix = f"/facedetector/{args.environment}"
        target_revision = input_git_revision or args.default_branch

    outputs = {
        "deployment_environment": deployment_environment,
        "runtime_template_environment": runtime_template_environment,
        "ssm_environment_key": ssm_environment_key,
        "param_prefix": param_prefix,
        "cluster_name": cluster_name,
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