from __future__ import annotations
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml
from scripts.evaluate_sandbox_requirement import evaluate_policy, main


class SandboxRequirementPolicyTest(unittest.TestCase):

    def test_heavy_lane_with_codeowners_approval_passes(self) -> None:
        report = evaluate_policy(
            make_event(),
            [".github/workflows/reusable-app-ci.yml"],
            approval_count=1,
        )
        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "pass")
        self.assertFalse(report["shouldFail"])



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
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(
            any("Cross-service change touches multiple application surfaces" in group["reason"] for group in report["reasonGroups"])
        )

    def test_heavy_pr_with_label_passes(self) -> None:
        report = evaluate_policy(
            make_event(labels=["deploy-sandbox"]),
            ["deploy/helm/face-detector/templates/nginx.yaml"],
        )

        self.assertEqual(report["decision"], "pass")
        self.assertFalse(report["shouldFail"])

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
                    "--allow-self-approve",
                ]
            )
            report = print_report.call_args.args[0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["decision"], "pass")
        self.assertTrue(report["selfApproveEligible"])
        self.assertTrue(report["selfApproveUsed"])
        self.assertEqual(report["selfApproveActor"], "chiendz11")
        self.assertEqual(report["matchedOwners"], ["chiendz11"])

    def test_workflow_change_without_label_fails(self) -> None:
        report = evaluate_policy(
            make_event(branch="devops/enterprise-ci-hardening"),
            [".github/workflows/reusable-app-ci.yml"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["shouldFail"])

    def test_release_contract_change_without_label_fails(self) -> None:
        report = evaluate_policy(
            make_event(),
            ["frontend-admin/Dockerfile"],
        )

        self.assertEqual(report["classification"], "heavy")
        self.assertEqual(report["decision"], "fail")
        self.assertTrue(report["shouldFail"])

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


if __name__ == "__main__":
    unittest.main()
