from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_compose_uses_deterministic_embedding_provider_for_smoke_e2e() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.ci.yml").read_text(encoding="utf-8"))

    for service_name in ("backend", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["EMBEDDING_PROVIDER"] == "hash"
        assert environment["EMBEDDING_DIMENSIONS"] == "512"
        assert environment["MODEL_VERSION"] == "ci-hash-512"
