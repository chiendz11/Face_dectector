from __future__ import annotations
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml
from scripts.evaluate_sandbox_requirement import evaluate_policy, main


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in document and "on" not in document:
        document["on"] = document.pop(True)
    return document


def make_event(
    *,
    branch: str = "feature/heavy-change",
    labels: list[str] | None = None,
    same_repo: bool = True,
    draft: bool = False,
    author: str = "chiendz11",
) -> dict[str, object]:
    repo_name = "chiendz11/Face_dectector"
    return {
        "repository": {"full_name": repo_name},
        "sender": {"login": author},
        "pull_request": {
            "draft": draft,
            "user": {"login": author},
            "head": {
                "ref": branch,
                "repo": {
                    "full_name": repo_name if same_repo else "someone-else/Face_dectector",
                },
            },
            "labels": [{"name": label} for label in (labels or [])],
        },
    }


def trusted_labels(*labels: str, actor: str = "chiendz11") -> dict[str, dict[str, object]]:
    return {
        label: {
            "present": True,
            "actor": actor,
            "trusted": True,
            "labeledAt": "2026-05-15T00:00:00Z",
        }
        for label in labels
    }


def untrusted_labels(*labels: str, actor: str = "github-actions[bot]") -> dict[str, dict[str, object]]:
    return {
        label: {
            "present": True,
            "actor": actor,
            "trusted": False,
            "labeledAt": "2026-05-15T00:00:00Z",
        }
        for label in labels
    }


