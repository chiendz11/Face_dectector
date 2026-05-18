from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


LICENSE_SPLIT_RE = re.compile(r"\s+(?:OR|AND)\s+|[;,]")
UNKNOWN_LICENSE_TOKENS = {
    "",
    "n/a",
    "none",
    "unknown",
    "unlicenced",
    "unlicensed",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate dependency license inventories against the repository policy."
    )
    parser.add_argument(
        "--policy",
        required=True,
        help="Path to the JSON policy file.",
    )
    parser.add_argument(
        "--inventory",
        action="append",
        default=[],
        metavar="SURFACE:KIND:PATH",
        help="Inventory descriptor. KIND must be 'pip' or 'node'.",
    )
    parser.add_argument(
        "--report-path",
        help="Optional path to write a JSON summary report.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Treat review-required licenses as blocking.",
    )
    return parser.parse_args(argv)


def canonicalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("*")).strip().casefold()


def normalize_token(token: str) -> str:
    token = re.sub(r"\s+", " ", token.strip().strip("*")).strip()
    while token.startswith("(") and token.endswith(")") and len(token) > 1:
        token = token[1:-1].strip()
    return token


def split_license_expression(expression: str) -> list[str]:
    if not expression:
        return []

    tokens: list[str] = []
    for part in LICENSE_SPLIT_RE.split(expression):
        token = normalize_token(part)
        if token:
            tokens.append(token)
    return tokens


def decode_json_document(path: Path) -> Any:
    raw = path.read_bytes()
    last_error: Exception | None = None
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return json.loads(raw.decode(encoding))
        except Exception as exc:  # pragma: no cover - exercised via fallback files
            last_error = exc
    raise ValueError(f"Unable to decode JSON document {path}: {last_error}")


def compile_policy(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed": {canonicalize(item) for item in document.get("allowedLicenses", [])},
        "review": {canonicalize(item) for item in document.get("reviewLicenses", [])},
        "disallowed": {canonicalize(item) for item in document.get("disallowedLicenses", [])},
        "ignore_rules": [
            {
                "surface": rule["surface"],
                "package": rule["package"],
                "private_only": bool(rule.get("privateOnly", False)),
                "reason": rule.get("reason", "Ignored by policy."),
            }
            for rule in document.get("ignorePackages", [])
        ],
        "review_rules": [
            {
                "surface": rule["surface"],
                "package": rule["package"],
                "private_only": bool(rule.get("privateOnly", False)),
                "reason": rule.get("reason", "Review required by package policy."),
            }
            for rule in document.get("reviewPackages", [])
        ],
    }


def load_policy(path: Path) -> dict[str, Any]:
    return compile_policy(json.loads(path.read_text(encoding="utf-8")))


def parse_inventory_spec(spec: str) -> dict[str, Any]:
    parts = spec.split(":", 2)
    if len(parts) != 3:
        raise ValueError(
            f"Invalid inventory spec {spec!r}; expected SURFACE:KIND:PATH."
        )

    surface, kind, raw_path = parts
    if kind not in {"pip", "node"}:
        raise ValueError(f"Unsupported inventory kind {kind!r} in {spec!r}.")

    return {
        "surface": surface,
        "kind": kind,
        "path": Path(raw_path),
    }


def split_node_package_ref(ref: str) -> tuple[str, str]:
    if ref.startswith("@"):
        package, _, version = ref.rpartition("@")
        return package, version

    if "@" not in ref:
        return ref, ""

    package, version = ref.rsplit("@", 1)
    return package, version


def iter_inventory_packages(surface: str, kind: str, document: Any) -> list[dict[str, Any]]:
    if kind == "pip":
        return [
            {
                "surface": surface,
                "package": str(item.get("Name", "")).strip(),
                "version": str(item.get("Version", "")).strip(),
                "license": str(item.get("License", "")).strip(),
                "private": False,
            }
            for item in document
        ]

    packages: list[dict[str, Any]] = []
    for ref, meta in sorted(document.items()):
        package, version = split_node_package_ref(ref)
        packages.append(
            {
                "surface": surface,
                "package": package,
                "version": version,
                "license": str(meta.get("licenses", "")).strip(),
                "private": bool(meta.get("private", False)),
            }
        )
    return packages


def match_ignore_rule(
    *,
    surface: str,
    package: str,
    is_private: bool,
    policy: dict[str, Any],
) -> str | None:
    for rule in policy["ignore_rules"]:
        if rule["surface"] != surface or rule["package"] != package:
            continue
        if rule["private_only"] and not is_private:
            continue
        return str(rule["reason"])
    return None


def match_review_rule(
    *,
    surface: str,
    package: str,
    is_private: bool,
    policy: dict[str, Any],
) -> str | None:
    for rule in policy["review_rules"]:
        if rule["surface"] != surface or rule["package"] != package:
            continue
        if rule["private_only"] and not is_private:
            continue
        return str(rule["reason"])
    return None


