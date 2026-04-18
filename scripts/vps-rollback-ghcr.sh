#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/home/ubuntu/face-detector}"
ENVIRONMENT="${ENVIRONMENT:-production}"
REGISTRY_HOST="${REGISTRY_HOST:-ghcr.io}"
REGISTRY_ORG="${REGISTRY_ORG:?REGISTRY_ORG is required}"
GHCR_USERNAME="${GHCR_USERNAME:-github}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
ENV_FILE="${ENV_FILE:-.env.${ENVIRONMENT}}"
ROLLBACK_TAG="${ROLLBACK_TAG:-}"
PREVIOUS_TAG_FILE=".deploy-previous-tag"
CURRENT_TAG_FILE=".deploy-current-tag"

cd "$TARGET_DIR"

if [ -z "$ROLLBACK_TAG" ]; then
  if [ -f "$PREVIOUS_TAG_FILE" ]; then
    ROLLBACK_TAG=$(cat "$PREVIOUS_TAG_FILE")
    echo "Using previous deployed tag from $PREVIOUS_TAG_FILE: $ROLLBACK_TAG"
  else
    echo "ERROR: ROLLBACK_TAG is not set and no $PREVIOUS_TAG_FILE file exists."
    echo "Set ROLLBACK_TAG=<tag> or deploy once to create the previous-tag file."
    exit 1
  fi
fi

if [ -n "$GHCR_TOKEN" ]; then
  echo "Logging into ${REGISTRY_HOST} as ${GHCR_USERNAME}"
  echo "$GHCR_TOKEN" | docker login "$REGISTRY_HOST" -u "$GHCR_USERNAME" --password-stdin
fi

echo "Rolling back to tag ${ROLLBACK_TAG}"
export IMAGE_HOST="$REGISTRY_HOST"
export REGISTRY_ORG
export IMAGE_TAG="$ROLLBACK_TAG"
export ENV_FILE

docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" pull

docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" up -d --build --remove-orphans

docker compose -f docker-compose.ghcr.yml --env-file "$ENV_FILE" ps

# Update rollback records
if [ -f "$CURRENT_TAG_FILE" ]; then
  CURRENT_TAG=$(cat "$CURRENT_TAG_FILE")
else
  CURRENT_TAG=""
fi

PREVIOUS_TAG=""
if [ -f "$PREVIOUS_TAG_FILE" ]; then
  PREVIOUS_TAG=$(cat "$PREVIOUS_TAG_FILE")
fi

if [ -n "$ROLLBACK_TAG" ] && [ "$ROLLBACK_TAG" != "$PREVIOUS_TAG" ]; then
  if [ -n "$CURRENT_TAG" ]; then
    mv "$CURRENT_TAG_FILE" "$PREVIOUS_TAG_FILE"
  fi
  echo "$ROLLBACK_TAG" > "$CURRENT_TAG_FILE"
  echo "Updated deployment records: CURRENT=$ROLLBACK_TAG, PREVIOUS=$CURRENT_TAG"
else
  echo "Rollback to previous tag detected; not swapping tag history to avoid flip-flopping."
  echo "$ROLLBACK_TAG" > "$CURRENT_TAG_FILE"
  echo "Updated deployment records: CURRENT=$ROLLBACK_TAG, PREVIOUS=$PREVIOUS_TAG"
fi

echo "Rollback complete. Current tag is now $ROLLBACK_TAG"
