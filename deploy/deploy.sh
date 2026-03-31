#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-$(pwd)}"
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$DEPLOY_DIR"
echo "Deploying branch: $BRANCH in $DEPLOY_DIR"

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

docker compose -f docker-compose.prod.yml up -d --build
docker image prune -f

echo "Waiting for service health check..."
for i in {1..30}; do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    echo "Deployment healthy."
    exit 0
  fi
  sleep 2
done

echo "Health check failed."
exit 1
