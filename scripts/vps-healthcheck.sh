#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${HEALTH_URL:-http://localhost/api/health}"
TIMEOUT=${TIMEOUT:-20}

printf "Waiting for service health at %s\n" "$HEALTH_URL"
for i in $(seq 1 "$TIMEOUT"); do
  if curl --silent --fail "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Service is healthy."
    exit 0
  fi
  echo "Health check attempt $i/$TIMEOUT failed, retrying..."
  sleep 3
done

echo "Service did not become healthy after $TIMEOUT attempts."
exit 1
