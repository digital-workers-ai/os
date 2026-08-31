#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/app"

compose() { docker compose -f docker-compose.yml "$@"; }

mode="${1:-unit}"
[ $# -gt 0 ] && shift

case "$mode" in
  unit) pytest_args=(tests -m "not e2e and not llm") ;;
  e2e) pytest_args=(tests -m "e2e and not llm") ;;
  *)
    echo "unknown mode: $mode" >&2
    echo "expected: unit | e2e" >&2
    exit 2
    ;;
esac

if ! docker info >/dev/null 2>&1; then
  echo "docker is not running — start Docker Desktop and try again" >&2
  exit 1
fi

if ! compose ps --status running --services 2>/dev/null | grep -qx backend; then
  echo "==> starting the v0 stack (postgres, mock, backend)"
  compose up -d --build --wait postgres mock backend
fi

echo "==> ruff"
compose exec -T backend ruff check app tests
compose exec -T backend ruff format --check app tests

echo "==> $mode suite"

if [ "$mode" = "e2e" ]; then
  compose exec -T backend python -u -m pytest "${pytest_args[@]}" \
    -v --tb=short "$@"
else
  compose exec -T backend python -u -m pytest "${pytest_args[@]}" \
    --cov=app --cov-branch --cov-fail-under=100 --cov-report=term-missing:skip-covered \
    -v --tb=short "$@"
fi
