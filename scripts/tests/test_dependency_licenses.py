from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from scripts.check_dependency_licenses import compile_policy, evaluate_inventory_document


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in document and "on" not in document:
        document["on"] = document.pop(True)
    return document


def build_policy() -> dict[str, object]:
    return compile_policy(
        {
            "allowedLicenses": [
                "Apache-2.0",
                "BSD-3-Clause",
                "MIT",
            ],
            "reviewLicenses": [
                "CC-BY-4.0",
            ],
            "disallowedLicenses": [
                "GPL-3.0",
                "UNLICENSED",
                "UNKNOWN",
            ],
            "ignorePackages": [
                {
                    "surface": "frontend-admin",
                    "package": "frontend-admin",
                    "privateOnly": True,
                    "reason": "Ignore the private workspace package.",
                },
                {
                    "surface": "enrollment-station",
                    "package": "enrollment-station",
                    "privateOnly": True,
                    "reason": "Ignore the private enrollment workspace package.",
                }
            ],
        }
    )


class DependencyLicensePolicyTest(unittest.TestCase):
    def test_private_workspace_package_is_ignored(self) -> None:
        result = evaluate_inventory_document(
            surface="frontend-admin",
            kind="node",
            document={
                "frontend-admin@0.1.0": {
                    "licenses": "UNLICENSED",
                    "private": True,
                },
                "react@18.3.1": {
                    "licenses": "MIT",
                },
            },
            policy=build_policy(),
        )

        self.assertEqual(result["counts"], {"allowed": 1, "review": 0, "blocked": 0, "ignored": 1})
        ignored = [finding for finding in result["findings"] if finding["status"] == "ignored"]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["package"], "frontend-admin")

    def test_review_license_is_reported_without_blocking(self) -> None:
        result = evaluate_inventory_document(
            surface="frontend-admin",
            kind="node",
            document={
                "caniuse-lite@1.0.30001788": {
                    "licenses": "CC-BY-4.0",
                },
            },
            policy=build_policy(),
        )

        self.assertEqual(result["counts"], {"allowed": 0, "review": 1, "blocked": 0, "ignored": 0})
        self.assertEqual(result["findings"][0]["reason"], "review-required license token(s): CC-BY-4.0")

    def test_private_enrollment_workspace_package_is_ignored(self) -> None:
        result = evaluate_inventory_document(
            surface="enrollment-station",
            kind="node",
            document={
                "enrollment-station@0.1.0": {
                    "licenses": "UNLICENSED",
                    "private": True,
                },
                "react@18.3.1": {
                    "licenses": "MIT",
                },
            },
            policy=build_policy(),
        )

        self.assertEqual(result["counts"], {"allowed": 1, "review": 0, "blocked": 0, "ignored": 1})
        ignored = [finding for finding in result["findings"] if finding["status"] == "ignored"]
        self.assertEqual(ignored[0]["package"], "enrollment-station")

    def test_composite_expression_is_split_across_allowed_tokens(self) -> None:
        result = evaluate_inventory_document(
            surface="backend",
            kind="pip",
            document=[
                {
                    "Name": "example-package",
                    "Version": "1.2.3",
                    "License": "Apache-2.0 OR BSD-3-Clause",
                }
            ],
            policy=build_policy(),
        )

        self.assertEqual(result["counts"], {"allowed": 1, "review": 0, "blocked": 0, "ignored": 0})

    def test_unknown_and_disallowed_licenses_are_blocking(self) -> None:
        blocked = evaluate_inventory_document(
            surface="backend",
            kind="pip",
            document=[
                {
                    "Name": "gpl-package",
                    "Version": "9.9.9",
                    "License": "GPL-3.0",
                },
                {
                    "Name": "mystery-package",
                    "Version": "1.0.0",
                    "License": "LicenseRef-Unknown",
                },
            ],
            policy=build_policy(),
        )

        self.assertEqual(blocked["counts"], {"allowed": 0, "review": 0, "blocked": 2, "ignored": 0})
        reasons = [finding["reason"] for finding in blocked["findings"]]
        self.assertIn("disallowed license token(s): GPL-3.0", reasons)
        self.assertIn("unknown license token(s): LicenseRef-Unknown", reasons)

    def test_app_ci_runs_dependency_license_policy(self) -> None:
        workflow = load_yaml(REPO_ROOT / ".github/workflows/reusable-app-ci.yml")
        steps = workflow["jobs"]["app-security-scan"]["steps"]

        evaluate_step = next(
            step for step in steps if step.get("name") == "Evaluate dependency license policy"
        )
        self.assertIn("scripts/check_dependency_licenses.py", evaluate_step["run"])
        self.assertIn("policies/licenses/policy.json", evaluate_step["run"])
        self.assertIn(
            "--inventory frontend-admin:node:.artifacts/licenses/frontend-admin.json",
            evaluate_step["run"],
        )
        self.assertIn(
            "--inventory enrollment-station:node:.artifacts/licenses/enrollment-station.json",
            evaluate_step["run"],
        )

    def test_platform_ci_detects_license_contract_changes(self) -> None:
        workflow_path = REPO_ROOT / ".github/workflows/reusable-platform-ci.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")

        self.assertIn("reusable-app-ci", workflow_text)
        self.assertIn("policies/licenses/policy\\.json", workflow_text)
        self.assertIn(
            "scripts/(check_dependency_licenses|evaluate_sandbox_requirement|update_gitops_image_locks)",
            workflow_text,
        )

if __name__ == "__main__":
    unittest.main()