class SandboxRequirementPolicyTest(unittest.TestCase):
    def test_heavy_infra_pr_without_label_fails(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["terraform/eks/main.tf"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["shouldFail"])

    def test_cross_service_pr_without_label_fails(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["backend/app/main.py", "frontend-admin/src/App.jsx"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["sandboxRecommended"])
        self.assertFalse(report["sandboxRequired"])
        self.assertFalse(report["block"])
        self.assertTrue(
            any("Cross-service change touches multiple application surfaces" in group["reason"] for group in report["reasonGroups"])
        )

    def test_heavy_pr_with_label_passes(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-sandbox"]),
            ["backend/app/main.py", "frontend-admin/src/App.jsx"],
            label_trust=trusted_labels("deploy-sandbox"),
        )

        self.assertEqual(report["decision"], "pass")
        self.assertFalse(report["shouldFail"])
        self.assertFalse(report["block"])
        self.assertEqual(report["governanceMode"], "sandbox_deploy_requested")
        self.assertEqual(report["deployLabelActor"], "chiendz11")
        self.assertTrue(report["sandboxRecommended"])
        self.assertTrue(report["autoApplyEligible"])

    def test_deploy_preview_label_is_supported_alias(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-preview"]),
            ["backend/app/main.py", "frontend-admin/src/App.jsx"],
            label_trust=trusted_labels("deploy-preview"),
        )

        self.assertEqual(report["decision"], "pass")
        self.assertFalse(report["shouldFail"])
        self.assertFalse(report["block"])

    def test_deploy_contract_with_deploy_label_still_requires_validation(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-sandbox"]),
            ["deploy/helm/face-detector/templates/nginx.yaml"],
            label_trust=trusted_labels("deploy-sandbox"),
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["autoApplyEligible"])
        self.assertTrue(report["block"])

    def test_untrusted_deploy_label_does_not_clear_governance_block(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-sandbox"]),
            ["terraform/eks/main.tf"],
            label_trust=untrusted_labels("deploy-sandbox"),
        )

        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["shouldFail"])
        self.assertTrue(report["block"])
        self.assertFalse(report["deployLabelTrusted"])
        self.assertIn("sandbox_required_missing_validation_or_waiver", report["blockingReasons"])

    def test_critical_path_with_deploy_label_runs_apply_but_still_blocks_merge(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-sandbox"]),
            ["terraform/eks/main.tf"],
            label_trust=trusted_labels("deploy-sandbox"),
        )

        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["autoApplyEligible"])
        self.assertTrue(report["block"])

    def test_critical_path_with_sandbox_validation_passes(self) -> None:
        report = evaluate_policy(
            make_event(labels=["sandbox-validated"]),
            ["terraform/eks/main.tf"],
            label_trust=trusted_labels("sandbox-validated", actor="github-actions[bot]"),
        )

        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["sandboxValidatedTrusted"])
        self.assertFalse(report["block"])
        self.assertEqual(report["governanceMode"], "sandbox_validated")

    def test_critical_path_with_owner_waiver_passes(self) -> None:
        report = evaluate_policy(
            make_event(labels=["skip-sandbox-approved"]),
            ["terraform/eks/main.tf"],
            label_trust=trusted_labels("skip-sandbox-approved"),
        )

        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["skipSandboxTrusted"])
        self.assertFalse(report["block"])
        self.assertEqual(report["governanceMode"], "sandbox_waived")

    def test_critical_path_self_approve_still_requires_sandbox_label(self) -> None:
        report = evaluate_policy(
            make_event(labels=["allow-self-approve"]),
            ["terraform/eks/main.tf"],
            codeowners={"*": ["chiendz11"]},
            allow_self_approve=True,
            label_trust=trusted_labels("allow-self-approve"),
        )

        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["shouldFail"])
        self.assertTrue(report["block"])
        self.assertIn("sandbox_required_missing_validation_or_waiver", report["blockingReasons"])

    def test_untrusted_self_approve_label_does_not_enable_self_approve(self) -> None:
        report = evaluate_policy(
            make_event(labels=["allow-self-approve"]),
            [".github/workflows/sandbox-policy.yml"],
            codeowners={"*": ["chiendz11"]},
            allow_self_approve=True,
            label_trust=untrusted_labels("allow-self-approve", actor="octocat"),
        )

        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["block"])
        self.assertFalse(report["selfApproveUsed"])
        self.assertFalse(report["selfApproveLabelTrusted"])

    def test_main_passes_allow_self_approve_flag_to_evaluator(self) -> None:
        with (
            patch(
                "scripts.evaluate_sandbox_requirement.load_event",
                return_value=make_event(labels=["allow-self-approve"]),
            ),
            patch(
                "scripts.evaluate_sandbox_requirement.load_changed_files",
                return_value=[".github/workflows/sandbox-policy.yml"],
            ),
            patch("scripts.evaluate_sandbox_requirement.parse_approvers", return_value=set()),
            patch("scripts.evaluate_sandbox_requirement.parse_codeowners", return_value={"*": ["chiendz11"]}),
            patch("scripts.evaluate_sandbox_requirement.parse_label_trust", return_value=trusted_labels("allow-self-approve")),
            patch("scripts.evaluate_sandbox_requirement.print_report") as print_report,
        ):
            exit_code = main(
                [
                    "--event-path",
                    "event.json",
                    "--changed-files-path",
                    "changed-files",
                    "--approvers-path",
                    "approvers.json",
                    "--codeowners-path",
                    "CODEOWNERS",
                    "--label-trust-path",
                    "label-trust.json",
                    "--allow-self-approve",
                ]
            )
            report = print_report.call_args.args[0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["block"])
        self.assertTrue(report["selfApproveEligible"])
        self.assertTrue(report["selfApproveUsed"])
        self.assertEqual(report["selfApproveActor"], "chiendz11")
        self.assertTrue(report["selfApproveLabelTrusted"])
        self.assertEqual(report["selfApproveLabelActor"], "chiendz11")
        self.assertEqual(report["matchedOwners"], ["chiendz11"])

    def test_workflow_change_without_label_fails(self) -> None:
        report = evaluate_policy(
            make_event(branch="devops/enterprise-ci-hardening"),
            [".github/workflows/reusable-app-ci.yml"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["sandboxRequired"])
        self.assertTrue(report["shouldFail"])

    def test_release_contract_change_without_label_is_recommended(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["frontend-admin/Dockerfile"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["sandboxRecommended"])
        self.assertFalse(report["shouldFail"])

    def test_compose_override_change_without_label_is_recommended(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["docker-compose.dev.yml"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["sandboxRecommended"])
        self.assertFalse(report["shouldFail"])

    def test_qa_scripts_and_docs_stay_fast_lane(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["scripts/qa-local-compose.ps1", "scripts/qa-local-commands.md"],
        )

        self.assertEqual(report["classification"], "fast")
        self.assertEqual(report["decision"], "pass")
        self.assertFalse(report["shouldFail"])

    def test_draft_heavy_pr_is_advisory(self) -> None:
        report = evaluate_policy(
            make_event(draft=True),
            ["backend/alembic/versions/0003_add_table.py"],
        )

        self.assertEqual(report["decision"], "advisory")
        self.assertFalse(report["shouldFail"])

    def test_workflow_runs_sandbox_requirement_script(self) -> None:
        workflow = load_yaml(REPO_ROOT / ".github/workflows/sandbox-policy.yml")
        steps = workflow["jobs"]["evaluate"]["steps"]

        evaluate_step = next(
            step for step in steps if step.get("name") == "Evaluate sandbox blast radius policy"
        )
        self.assertIn("scripts/evaluate_sandbox_requirement.py", evaluate_step["run"])
        self.assertIn("--changed-files-path .sandbox-policy-files", evaluate_step["run"])
        self.assertIn("--label-trust-path .sandbox-policy-label-trust.json", evaluate_step["run"])

        label_step = next(
            step for step in steps if step.get("name") == "Resolve trusted governance labels"
        )
        self.assertIn("issues.listEvents", label_step["with"]["script"])
        self.assertIn("actor === repoOwner", label_step["with"]["script"])
        self.assertIn("skip-sandbox-approved", label_step["with"]["script"])
        self.assertIn("sandbox-validated", label_step["with"]["script"])

        reconcile_step = next(
            step for step in steps if step.get("name") == "Reconcile sandbox governance labels"
        )
        self.assertIn("sandbox-required", reconcile_step["with"]["script"])
        self.assertIn("sandbox-recommended", reconcile_step["with"]["script"])

        comment_step = next(
            step for step in steps if step.get("name") == "Upsert sandbox policy PR comment"
        )
        uses_value = str(comment_step["uses"])
        self.assertTrue(
            uses_value.startswith("actions/github-script@"),
            f"Unexpected action reference: {uses_value}",
        )
        pinned_ref = uses_value.split("@", 1)[1]
        self.assertEqual(
            len(pinned_ref),
            40,
            "actions/github-script must stay pinned to a full commit SHA",
        )

    def test_platform_ci_detects_sandbox_policy_contract_changes(self) -> None:
        workflow_path = REPO_ROOT / ".github/workflows/reusable-platform-ci.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")

        self.assertIn("sandbox-policy", workflow_text)
        self.assertIn("evaluate_sandbox_requirement", workflow_text)

    def test_sandbox_auto_apply_does_not_special_case_branch_prefixes(self) -> None:
        workflow_path = REPO_ROOT / ".github/workflows/sandbox-auto-apply.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")

        self.assertNotIn("isDevopsBranch", workflow_text)
        self.assertNotIn("Skipping developer sandbox flow for devops/* branches.", workflow_text)

    def test_sandbox_auto_apply_accepts_deploy_preview_alias(self) -> None:
        workflow_path = REPO_ROOT / ".github/workflows/sandbox-auto-apply.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")

        self.assertIn("const deployLabels = ['deploy-sandbox', 'deploy-preview'];", workflow_text)
        self.assertIn("report.autoApplyEligible", workflow_text)
        self.assertIn("sandbox-validated", workflow_text)
        self.assertIn("listPullRequestsAssociatedWithCommit", workflow_text)
        self.assertIn("sandbox-validation-status", workflow_text)


if __name__ == "__main__":
    unittest.main()
