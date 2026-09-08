#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/app"

compose() { docker compose -f docker-compose.yml "$@"; }

if ! compose ps --status running --services 2>/dev/null | grep -qx backend; then
  echo "==> starting the v0 stack (postgres, backend)"
  compose up -d --build --wait postgres backend
fi

compose exec -T backend ruff check --fix app tests tools alembic
compose exec -T backend ruff format app tests tools alembic
