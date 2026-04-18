#!/usr/bin/env bash
set -euo pipefail

if [ -z "${VPS_USER:-}" ] || [ -z "${VPS_HOST:-}" ]; then
  echo "Usage: VPS_USER=username VPS_HOST=host bash scripts/setup-vps.sh"
  exit 1
fi

SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"

if [ ! -f "$SSH_KEY_PATH" ]; then
  echo "SSH key not found at $SSH_KEY_PATH"
  exit 1
fi

echo "Connecting to ${VPS_USER}@${VPS_HOST} to install Docker and Docker Compose..."
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" <<'EOF'
set -e
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker
EOF

echo "Docker installation complete. Reconnect to apply group membership if necessary."
