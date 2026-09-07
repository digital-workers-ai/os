#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/app"

compose() { docker compose -f docker-compose.yml "$@"; }
compose_snap() { docker compose -p os_snap -f docker-compose.yml -f docker-compose.snap.yml "$@"; }

mode="${1:-unit}"
[ $# -gt 0 ] && shift

case "$mode" in
  unit) pytest_args=(tests -m "not e2e and not llm") ;;
  e2e) pytest_args=(tests -m "e2e and not llm") ;;
  snap) snap_script=snap ;;
  snap-update) snap_script=snap:update ;;
  *)
    echo "unknown mode: $mode" >&2
    echo "expected: unit | e2e | snap | snap-update" >&2
    exit 2
    ;;
esac

if ! docker info >/dev/null 2>&1; then
  echo "docker is not running — start Docker Desktop and try again" >&2
  exit 1
fi

wait_for_frontend() {
  for _ in $(seq 60); do
    if compose_snap exec -T frontend wget -qO- http://127.0.0.1:3000 >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  echo "frontend did not answer within 5 minutes" >&2
  return 1
}

post_api() {
  for _ in $(seq 5); do
    code=$(compose_snap exec -T backend python -c "
import urllib.error, urllib.request
request = urllib.request.Request('http://localhost:8000/api/$1', method='POST')
try:
    print(urllib.request.urlopen(request).status)
except urllib.error.HTTPError as e:
    print(e.code)
")
    echo "POST /api/$1 -> $code"
    case "$code" in
      2*) return 0 ;;
      409) sleep 3 ;;
      *) return 1 ;;
    esac
  done
  return 1
}

if [ -n "${snap_script:-}" ]; then
  echo "==> fresh snap stack (postgres, mock, backend, frontend)"
  docker volume create os_frontend_node_modules >/dev/null
  compose_snap down -v --remove-orphans
  compose_snap up -d --build --wait postgres mock backend
  compose_snap up -d --build frontend
  wait_for_frontend
  echo "==> sync + rebuild"
  post_api sync
  post_api rebuild
  post_api rebuild
  if [ -f backend/tools/seed_demo.py ]; then
    echo "==> seed demo data"
    compose_snap exec -T backend python -m tools.seed_demo
  else
    echo "==> backend/tools/seed_demo.py is absent — skipping the seed"
  fi
  echo "==> playwright ($snap_script)"
  compose_snap run --rm playwright npm run "$snap_script" -- "$@"
  exit 0
fi

if ! compose ps --status running --services 2>/dev/null | grep -qx backend; then
  echo "==> starting the v0 stack (postgres, mock, backend)"
  compose up -d --build --wait postgres mock backend
fi

if [ "$mode" = "unit" ]; then
  echo "==> search vocabulary"
  python3 backend/tools/check_search_vocab.py
fi

echo "==> ruff"
compose exec -T backend ruff check app tests tools
compose exec -T backend ruff format --check app tests tools

echo "==> $mode suite"

if [ "$mode" = "e2e" ]; then
  compose exec -T backend python -u -m pytest "${pytest_args[@]}" \
    -v --tb=short "$@"
else
  compose exec -T backend python -u -m pytest "${pytest_args[@]}" \
    --cov=app --cov-branch --cov-fail-under=100 --cov-report=term-missing:skip-covered \
    -v --tb=short "$@"
fi
