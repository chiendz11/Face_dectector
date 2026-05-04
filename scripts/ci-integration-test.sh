#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "scripts/ci-integration-test.sh is deprecated; delegating to scripts/ci-e2e-test.sh"
exec "$ROOT_DIR/scripts/ci-e2e-test.sh"