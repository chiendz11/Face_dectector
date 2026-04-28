#!/usr/bin/env python3
import argparse
import sys


def build_apply_comment(args: argparse.Namespace) -> str:
    lines = [
        "<!-- sandbox-lifecycle-status -->",
        "## Sandbox Status",
        "",
        f"🚀 Sandbox infrastructure for PR #{args.pull_request_number} is ready.",
        "",
        f"- Sandbox key: `{args.sandbox_key}`",
        f"- Environment version: `{args.env_version}`",
        f"- Cluster name: `{args.cluster_name}`",
        f"- Terraform state: `{args.terraform_state_key}`",
        f"- SSM state: `{args.ssm_state_key}`",
        f"- Snapshot bucket: `{args.snapshot_bucket_name}`",
        f"- Workflow run: [view run]({args.run_url})",
    ]
    if args.cluster_endpoint:
        lines.append(f"- EKS endpoint: [{args.cluster_endpoint}]({args.cluster_endpoint})")
    lines.append("")
    lines.append("ArgoCD bootstrap and application sync can now target this exact PR sandbox.")
    return "\n".join(lines)


def build_destroy_comment(args: argparse.Namespace) -> str:
    return "\n".join(
        [
            "<!-- sandbox-lifecycle-status -->",
            "## Sandbox Status",
            "",
            f"🧹 Sandbox resources for PR #{args.pull_request_number} have been wiped clean. AWS is safe!",
            "",
            f"- Sandbox key: `{args.sandbox_key}`",
            f"- Environment version: `{args.env_version}`",
            f"- Cluster name: `{args.cluster_name}`",
            f"- Terraform state: `{args.terraform_state_key}`",
            f"- SSM state: `{args.ssm_state_key}`",
            "- Cleanup sweep: EKS nodegroups, Auto Scaling groups, EC2 instances, load balancers, available EBS volumes, VPC endpoints, and VPC peering connections",
            f"- Workflow run: [view run]({args.run_url})",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["apply", "destroy"], required=True)
    parser.add_argument("--pull-request-number", required=True)
    parser.add_argument("--sandbox-key", required=True)
    parser.add_argument("--env-version", required=True)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--terraform-state-key", required=True)
    parser.add_argument("--ssm-state-key", required=True)
    parser.add_argument("--snapshot-bucket-name", default="")
    parser.add_argument("--cluster-endpoint", default="")
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()

    body = build_apply_comment(args) if args.mode == "apply" else build_destroy_comment(args)
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())