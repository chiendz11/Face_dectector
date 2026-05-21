from __future__ import annotations

import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in document and "on" not in document:
        document["on"] = document.pop(True)
    return document


class WorkflowGovernancePolicyTest(unittest.TestCase):
    def test_trust_boundary_exception_schema_exists(self) -> None:
        data = load_yaml(REPO_ROOT / "policies/data/exceptions.yaml")
        github_exceptions = data["exceptions"]["github"]

        self.assertIn("trust_boundary_changes", github_exceptions)
        self.assertIsInstance(github_exceptions["trust_boundary_changes"], list)

        for entry in github_exceptions["trust_boundary_changes"]:
            self.assertIsInstance(entry.get("rule"), str)
            self.assertTrue(entry["rule"])
            self.assertIsInstance(entry.get("workflow"), str)
            self.assertTrue(entry["workflow"])
            self.assertIsInstance(entry.get("reason"), str)
            self.assertTrue(entry["reason"])
            self.assertIsInstance(entry.get("expires_on"), str)

    def test_trusted_parent_workflows_keep_pull_request_target(self) -> None:
        trusted_workflows = {
            ".github/workflows/sandbox-auto-apply.yml": "Sandbox Auto Apply",
            ".github/workflows/sandbox-auto-destroy.yml": "Sandbox Auto Destroy",
            ".github/workflows/terraform-plan.yml": "Terraform PR Plan",
        }

        for relative_path, expected_name in trusted_workflows.items():
            workflow = load_yaml(REPO_ROOT / relative_path)
            self.assertEqual(workflow["name"], expected_name)
            self.assertIn("pull_request_target", workflow["on"])
            self.assertNotIn("pull_request", workflow["on"])

    def test_platform_ci_enforces_workflow_governance_policy(self) -> None:
        workflow = load_yaml(REPO_ROOT / ".github/workflows/reusable-platform-ci.yml")
        steps = workflow["jobs"]["platform-validate"]["steps"]

        validate_step = next(
            step for step in steps if step.get("name") == "Validate GitHub workflow governance"
        )
        self.assertIn("conftest test", validate_step["run"])
        self.assertIn("--policy policies/github/workflows", validate_step["run"])
        self.assertIn("--data policies/data", validate_step["run"])

    def test_sandbox_workflow_run_only_signals_pull_request_target_apply(self) -> None:
        workflow = load_yaml(REPO_ROOT / ".github/workflows/sandbox-auto-apply.yml")
        jobs = workflow["jobs"]

        self.assertIn("workflow_run", workflow["on"])

        signal_job = jobs["signal-apply-ready"]
        self.assertIn("github.event_name == 'workflow_run'", signal_job["if"])
        self.assertEqual(signal_job["permissions"]["issues"], "write")
        signal_script = signal_job["steps"][0]["with"]["script"]
        self.assertIn("removeLabel", signal_script)
        self.assertIn("addLabels", signal_script)
        self.assertIn("ready-for-deploy", signal_script)

        for job_name in ("apply-infrastructure", "bootstrap-sandbox", "mark-sandbox-validated"):
            self.assertIn(
                "github.event_name == 'pull_request_target'",
                jobs[job_name]["if"],
                f"{job_name} must not assume AWS permissions from workflow_run events",
            )


if __name__ == "__main__":
    unittest.main()
