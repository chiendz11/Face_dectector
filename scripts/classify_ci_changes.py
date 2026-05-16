from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


IMAGE_ORDER = ("backend", "frontend-admin", "edge-client", "nginx")

APP_SHARED_EXACT = {
    ".env.example",
    ".trivyignore",
    "docker-compose.yml",
    "docker-compose.ci.yml",
    ".github/image-catalog.json",
    ".github/workflows/app-ci.yml",
    ".github/workflows/reusable-app-ci.yml",
    "scripts/classify_ci_changes.py",
    "scripts/ci-e2e-test.sh",
    "scripts/resolve_registry_digest.py",
}

APP_SHARED_PREFIXES = (
    ".github/actions/build-images/",
    ".github/actions/load-images/",
    ".github/actions/save-images/",
    ".github/actions/trivy-scan-images/",
    ".github/actions/sbom-images/",
)

PLATFORM_EXACT = {
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    "scripts/classify_ci_changes.py",
    "scripts/cleanup_sandbox_aws_orphans.py",
    "scripts/ci-e2e-test.sh",
    "scripts/ci-integration-test.sh",
    "scripts/evaluate_sandbox_requirement.py",
    "scripts/generate-env-from-ssm.sh",
    "scripts/render_sandbox_status_comment.py",
    "scripts/resolve_registry_digest.py",
    "scripts/resolve_workflow_context.py",
    "scripts/update_gitops_image_locks.py",
}

PLATFORM_PREFIXES = (
    ".github/actions/",
    ".github/workflows/",
    "policies/",
    "scripts/tests/",
)

INFRA_EXACT = {
    "scripts/resolve_workflow_context.py",
}

INFRA_PREFIXES = (
    ".github/actions/setup-conftest/",
    ".github/workflows/infra-",
    ".github/workflows/reusable-infra-",
    "deploy/",
    "policies/data/",
    "policies/kubernetes/",
    "policies/terraform/",
    "terraform/",
)


@dataclass(frozen=True)
class CiChangeClassification:
    backend_changed: bool = False
    frontend_admin_changed: bool = False
    edge_client_changed: bool = False
    nginx_changed: bool = False
    app_shared_changed: bool = False
    platform_changed: bool = False
    infra_changed: bool = False

    @property
    def app_changed(self) -> bool:
        return any(
            (
                self.backend_changed,
                self.frontend_admin_changed,
                self.edge_client_changed,
                self.nginx_changed,
                self.app_shared_changed,
            )
        )

    @property
    def image_names(self) -> str:
        if self.app_shared_changed:
            return ",".join(IMAGE_ORDER)

        selected: list[str] = []
        if self.backend_changed:
            selected.append("backend")
        if self.frontend_admin_changed:
            selected.append("frontend-admin")
        if self.edge_client_changed:
            selected.append("edge-client")
        if self.nginx_changed:
            selected.append("nginx")

        return ",".join(selected)

    def as_outputs(self) -> dict[str, str]:
        return {
            "backend_changed": _bool_output(self.backend_changed),
            "frontend_admin_changed": _bool_output(self.frontend_admin_changed),
            "edge_client_changed": _bool_output(self.edge_client_changed),
            "nginx_changed": _bool_output(self.nginx_changed),
            "app_shared_changed": _bool_output(self.app_shared_changed),
            "app_changed": _bool_output(self.app_changed),
            "platform_changed": _bool_output(self.platform_changed),
            "infra_changed": _bool_output(self.infra_changed),
            "image_names": self.image_names,
        }


def classify_paths(paths: list[str]) -> CiChangeClassification:
    backend_changed = False
    frontend_admin_changed = False
    edge_client_changed = False
    nginx_changed = False
    app_shared_changed = False
    platform_changed = False
    infra_changed = False

    for raw_path in paths:
        path = raw_path.strip().replace("\\", "/")
        if not path:
            continue

        if path.startswith("backend/"):
            backend_changed = True
        elif path.startswith("frontend-admin/"):
            frontend_admin_changed = True
        elif path.startswith("edge-client/"):
            edge_client_changed = True
        elif path.startswith("nginx/"):
            nginx_changed = True

        if path in APP_SHARED_EXACT or _has_prefix(path, APP_SHARED_PREFIXES):
            app_shared_changed = True

        if path in PLATFORM_EXACT or _has_prefix(path, PLATFORM_PREFIXES):
            platform_changed = True

        if path in INFRA_EXACT or _has_prefix(path, INFRA_PREFIXES):
            infra_changed = True

    return CiChangeClassification(
        backend_changed=backend_changed,
        frontend_admin_changed=frontend_admin_changed,
        edge_client_changed=edge_client_changed,
        nginx_changed=nginx_changed,
        app_shared_changed=app_shared_changed,
        platform_changed=platform_changed,
        infra_changed=infra_changed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify changed files into CI gateway lanes."
    )
    parser.add_argument(
        "--changed-files",
        required=True,
        help="Path to a newline-delimited changed file list.",
    )
    parser.add_argument(
        "--github-output",
        default="",
        help="Optional path to append GitHub Actions outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    changed_files = Path(args.changed_files).read_text(encoding="utf-8").splitlines()
    outputs = classify_paths(changed_files).as_outputs()

    for key, value in outputs.items():
        print(f"{key}={value}")

    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")


def _has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _bool_output(value: bool) -> str:
    return "true" if value else "false"


if __name__ == "__main__":
    main()
