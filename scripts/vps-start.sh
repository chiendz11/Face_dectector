#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/home/ubuntu/face-detector}"

cd "$TARGET_DIR"

# Preserve a real .env file if one already exists on the VPS.
cp -n .env.example .env || true

echo "Starting Docker Compose services from $TARGET_DIR"
docker compose up -d --build --remove-orphans backend worker frontend-admin nginx
