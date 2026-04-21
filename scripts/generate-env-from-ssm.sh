#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-production}"
OUTPUT_FILE="${OUTPUT_FILE:-.env.${ENVIRONMENT}}"
PARAM_PREFIX="${PARAM_PREFIX:-/facedetector/${ENVIRONMENT}}"

rm -f "$OUTPUT_FILE"

aws ssm get-parameters-by-path \
  --path "$PARAM_PREFIX" \
  --with-decryption \
  --recursive \
  --output json \
  | python3 - "$OUTPUT_FILE" "$PARAM_PREFIX" <<'PY'
import json
import sys

output_file = sys.argv[1]
param_prefix = sys.argv[2].rstrip("/")
payload = json.load(sys.stdin)
parameters = payload.get("Parameters", [])

if not parameters:
    raise SystemExit(f"ERROR: no parameters found under {param_prefix}")

entries = {}
for parameter in parameters:
    key = parameter["Name"].rsplit("/", 1)[-1]
    entries[key] = parameter["Value"]

with open(output_file, "w", encoding="utf-8") as handle:
    for key in sorted(entries):
        handle.write(f"{key}={entries[key]}\n")

print(f"Generated {output_file} from SSM path {param_prefix} with {len(entries)} parameters")
PY
