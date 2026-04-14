#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/home/ubuntu/face-detector}"
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY_HOST="${REGISTRY_HOST:-ghcr.io}"
REGISTRY_ORG="${REGISTRY_ORG:?REGISTRY_ORG is required}"
GHCR_USERNAME="${GHCR_USERNAME:-github}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
ENV_FILE="${ENV_FILE:-.env.${ENVIRONMENT}}"

cd "$TARGET_DIR"

if [ -n "$GHCR_TOKEN" ]; then
  echo "Logging into ${REGISTRY_HOST} as ${GHCR_USERNAME}"
  echo "$GHCR_TOKEN" | docker login "$REGISTRY_HOST" -u "$GHCR_USERNAME" --password-stdin
fi

echo "Pulling images for ${IMAGE_TAG} from ${REGISTRY_HOST}/${REGISTRY_ORG}"
export IMAGE_HOST="$REGISTRY_HOST"
export REGISTRY_ORG
export IMAGE_TAG
export ENV_FILE

docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" pull

echo "Starting compose stack with ${ENV_FILE}"
docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" up -d --build --remove-orphans

docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" ps

# Record deployed tag for rollback
PREVIOUS_TAG_FILE=".deploy-previous-tag"
CURRENT_TAG_FILE=".deploy-current-tag"
if [ -f "$CURRENT_TAG_FILE" ]; then
  mv "$CURRENT_TAG_FILE" "$PREVIOUS_TAG_FILE"
fi

echo "$IMAGE_TAG" > "$CURRENT_TAG_FILE"
echo "Deployed image tag recorded: $IMAGE_TAG"
