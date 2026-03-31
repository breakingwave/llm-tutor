#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <repo_ssh_url> <deploy_dir>"
  echo "Example: $0 git@github.com:you/llm_tutor.git /opt/llm_tutor"
  exit 1
fi

REPO_URL="$1"
DEPLOY_DIR="$2"

echo "Installing Docker and dependencies..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw

if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "Preparing deployment directory..."
sudo mkdir -p "$DEPLOY_DIR"
sudo chown -R "$USER":"$USER" "$DEPLOY_DIR"

if [[ ! -d "$DEPLOY_DIR/.git" ]]; then
  git clone "$REPO_URL" "$DEPLOY_DIR"
fi

cd "$DEPLOY_DIR"
if [[ ! -f .env.production ]]; then
  cp .env.production.example .env.production
  echo "Created .env.production. Fill in real API keys before first deploy."
fi

mkdir -p deploy/certbot-www deploy/certs

echo "Bootstrap complete."
echo "Next steps:"
echo "1) Edit $DEPLOY_DIR/.env.production"
echo "2) Run: bash deploy/deploy.sh"
