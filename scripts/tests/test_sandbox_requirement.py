from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from scripts.evaluate_sandbox_requirement import evaluate_policy


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
) -> dict[str, object]:
    repo_name = "chiendz11/Face_dectector"
    return {
        "repository": {"full_name": repo_name},
        "pull_request": {
            "draft": draft,
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