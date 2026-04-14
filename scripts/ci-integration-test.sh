#!/usr/bin/env bash
set -euo pipefail

echo "Starting Docker Compose integration environment..."
docker compose up -d --build

cleanup() {
  echo "Tearing down Docker Compose integration environment..."
  docker compose down --volumes
}
trap cleanup EXIT

# wait for the backend to become healthy via nginx proxy
echo "Waiting for /api/health to respond..."
for i in $(seq 1 20); do
  if curl --silent --fail http://localhost/api/health >/dev/null 2>&1; then
    echo "Backend is healthy."
    break
  fi
  echo "Waiting for service startup ($i/20)..."
  sleep 3
  if [ "$i" -eq 20 ]; then
    echo "Service did not become healthy in time."
    exit 1
  fi
done

echo "Integration smoke test passed."
