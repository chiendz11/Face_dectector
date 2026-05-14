from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable


DEPLOY_LABELS = {"deploy-sandbox", "deploy-preview"}
HEAVY_REASON_PATTERNS = {
    "Touches infrastructure, deployment, workflow, policy, or ingress control paths": [
        ".github/actions/**",
        ".github/workflows/**",
        "aws/**",
        "deploy/**",
        "nginx/**",
        "policies/**",
        "terraform/**",
    ],
    "Touches shared runtime or release contract files": [
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
        ".github/image-catalog.json",
        ".trivyignore",
        "backend/Dockerfile",
        "docker-compose.ci.yml",
        "docker-compose.edge.yml",
        "docker-compose.yml",
        "edge-client/Dockerfile",
        "frontend-admin/Dockerfile",
        "nginx/Dockerfile",
        "scripts/ci-e2e-test.sh",
        "scripts/ci-integration-test.sh",
        "scripts/cleanup_sandbox_aws_orphans.py",
        "scripts/generate-env-from-ssm.sh",
        "scripts/render_sandbox_status_comment.py",
        "scripts/resolve_registry_digest.py",
        "scripts/resolve_workflow_context.py",
        "scripts/update_gitops_image_locks.py",
    ],
    "Touches database or migration state paths": [
        "backend/alembic.ini",
        "backend/alembic/**",
    ],
}
SERVICE_SURFACE_PATTERNS = {
    "backend": ["backend/**"],
    "frontend-admin": ["frontend-admin/**"],
    "edge-client": ["edge-client/**"],
    "nginx": ["nginx/**"],
}

# Patterns that are considered critically sensitive and should block merges
CRITICAL_PATH_PATTERNS = [
    "terraform/**",
    "backend/alembic.ini",
    "backend/alembic/**",
    "iam/**",
    "network/**",
    "auth/**",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify PR blast radius and enforce sandbox labels for heavy changes."
    )
    parser.add_argument("--event-path", required=True, help="Path to the GitHub event payload JSON.")
    parser.add_argument(
        "--changed-files-path",
        required=True,
        help="Path to a newline-delimited file containing changed repository paths.",
    )
    parser.add_argument("--approvals-path", help="Optional path to a file containing approval count.")
    parser.add_argument("--approvers-path", help="Optional path to a file (JSON array or newline) with approver usernames.")
    parser.add_argument("--codeowners-path", help="Optional path to the CODEOWNERS file to validate owners.")
    parser.add_argument("--report-path", help="Optional path to write the JSON evaluation report.")
    return parser.parse_args(argv)


def parse_approvers(path: Path) -> set[str]:
    try:
        txt = path.read_text(encoding="utf-8").strip()
    except Exception:
        return set()

    if not txt:
        return set()

    # try JSON array first
    try:
        data = json.loads(txt)
        if isinstance(data, list):
            names = [str(x) for x in data]
        else:
            names = [str(data)]
    except Exception:
        names = [line.strip() for line in txt.splitlines() if line.strip()]

    return {n.lstrip("@") for n in names}


