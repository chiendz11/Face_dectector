#!/usr/bin/env bash
set -euo pipefail

: "${VPS_HOST:?Need VPS_HOST to deploy}"
: "${VPS_USER:?Need VPS_USER to deploy}"

SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"
TARGET_DIR="${TARGET_DIR:-/opt/face-detector}"
LOCAL_SOURCE="${LOCAL_SOURCE:-backend frontend-admin nginx docker-compose.yml .env.example}"

if [ ! -f "$SSH_KEY_PATH" ]; then
  echo "SSH key not found at $SSH_KEY_PATH"
  exit 1
fi

echo "Deploying repo to ${VPS_USER}@${VPS_HOST}:${TARGET_DIR}..."
scp -i "$SSH_KEY_PATH" -r $LOCAL_SOURCE "${VPS_USER}@${VPS_HOST}:$TARGET_DIR"

echo "Starting remote compose on VPS..."
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" <<EOF
set -e
cd "$TARGET_DIR"
cp -n .env.example .env || true
docker compose up -d --build --remove-orphans backend worker frontend-admin nginx
EOF

echo "Deploy complete."
