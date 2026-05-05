from __future__ import annotations

import argparse
import base64
import http.client
import json
import re
import sys
import time
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

_DIGEST_RE = re.compile(r"^[a-z0-9]+:[a-f0-9]{64,}$")
_TRANSIENT_HTTP_CODES = frozenset({429, 500, 502, 503, 504})

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve an OCI manifest digest from a registry tag/reference.")
    parser.add_argument("--registry", default="https://ghcr.io", help="Registry base URL, e.g. https://ghcr.io")
    parser.add_argument("--repository", required=True, help="Repository path without registry host")
    parser.add_argument("--reference", required=True, help="Tag or digest reference")
    parser.add_argument("--username", required=True, help="Registry username")
    parser.add_argument("--password", required=True, help="Registry password or token")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP request timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max retries on transient errors")
    return parser.parse_args()


def build_manifest_request(manifest_url: str, auth_header: str | None = None) -> urllib.request.Request:
    request = urllib.request.Request(manifest_url, method="HEAD")
    if auth_header:
        request.add_header("Authorization", auth_header)
    request.add_header("Accept", ACCEPT_MANIFEST)
    return request


def extract_digest(response_headers: http.client.HTTPMessage) -> str:
    return response_headers.get("Docker-Content-Digest", "").strip()


def validate_digest(digest: str) -> bool:
    return bool(_DIGEST_RE.match(digest))


def parse_bearer_challenge(header_value: str) -> dict[str, str]:
    scheme, _, params_fragment = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return {}

    return {key: value for key, value in re.findall(r'([A-Za-z]+)="([^"]*)"', params_fragment)}


def request_bearer_token(challenge_header: str, encoded_credentials: str, timeout: int) -> str:
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

    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")

    return str(payload.get("token") or payload.get("access_token") or "").strip()


def _do_resolve(manifest_url: str, encoded_credentials: str, timeout: int) -> str:
    basic_request = build_manifest_request(manifest_url, auth_header=f"Basic {encoded_credentials}")

    try:
        with urllib.request.urlopen(basic_request, timeout=timeout) as response:
            return extract_digest(response.headers)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise

        bearer_token = request_bearer_token(exc.headers.get("WWW-Authenticate", ""), encoded_credentials, timeout)
        if not bearer_token:
            raise

        bearer_request = build_manifest_request(manifest_url, auth_header=f"Bearer {bearer_token}")
        with urllib.request.urlopen(bearer_request, timeout=timeout) as response:
            return extract_digest(response.headers)


def resolve_digest(
    manifest_url: str,
    encoded_credentials: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _do_resolve(manifest_url, encoded_credentials, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in _TRANSIENT_HTTP_CODES:
                raise
            last_exc = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc

        if attempt < max_retries - 1:
            wait = 2.0 * (2**attempt)
            print(f"Transient error on attempt {attempt + 1}/{max_retries}, retrying in {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)

    raise last_exc  # type: ignore[misc]


def main() -> int:
    args = parse_args()
    credentials = f"{args.username}:{args.password}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")

    manifest_url = (
        f"{args.registry.rstrip('/')}/v2/{args.repository}/manifests/"
        f"{urllib.parse.quote(args.reference, safe=':@')}"
    )

    try:
        digest = resolve_digest(manifest_url, encoded_credentials, timeout=args.timeout, max_retries=args.max_retries)
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
    except TimeoutError:
        print(
            f"Timed out resolving digest for {args.repository}:{args.reference} from {args.registry} "
            f"(timeout={args.timeout}s).",
            file=sys.stderr,
        )
        return 1

    if not digest:
        print(
            f"Registry {args.registry} did not return Docker-Content-Digest for {args.repository}:{args.reference}.",
            file=sys.stderr,
        )
        return 1

    if not validate_digest(digest):
        print(
            f"Registry {args.registry} returned an invalid digest format for {args.repository}:{args.reference}: "
            f"{digest!r}.",
            file=sys.stderr,
        )
        return 1

    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())