#!/usr/bin/env python3
"""
Validate that no entry in policies/pip-audit-ignore.txt has passed its expiry date.

Usage: python scripts/check_pip_audit_exceptions.py policies/pip-audit-ignore.txt

Exit 0  — all entries valid.
Exit 1  — one or more entries are expired; CI must fail to force a security review.

Line format (fields separated by #):
  CVE_ID  # package @ version  # expires: YYYY-MM-DD  # reason: ...
"""
import re
import sys
from datetime import date, datetime

EXPIRY_RE = re.compile(r"expires:\s*(\d{4}-\d{2}-\d{2})")


def main(policy_file: str) -> int:
    today = date.today()
    expired: list[tuple[int, str, date]] = []

    with open(policy_file, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            m = EXPIRY_RE.search(line)
            if not m:
                print(
                    f"::error file={policy_file},line={lineno}::"
                    f"Missing 'expires: YYYY-MM-DD' field — {line}",
                    file=sys.stderr,
                )
                return 1

            expiry = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            cve_id = line.split()[0]

            if expiry < today:
                expired.append((lineno, cve_id, expiry))

    if expired:
        print(
            "::error::The following pip-audit exception(s) have expired and must be "
            "reviewed. Either remove the entry (if the package is now fixed in "
            "requirements.txt) or extend the expiry date with a fresh justification.",
            file=sys.stderr,
        )
        for lineno, cve_id, expiry in expired:
            print(
                f"  line {lineno}: {cve_id} expired on {expiry} "
                f"({(today - expiry).days} days ago)",
                file=sys.stderr,
            )
        return 1

    print(f"All {sum(1 for _ in open(policy_file) if _.strip() and not _.startswith('#'))} "
          f"exception(s) are within their expiry window.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <policy-file>", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