def classify_license_expression(
    expression: str,
    policy: dict[str, Any],
) -> tuple[str, list[str], str]:
    tokens = split_license_expression(expression)
    if not tokens:
        return "blocked", [], "missing license metadata"

    review_tokens: list[str] = []
    disallowed_tokens: list[str] = []
    unknown_tokens: list[str] = []

    for token in tokens:
        canonical = canonicalize(token)
        if canonical in policy["disallowed"] or canonical in UNKNOWN_LICENSE_TOKENS:
            disallowed_tokens.append(token)
            continue
        if canonical in policy["allowed"]:
            continue
        if canonical in policy["review"]:
            review_tokens.append(token)
            continue
        unknown_tokens.append(token)

    if disallowed_tokens:
        joined = ", ".join(disallowed_tokens)
        return "blocked", tokens, f"disallowed license token(s): {joined}"

    if unknown_tokens:
        joined = ", ".join(unknown_tokens)
        return "blocked", tokens, f"unknown license token(s): {joined}"

    if review_tokens:
        joined = ", ".join(review_tokens)
        return "review", tokens, f"review-required license token(s): {joined}"

    return "allowed", tokens, "allowed by policy"


def evaluate_inventory_document(
    *,
    surface: str,
    kind: str,
    document: Any,
    policy: dict[str, Any],
) -> dict[str, Any]:
    counts = {
        "allowed": 0,
        "review": 0,
        "blocked": 0,
        "ignored": 0,
    }
    findings: list[dict[str, Any]] = []

    for package in iter_inventory_packages(surface, kind, document):
        ignore_reason = match_ignore_rule(
            surface=surface,
            package=package["package"],
            is_private=package["private"],
            policy=policy,
        )
        if ignore_reason:
            counts["ignored"] += 1
            findings.append(
                {
                    **package,
                    "status": "ignored",
                    "tokens": split_license_expression(package["license"]),
                    "reason": ignore_reason,
                }
            )
            continue

        review_reason = match_review_rule(
            surface=surface,
            package=package["package"],
            is_private=package["private"],
            policy=policy,
        )
        if review_reason:
            counts["review"] += 1
            findings.append(
                {
                    **package,
                    "status": "review",
                    "tokens": split_license_expression(package["license"]),
                    "reason": review_reason,
                }
            )
            continue

        status, tokens, reason = classify_license_expression(package["license"], policy)
        counts[status] += 1
        findings.append(
            {
                **package,
                "status": status,
                "tokens": tokens,
                "reason": reason,
            }
        )

    return {
        "surface": surface,
        "kind": kind,
        "counts": counts,
        "findings": findings,
    }


def evaluate_inventories(
    inventory_documents: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    surfaces: list[dict[str, Any]] = []
    review_findings: list[dict[str, Any]] = []
    blocked_findings: list[dict[str, Any]] = []

    for inventory in inventory_documents:
        result = evaluate_inventory_document(
            surface=inventory["surface"],
            kind=inventory["kind"],
            document=inventory["document"],
            policy=policy,
        )
        surfaces.append(result)
        review_findings.extend(
            finding for finding in result["findings"] if finding["status"] == "review"
        )
        blocked_findings.extend(
            finding for finding in result["findings"] if finding["status"] == "blocked"
        )

    return {
        "surfaces": surfaces,
        "reviewFindings": review_findings,
        "blockedFindings": blocked_findings,
    }


def print_summary(result: dict[str, Any]) -> None:
    print("Dependency license summary")
    for surface in result["surfaces"]:
        counts = surface["counts"]
        print(
            "- "
            f"{surface['surface']}: "
            f"allowed={counts['allowed']}, "
            f"review={counts['review']}, "
            f"blocked={counts['blocked']}, "
            f"ignored={counts['ignored']}"
        )

    if result["reviewFindings"]:
        print("\nReview-required dependency licenses")
        for finding in result["reviewFindings"]:
            package_ref = f"{finding['package']}@{finding['version']}".rstrip("@")
            print(
                f"- [{finding['surface']}] {package_ref}: "
                f"{finding['license']} ({finding['reason']})"
            )

    if result["blockedFindings"]:
        print("\nBlocking dependency license findings", file=sys.stderr)
        for finding in result["blockedFindings"]:
            package_ref = f"{finding['package']}@{finding['version']}".rstrip("@")
            print(
                f"- [{finding['surface']}] {package_ref}: "
                f"{finding['license']} ({finding['reason']})",
                file=sys.stderr,
            )


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_policy(Path(args.policy))

    inventory_documents = []
    for spec in args.inventory:
        inventory = parse_inventory_spec(spec)
        inventory_documents.append(
            {
                **inventory,
                "document": decode_json_document(inventory["path"]),
            }
        )

    result = evaluate_inventories(inventory_documents, policy)
    print_summary(result)

    if args.report_path:
        write_report(Path(args.report_path), result)

    if result["blockedFindings"]:
        return 1
    if args.fail_on_review and result["reviewFindings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
