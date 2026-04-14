#!/usr/bin/env bash
set -euo pipefail

if [ -z "${VPS_HOST:-}" ] || [ -z "${VPS_USER:-}" ]; then
  echo "Missing required environment variables."
  echo "Set VPS_HOST and VPS_USER before running this script."
  echo "Optional: SSH_KEY_PATH (defaults to ~/.ssh/id_rsa)."
  exit 1
fi

SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"

if [ ! -f "$SSH_KEY_PATH" ]; then
  echo "SSH key not found at $SSH_KEY_PATH"
  echo "Set SSH_KEY_PATH to the private key file for your AWS instance."
  exit 1
fi

echo "Connecting to ${VPS_USER}@${VPS_HOST} using key ${SSH_KEY_PATH}..."
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}"
