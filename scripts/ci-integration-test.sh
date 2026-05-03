#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export COMPOSE_FILE_PATH="${COMPOSE_FILE_PATH:-docker-compose.yml}"

# Build the full `docker compose` invocation.
# docker-compose.ci-override.yml disables nginx rate-limiting so automated
# integration tests are not throttled by the production 5r/s limit.
COMPOSE_ARGS="-f $COMPOSE_FILE_PATH"
if [ -f "$ROOT_DIR/docker-compose.ci-override.yml" ]; then
  COMPOSE_ARGS="$COMPOSE_ARGS -f $ROOT_DIR/docker-compose.ci-override.yml"
fi
COMPOSE_CMD="docker compose $COMPOSE_ARGS"

load_env_file() {
  local env_file="$1"
  local line=""

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"

    if [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]]; then
      continue
    fi

    if [[ "$line" != *=* ]]; then
      echo "Invalid env assignment in ${env_file}: ${line}" >&2
      return 1
    fi

    export "$line"
  done < "$env_file"
}

ORIGINAL_ENV_BACKUP=""
if [ -f .env ]; then
  ORIGINAL_ENV_BACKUP="$(mktemp)"
  cp .env "$ORIGINAL_ENV_BACKUP"
fi
cp .env.example .env
load_env_file .env

restore_env() {
  if [ -n "$ORIGINAL_ENV_BACKUP" ]; then
    mv "$ORIGINAL_ENV_BACKUP" .env
  else
    rm -f .env
  fi
}

wait_for_command() {
  local description="$1"
  local command="$2"
  local attempts="${3:-30}"
  local delay_seconds="${4:-3}"

  echo "Waiting for ${description}..."
  for i in $(seq 1 "$attempts"); do
    if bash -lc "$command" >/dev/null 2>&1; then
      echo "${description} is ready."
      return 0
    fi
    echo "Waiting for ${description} (${i}/${attempts})..."
    sleep "$delay_seconds"
  done

  echo "${description} did not become ready in time."
  return 1
}

cleanup() {
  echo "Tearing down Docker Compose integration environment..."
  $COMPOSE_CMD down --volumes --remove-orphans || true
  restore_env
}
trap cleanup EXIT

echo "Starting Docker Compose integration environment..."
$COMPOSE_CMD up -d

wait_for_command \
  "Postgres" \
  "$COMPOSE_CMD exec -T db sh -lc 'pg_isready -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"'"

wait_for_command \
  "Redis" \
  "test \"\$($COMPOSE_CMD exec -T redis redis-cli ping | tr -d '\\r')\" = 'PONG'"

echo "Running Alembic migrations against Docker Compose Postgres..."
$COMPOSE_CMD exec -T backend alembic upgrade head

wait_for_command \
  "pgvector extension" \
  "test \"\$($COMPOSE_CMD exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Atc \"SELECT extname FROM pg_extension WHERE extname = '''\''vector'''\''\"' | tr -d '\\r')\" = 'vector'"

wait_for_command \
  "admin health endpoint" \
  "curl --silent --fail http://localhost/api/admin/health"

export FACE_DETECTOR_BASE_URL="http://localhost"
export FACE_DETECTOR_ADMIN_USERNAME="$ADMIN_USERNAME"
export FACE_DETECTOR_ADMIN_PASSWORD="$ADMIN_PASSWORD"
export FACE_DETECTOR_TIMEOUT_SECONDS="30"

if [ "${MINIO_USE_S3_API:-false}" = "true" ]; then
  export FACE_DETECTOR_OBJECT_STORE_MODE="local-minio"
  export FACE_DETECTOR_MINIO_ENDPOINT="${MINIO_PUBLIC_ENDPOINT}"
  export FACE_DETECTOR_MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY}"
  export FACE_DETECTOR_MINIO_SECRET_KEY="${MINIO_SECRET_KEY}"
  export FACE_DETECTOR_MINIO_BUCKET="${MINIO_BUCKET}"
else
  export FACE_DETECTOR_OBJECT_STORE_MODE="none"
fi

echo "Running pytest integration smoke suite against Docker Compose stack..."
"$PYTHON_BIN" -m pytest \
  backend/tests/integration/test_live_shared_smoke.py \
  backend/tests/integration/test_live_sandbox_smoke.py \
  -q -m integration

echo "Compose-backed integration smoke test passed."