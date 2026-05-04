from __future__ import annotations

import argparse
import base64
import sys
import urllib.error
import urllib.parse
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve an OCI manifest digest from a registry tag/reference.")
    parser.add_argument("--registry", default="https://ghcr.io", help="Registry base URL, e.g. https://ghcr.io")
    parser.add_argument("--repository", required=True, help="Repository path without registry host")
    parser.add_argument("--reference", required=True, help="Tag or digest reference")
    parser.add_argument("--username", required=True, help="Registry username")
    parser.add_argument("--password", required=True, help="Registry password or token")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    credentials = f"{args.username}:{args.password}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")

    manifest_url = (
        f"{args.registry.rstrip('/')}/v2/{args.repository}/manifests/"
        f"{urllib.parse.quote(args.reference, safe=':@')}"
    )
    request = urllib.request.Request(manifest_url, method="HEAD")
    request.add_header("Authorization", f"Basic {encoded_credentials}")
    request.add_header(
        "Accept",
        ", ".join(
            [
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
            ]
        ),
    )

    try:
        with urllib.request.urlopen(request) as response:
            digest = response.headers.get("Docker-Content-Digest", "").strip()
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