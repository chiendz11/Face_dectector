#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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
  docker compose down --volumes --remove-orphans || true
  restore_env
}
trap cleanup EXIT

echo "Starting Docker Compose integration environment..."
docker compose up -d --build

wait_for_command \
  "Postgres" \
  "docker compose exec -T db sh -lc 'pg_isready -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"'"

wait_for_command \
  "Redis" \
  "test \"\$(docker compose exec -T redis redis-cli ping | tr -d '\\r')\" = 'PONG'"

echo "Bootstrapping employee table for integration smoke test..."
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<"SQL"
CREATE TABLE IF NOT EXISTS employees (
  id SERIAL PRIMARY KEY,
  employee_code VARCHAR(32) NOT NULL UNIQUE,
  full_name VARCHAR(128) NOT NULL,
  department VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_employees_employee_code ON employees (employee_code);
SQL'

wait_for_command \
  "admin health endpoint" \
  "curl --silent --fail http://localhost/api/admin/health"

echo "Requesting JWT token..."
LOGIN_RESPONSE="$(curl --silent --show-error --fail \
  -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${ADMIN_USERNAME}\",\"password\":\"${ADMIN_PASSWORD}\"}")"
ACCESS_TOKEN="$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])["access_token"])' "$LOGIN_RESPONSE")"

EMPLOYEE_CODE="CI-$(date +%s)"
echo "Creating employee ${EMPLOYEE_CODE} through nginx -> backend -> Postgres..."
CREATE_RESPONSE="$(curl --silent --show-error --fail \
  -X POST http://localhost/api/admin/employees \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"employee_code\":\"${EMPLOYEE_CODE}\",\"full_name\":\"CI Smoke Test\",\"department\":\"Platform\"}")"
python3 -c 'import json, sys; payload = json.loads(sys.argv[1]); expected = sys.argv[2]; assert payload["employee_code"] == expected, payload' "$CREATE_RESPONSE" "$EMPLOYEE_CODE"

echo "Listing employees through authenticated admin API..."
LIST_RESPONSE="$(curl --silent --show-error --fail \
  http://localhost/api/admin/employees \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")"
python3 -c 'import json, sys; payload = json.loads(sys.argv[1]); expected = sys.argv[2]; assert any(item["employee_code"] == expected for item in payload["items"]), payload' "$LIST_RESPONSE" "$EMPLOYEE_CODE"

echo "Integration smoke test passed."
