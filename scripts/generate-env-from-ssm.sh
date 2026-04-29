#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-production}"
OUTPUT_FILE="${OUTPUT_FILE:-.env.${ENVIRONMENT}}"
PARAM_PREFIX="${PARAM_PREFIX:-/facedetector/${ENVIRONMENT}}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"

rm -f "$OUTPUT_FILE"

stdout_file="$(mktemp)"
stderr_file="$(mktemp)"

cleanup() {
    rm -f "$stdout_file" "$stderr_file"
}

trap cleanup EXIT

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    if aws ssm get-parameters-by-path \
        --no-cli-pager \
        --path "$PARAM_PREFIX" \
        --with-decryption \
        --recursive \
        --output json \
        >"$stdout_file" 2>"$stderr_file"; then
        if python3 - "$stdout_file" "$OUTPUT_FILE" "$PARAM_PREFIX" <<'PY'
import json
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
output_file = Path(sys.argv[2])
param_prefix = sys.argv[3].rstrip("/")
payload_text = payload_path.read_text(encoding="utf-8")

if not payload_text.strip():
    raise SystemExit(f"ERROR: empty SSM response for {param_prefix}")

try:
    payload = json.loads(payload_text)
except json.JSONDecodeError as exc:
    raise SystemExit(f"ERROR: invalid JSON from SSM for {param_prefix}: {exc}") from exc

parameters = payload.get("Parameters", [])

if not parameters:
    raise SystemExit(f"ERROR: no parameters found under {param_prefix}")

entries = {}
for parameter in parameters:
    key = parameter["Name"].rsplit("/", 1)[-1]
    entries[key] = parameter["Value"]

with output_file.open("w", encoding="utf-8") as handle:
    for key in sorted(entries):
        handle.write(f"{key}={entries[key]}\n")

print(f"Generated {output_file} from SSM path {param_prefix} with {len(entries)} parameters")
PY
        then
            exit 0
        fi
    fi

    if [ -s "$stderr_file" ]; then
        cat "$stderr_file" >&2
    fi
    if [ -s "$stdout_file" ]; then
        cat "$stdout_file" >&2
    fi

    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: unable to generate runtime env file from SSM path $PARAM_PREFIX after $MAX_ATTEMPTS attempts" >&2
        exit 1
    fi

    echo "Retrying SSM env generation for $PARAM_PREFIX (attempt $attempt/$MAX_ATTEMPTS)." >&2
    sleep 3
    attempt=$((attempt + 1))
done
