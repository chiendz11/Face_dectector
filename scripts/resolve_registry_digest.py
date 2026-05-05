from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


ACCEPT_MANIFEST = ", ".join(
    [
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve an OCI manifest digest from a registry tag/reference.")
    parser.add_argument("--registry", default="https://ghcr.io", help="Registry base URL, e.g. https://ghcr.io")
    parser.add_argument("--repository", required=True, help="Repository path without registry host")
    parser.add_argument("--reference", required=True, help="Tag or digest reference")
    parser.add_argument("--username", required=True, help="Registry username")
    parser.add_argument("--password", required=True, help="Registry password or token")
    return parser.parse_args()


def build_manifest_request(manifest_url: str, auth_header: str | None = None) -> urllib.request.Request:
    request = urllib.request.Request(manifest_url, method="HEAD")
    if auth_header:
        request.add_header("Authorization", auth_header)
    request.add_header("Accept", ACCEPT_MANIFEST)
    return request


def extract_digest(response_headers: urllib.response.addinfourl.headers) -> str:
    return response_headers.get("Docker-Content-Digest", "").strip()


def parse_bearer_challenge(header_value: str) -> dict[str, str]:
    scheme, _, params_fragment = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return {}

    return {key: value for key, value in re.findall(r'([A-Za-z]+)="([^"]*)"', params_fragment)}


def request_bearer_token(challenge_header: str, encoded_credentials: str) -> str:
    challenge = parse_bearer_challenge(challenge_header)
    realm = challenge.get("realm", "").strip()
    if not realm:
        return ""

    query = {
        key: value
        for key in ("service", "scope")
        if (value := challenge.get(key, "").strip())
    }
    token_url = realm
    if query:
        separator = "&" if "?" in realm else "?"
        token_url = f"{realm}{separator}{urllib.parse.urlencode(query)}"

    request = urllib.request.Request(token_url, method="GET")
    request.add_header("Authorization", f"Basic {encoded_credentials}")
    request.add_header("Accept", "application/json")

    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")

    return str(payload.get("token") or payload.get("access_token") or "").strip()


def resolve_digest(manifest_url: str, encoded_credentials: str) -> str:
    basic_request = build_manifest_request(manifest_url, auth_header=f"Basic {encoded_credentials}")

    try:
        with urllib.request.urlopen(basic_request) as response:
            return extract_digest(response.headers)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise

        bearer_token = request_bearer_token(exc.headers.get("WWW-Authenticate", ""), encoded_credentials)
        if not bearer_token:
            raise

        bearer_request = build_manifest_request(manifest_url, auth_header=f"Bearer {bearer_token}")
        with urllib.request.urlopen(bearer_request) as response:
            return extract_digest(response.headers)


def main() -> int:
    args = parse_args()
    credentials = f"{args.username}:{args.password}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")

    manifest_url = (
        f"{args.registry.rstrip('/')}/v2/{args.repository}/manifests/"
        f"{urllib.parse.quote(args.reference, safe=':@')}"
    )

    try:
        digest = resolve_digest(manifest_url, encoded_credentials)
    except urllib.error.HTTPError as exc:
        print(
            f"Failed to resolve digest for {args.repository}:{args.reference} from {args.registry}: "
            f"{exc.code} {exc.reason}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"Failed to reach registry {args.registry}: {exc.reason}", file=sys.stderr)
        return 1

    if not digest:
        print(
            f"Registry {args.registry} did not return Docker-Content-Digest for {args.repository}:{args.reference}.",
            file=sys.stderr,
        )
        return 1

    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())