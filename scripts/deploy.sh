#!/usr/bin/env bash
# Build and start the production stack locally or on a server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.production.example to .env and configure secrets."
  exit 1
fi

docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "Stack started. Open http://localhost:${HTTP_PORT:-8080}"
echo "Create admin: docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.create_admin admin PASSWORD 'Admin'"
