from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable


DEPLOY_LABELS = ("deploy-sandbox", "deploy-preview")
SELF_APPROVE_LABEL = "allow-self-approve"
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
        "docker-compose.dev.yml",
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
    parser.add_argument("--label-trust-path", help="Optional path to trusted label metadata resolved by the workflow.")
    parser.add_argument(
        "--allow-self-approve",
        action="store_true",
        help="Allow self-approval when PR author is sole CODEOWNER for changed files (solo-maintainer).",
    )
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


def parse_label_trust(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    trust: dict[str, dict[str, Any]] = {}
    for label, value in data.items():
        if not isinstance(value, dict):
            continue
        trust[str(label)] = {
            "present": bool(value.get("present")),
            "actor": str(value.get("actor") or ""),
            "trusted": bool(value.get("trusted")),
            "labeledAt": value.get("labeledAt"),
        }
    return trust


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
    allow_self_approve: bool = False,
    label_trust: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pull_request = event["pull_request"]
    repository = event["repository"]
    branch = str(pull_request["head"]["ref"])
    pr_author = str(pull_request.get("user", {}).get("login", ""))
    labels = sorted(str(label["name"]) for label in pull_request.get("labels", []))
    has_deploy_label = any(label in DEPLOY_LABELS for label in labels)
    trusted_deploy_labels = [
        label
        for label in DEPLOY_LABELS
        if label in labels and label_trust and label_trust.get(label, {}).get("trusted")
    ]
    deploy_label = trusted_deploy_labels[0] if trusted_deploy_labels else None
    deploy_label_info = label_trust.get(deploy_label, {}) if label_trust and deploy_label else {}
    deploy_label_actor = str(deploy_label_info.get("actor") or "") if deploy_label_info else None
    deploy_label_trusted = deploy_label is not None
    self_approve_label_info = label_trust.get(SELF_APPROVE_LABEL, {}) if label_trust else {}
    self_approve_label_actor = str(self_approve_label_info.get("actor") or "") if self_approve_label_info else None
    self_approve_label_trusted = bool(self_approve_label_info.get("trusted"))
    self_approve_allowed = allow_self_approve and self_approve_label_trusted
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
    self_approve_used = False
    self_approve_actor = None
    if codeowners:
        matched_owners = owners_for_changed_files(changed_files, codeowners)
        if matched_owners:
            if approvers and any(a in matched_owners for a in approvers):
                approval_exception = True
            elif self_approve_allowed and matched_owners == {pr_author}:
                # explicit opt-in for solo-maintainer self-approve
                approval_exception = True
                self_approve_used = True
                # actor that triggered event (if present)
                self_approve_actor = event.get("sender", {}).get("login")
        else:
            # no owners matched; fallback to numeric approvals
            approval_exception = approval_count >= 1
    else:
        # no codeowners file loaded; fallback to numeric approvals
        approval_exception = approval_count >= 1
    # detect critical path touches
    touches_critical_paths = any(path_matches(path, CRITICAL_PATH_PATTERNS) for path in changed_files)
    critical_path_requires_sandbox = touches_critical_paths and not deploy_label_trusted
    governance_satisfied = deploy_label_trusted or approval_exception
    should_fail = requires_sandbox_label and (not governance_satisfied or critical_path_requires_sandbox)

    # blocking reasons (governance core)
    blocking_reasons: list[str] = []
    if classification == "heavy" and same_repo and not is_draft and not is_dependabot_pr:
        if not governance_satisfied:
            blocking_reasons.append("missing_sandbox_label_or_approval")
        if critical_path_requires_sandbox:
            blocking_reasons.append("critical_path_requires_sandbox")

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
    elif deploy_label_trusted:
        decision = "pass"
        summary = (
            "This PR is in the heavy lane and carries a trusted sandbox deploy label, so the reviewer-managed sandbox "
            "requirement is satisfied and the sandbox deploy path may run."
        )
    elif critical_path_requires_sandbox:
        decision = "fail"
        summary = (
            "This PR touches critical paths and must carry `deploy-sandbox` or `deploy-preview` before it can pass "
            "the sandbox policy gate."
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
            "This PR is in the heavy lane and is missing a trusted `deploy-sandbox`/`deploy-preview` label or sufficient approvals. "
            "Have the repository owner add a sandbox deploy label, use the owner-only `allow-self-approve` path for non-critical changes, "
            "or get an owner approval."
        )
    return {
        "version": "1",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "branch": branch,
        "changedFiles": changed_files,
        "classification": classification,
        "decision": decision,
        "governanceMode": (
            "fast"
            if classification == "fast"
            else "sandbox_deploy"
            if deploy_label_trusted
            else "self_approved"
            if self_approve_used
            else "approved"
            if approval_exception
            else "blocked"
            if block
            else "advisory"
        ),
        "hasDeployLabel": has_deploy_label,
        "deployLabel": deploy_label,
        "deployLabelActor": deploy_label_actor,
        "deployLabelTrusted": deploy_label_trusted,
        "isDevopsBranch": False,
        "isDependabotPr": is_dependabot_pr,
        "isDraft": is_draft,
        "reasonGroups": reason_groups,
        "requiresSandboxLabel": requires_sandbox_label,
        "governanceSatisfied": governance_satisfied,
        "sameRepo": same_repo,
        "shouldFail": should_fail,
        "block": block,
        "blockingReasons": blocking_reasons,
        "criticalPathRequiresSandbox": critical_path_requires_sandbox,
        "touchesCriticalPaths": touches_critical_paths,
        "summary": summary,
        "approvers": sorted(list(approvers)) if approvers else [],
        "matchedOwners": sorted(list(matched_owners)) if matched_owners else [],
        "selfApproveEligible": bool(allow_self_approve),
        "selfApproveLabelActor": self_approve_label_actor,
        "selfApproveLabelTrusted": self_approve_label_trusted,
        "selfApproveUsed": bool(self_approve_used),
        "selfApproveActor": self_approve_actor,
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"Sandbox policy decision: {report['decision']}")
    print(f"Governance mode: {report.get('governanceMode', 'unknown')}")
    print(f"Lane classification: {report['classification']}")
    print(f"Branch: {report['branch']}")
    print(f"Deploy label present: {report['hasDeployLabel']}")
    print(f"Trusted deploy label: {report.get('deployLabel') or 'none'}")
    print(f"Deploy label actor: {report.get('deployLabelActor') or 'none'}")
    if report.get("selfApproveEligible"):
        print("Self-approve mode enabled: true")
        print(f"Self-approve actor: {report.get('selfApproveActor') or 'unknown'}")
        print(f"Self-approve label actor: {report.get('selfApproveLabelActor') or 'none'}")
        print(f"Matched owners: {', '.join(report.get('matchedOwners', [])) or 'none'}")
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
        label_trust: dict[str, dict[str, Any]] | None = None
        if getattr(args, "label_trust_path", None):
            try:
                label_trust = parse_label_trust(Path(args.label_trust_path))
            except Exception:
                label_trust = {}

        report = evaluate_policy(
            load_event(Path(args.event_path)),
            load_changed_files(Path(args.changed_files_path)),
            approval_count=approval_count,
            approvers=approvers,
            codeowners=codeowners,
            allow_self_approve=getattr(args, "allow_self_approve", False),
            label_trust=label_trust,
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
            except Exception as report_exc:
                print(f"Failed to write evaluator error report: {report_exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