def parse_codeowners(path: Path) -> Dict[str, list[str]]:
    mapping: Dict[str, list[str]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return mapping

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners: list[str] = []
        for owner in parts[1:]:
            if not owner.startswith("@"):
                continue
            owner_name = owner.lstrip("@")
            # ignore team entries like org/team
            if "/" in owner_name:
                continue
            owners.append(owner_name)
        if owners:
            mapping[pattern] = owners
    return mapping


def owners_for_changed_files(changed_files: Iterable[str], codeowners: Dict[str, list[str]]) -> set[str]:
    owners: set[str] = set()
    for path in changed_files:
        for pattern, owner_list in codeowners.items():
            if path_matches(path, [pattern]):
                owners.update(owner_list)
    return owners


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def path_matches(path: str, patterns: list[str]) -> bool:
    candidate = normalize_path(path)
    return any(fnmatch.fnmatch(candidate, normalize_path(pattern)) for pattern in patterns)


def load_event(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_changed_files(path: Path) -> list[str]:
    return [
        normalize_path(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if normalize_path(line)
    ]


def collect_reason_groups(changed_files: list[str]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    for reason, patterns in HEAVY_REASON_PATTERNS.items():
        matches = [path for path in changed_files if path_matches(path, patterns)]
        if matches:
            groups.append(
                {
                    "reason": reason,
                    "examples": matches[:5],
                }
            )

    touched_surfaces = sorted(
        surface
        for surface, patterns in SERVICE_SURFACE_PATTERNS.items()
        if any(path_matches(path, patterns) for path in changed_files)
    )
    if len(touched_surfaces) >= 2:
        groups.append(
            {
                "reason": f"Cross-service change touches multiple application surfaces: {', '.join(touched_surfaces)}",
                "examples": touched_surfaces,
            }
        )

    return groups


def evaluate_policy(
    event: dict[str, Any],
    changed_files: list[str],
    approval_count: int = 0,
    approvers: set[str] | None = None,
    codeowners: Dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    pull_request = event["pull_request"]
    repository = event["repository"]
    branch = str(pull_request["head"]["ref"])
    pr_author = str(pull_request.get("user", {}).get("login", ""))
    labels = sorted(str(label["name"]) for label in pull_request.get("labels", []))
    has_deploy_label = any(label in DEPLOY_LABELS for label in labels)
    is_dependabot_pr = pr_author == "dependabot[bot]" or branch.startswith("dependabot/")
    is_draft = bool(pull_request.get("draft", False))
    same_repo = pull_request["head"]["repo"]["full_name"] == repository["full_name"]
    reason_groups = collect_reason_groups(changed_files)
    classification = "heavy" if reason_groups else "fast"
    requires_sandbox_label = (
        classification == "heavy"
        and same_repo
        and not is_draft
        and not is_dependabot_pr
    )
    # CODEOWNERS/ruleset exception: if approver is an owner of changed heavy files
    approval_exception = False
    matched_owners: set[str] = set()
    if codeowners and approvers:
        matched_owners = owners_for_changed_files(changed_files, codeowners)
        if matched_owners and any(a in matched_owners for a in approvers):
            approval_exception = True
    else:
        # fallback: numeric approval count
        approval_exception = approval_count >= 1
    should_fail = requires_sandbox_label and not has_deploy_label and not approval_exception
    # detect critical path touches
    touches_critical_paths = any(path_matches(path, CRITICAL_PATH_PATTERNS) for path in changed_files)

    # blocking reasons (governance core)
    blocking_reasons: list[str] = []
    if classification == "heavy" and same_repo and not is_draft and not is_dependabot_pr:
        # missing approvals (CODEOWNERS/ruleset) is a governance block
        if not approval_exception:
            blocking_reasons.append("missing_approvals")
        if touches_critical_paths:
            blocking_reasons.append("touches_critical_paths")

    block = len(blocking_reasons) > 0

    if classification == "fast":
        decision = "pass"
        summary = (
            "This PR stays in the fast lane. It does not currently touch the high-blast-radius "
            "paths that require a reviewer-managed sandbox label."
        )
    elif is_dependabot_pr:
        decision = "advisory"
        summary = (
            "This is a Dependabot PR. Heavy-lane deploy-label enforcement is skipped so dependency update "
            "automation can proceed through the normal CI and review gates."
        )
    elif is_draft:
        decision = "advisory"
        summary = (
            "This is a heavy-lane draft PR. The sandbox label gate is delayed until the PR is ready for review."
        )
    elif not same_repo:
        decision = "advisory"
        summary = (
            "This is a heavy-lane PR from a fork. The standard same-repository auto-apply sandbox path is unavailable, "
            "so this check does not enforce a deploy label."
        )
    elif has_deploy_label:
        decision = "pass"
        summary = (
            "This PR is in the heavy lane and already carries a sandbox deploy label, so the reviewer-managed sandbox "
            "requirement is satisfied."
        )
    elif approval_exception:
        decision = "pass"
        summary = (
            "This PR is in the heavy lane but has sufficient approvals (CODEOWNERS/ruleset), so the reviewer-managed sandbox "
            "requirement is satisfied."
        )
    else:
        decision = "fail"
        summary = (
            "This PR is in the heavy lane and is missing `deploy-sandbox` or `deploy-preview` and does not have sufficient approvals. "
            "Add one of those labels or get approval before asking the standard sandbox auto-apply flow to create a PR environment."
        )
    return {
        "version": "1",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "branch": branch,
        "changedFiles": changed_files,
        "classification": classification,
        "decision": decision,
        "hasDeployLabel": has_deploy_label,
        "isDevopsBranch": False,
        "isDependabotPr": is_dependabot_pr,
        "isDraft": is_draft,
        "reasonGroups": reason_groups,
        "requiresSandboxLabel": requires_sandbox_label,
        "sameRepo": same_repo,
        "shouldFail": should_fail,
        "block": block,
        "blockingReasons": blocking_reasons,
        "touchesCriticalPaths": touches_critical_paths,
        "summary": summary,
        "approvers": sorted(list(approvers)) if approvers else [],
        "matchedOwners": sorted(list(matched_owners)) if matched_owners else [],
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"Sandbox policy decision: {report['decision']}")
    print(f"Lane classification: {report['classification']}")
    print(f"Branch: {report['branch']}")
    print(f"Deploy label present: {report['hasDeployLabel']}")
    print(report["summary"])

    if report["reasonGroups"]:
        print("Reasons:")
        for group in report["reasonGroups"]:
            examples = ", ".join(group.get("examples", [])[:3])
            suffix = f" Example files: {examples}." if examples else ""
            print(f"- {group['reason']}.{suffix}")


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        approval_count = 0
        if args.approvals_path:
            try:
                approval_count = int(Path(args.approvals_path).read_text(encoding="utf-8").strip())
            except Exception:
                approval_count = 0
        approvers: set[str] | None = None
        if getattr(args, "approvers_path", None):
            try:
                approvers = parse_approvers(Path(args.approvers_path))
            except Exception:
                approvers = set()
        codeowners: Dict[str, list[str]] | None = None
        if getattr(args, "codeowners_path", None):
            try:
                codeowners = parse_codeowners(Path(args.codeowners_path))
            except Exception:
                codeowners = None

        report = evaluate_policy(
            load_event(Path(args.event_path)),
            load_changed_files(Path(args.changed_files_path)),
            approval_count=approval_count,
            approvers=approvers,
            codeowners=codeowners,
        )
        print_report(report)

        if args.report_path:
            write_report(Path(args.report_path), report)

        # Normal completion: return 0. Blocking/allow decisions are encoded in report['block']
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        err_report = {
            "version": "1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "decision": "error",
            "classification": "unknown",
            "summary": "Evaluator encountered an unexpected error.",
            "error": str(exc),
            "traceback": tb,
        }
        print("Evaluator runtime error:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        if getattr(args, "report_path", None):
            try:
                write_report(Path(args.report_path), err_report)
            except Exception:
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())