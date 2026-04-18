#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-production}"
OUTPUT_FILE="${OUTPUT_FILE:-.env.${ENVIRONMENT}}"
PARAM_PREFIX="${PARAM_PREFIX:-/facedetector/${ENVIRONMENT}}"

PARAM_NAMES=(
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  DATABASE_URL
  REDIS_URL
  QDRANT_URL
  MINIO_ROOT_USER
  MINIO_ROOT_PASSWORD
  MINIO_ENDPOINT
  MINIO_ACCESS_KEY
  MINIO_SECRET_KEY
  MINIO_BUCKET
  AWS_S3_BUCKET
  AWS_S3_REGION
  API_PREFIX
  MODEL_NAME
  MODEL_VERSION
  MATCH_THRESHOLD
  JWT_SECRET_KEY
  ADMIN_USERNAME
  ADMIN_PASSWORD
  ACCESS_TOKEN_EXPIRE_MINUTES
  BACKEND_BASE_URL
  EDGE_DEVICE_NAME
  SCAN_INTERVAL_SECONDS
)

rm -f "$OUTPUT_FILE"

for name in "${PARAM_NAMES[@]}"; do
  parameter_name="${PARAM_PREFIX}/${name}"
  value=$(aws ssm get-parameter --name "$parameter_name" --with-decryption --query 'Parameter.Value' --output text)
  if [ "$value" = "None" ]; then
    echo "ERROR: parameter $parameter_name not found or empty" >&2
    exit 1
  fi
  printf '%s=%s\n' "$name" "$value" >> "$OUTPUT_FILE"
done

echo "Generated $OUTPUT_FILE from SSM path $PARAM_PREFIX"
